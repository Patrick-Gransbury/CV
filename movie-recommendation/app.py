from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import re
import ast
import requests
from sklearn.feature_extraction.text import CountVectorizer
from nltk.stem.porter import PorterStemmer

TMDB_API_KEY = 'a1fe2f0ac92d2dd849674115d68777a5'

app = Flask(__name__)
CORS(app)

movies = pd.read_csv('processed_movies.csv')
similarity = np.load('similarity_matrix.npy')

def handle_missing_values(x):
    if isinstance(x, (int, float)):  # If the value is numeric
        return 0 if np.isnan(x) else x  # Replace NaN with 0
    elif pd.isna(x) or x == '' or x is None:  # If the value is empty (NaN, None, empty string)
        return 0  # Replace empty or None with 0
    else:
        return x  # If the value is valid, leave it unchanged

def split_names(name):
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', name)

def fetch_movie_details(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US'
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching details for movie ID {movie_id}: {e}")
        return None
    
def fetch_poster_path(movie_id):
    data = fetch_movie_details(movie_id)
    poster_path = data.get('poster_path')
    if poster_path:
        return f'https://image.tmdb.org/t/p/w500/{poster_path}'
    
def get_poster_html(movie_id):
    poster_path = fetch_poster_path(movie_id)
    if poster_path:
        return f'<img src="{poster_path}" style="max-height:150px;">'
    else:
        return ''
    
def get_movie_link_html(title):
    google_search_link = f'https://www.google.com/search?q={title}'
    return f'<a href="{google_search_link}" target="_blank">{title}</a>'

def recommendations_list(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:26]
    
    # Create a dictionary to store the combined scores (similarity + popularity_weight * popularity)
    combined_scores = {}
    
    w_similarity = 0.9
    w_popularity = 0.1
    # w_imbd = 0.1

    for i in movies_list:
        index = i[0]
        sim_score = i[1]
        
        pop_score = movies.iloc[index]['popularity_log_norm']

        # Calculate the combined score
        combined_score = (w_similarity * sim_score
                          + w_popularity * pop_score)

        combined_scores[index] = combined_score

    # Sort the dictionary by combined scores in descending order
    
    sorted_combined_scores = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

    # Get the top 10 movies based on the combined scores
    movies_final_list = sorted_combined_scores[:10]
    
    recommended_movies = []
    for counter, i in enumerate(movies_final_list, start = 1):
        title = movies.iloc[i[0]]['title']
        overview = movies.iloc[i[0]]['overview']
        cast_list = ast.literal_eval(movies.iloc[i[0]]['cast'])
        cast = split_names(', '.join(cast_list))
        crew_list = ast.literal_eval(movies.iloc[i[0]]['crew'])
        crew = split_names(', '.join(crew_list))
        imdb_score = handle_missing_values(movies.iloc[i[0]]['imdb_score'])
        rt_score = handle_missing_values(movies.iloc[i[0]]['rt_score'])
        poster_html = get_poster_html(movies.iloc[i[0]]['movie_id'])
        movie_title_link_html = get_movie_link_html(title)
        recommended_movies.append({
            "counter": counter,
            "poster_html": poster_html,
            "movie_title_link_html": movie_title_link_html,
            "overview": overview,
            "cast": cast,
            "crew": crew,
            "title": title,
            'rt_score': rt_score,
            'imdb_score': imdb_score
        })
        
    
    return recommended_movies

@app.route('/recommend', methods=['GET'])
def recommend_movies():
    movie = request.args.get('movie')
    if not movie:
        return jsonify({"error": "Please provide a movie name in the 'movie' query parameter"}), 400
    
    recommendations = recommendations_list(movie)
    return jsonify(recommendations)

if __name__ == '__main__':
    app.run(debug=True)