from flask import Flask, request, jsonify
from flask_cors import CORS
from rapidfuzz import process
import pandas as pd
import numpy as np
import re
import ast
import requests

from werkzeug.middleware.proxy_fix import ProxyFix

TMDB_API_KEY = 'a1fe2f0ac92d2dd849674115d68777a5'

app = Flask(__name__)
CORS(app)

app.wsgi_app = ProxyFix(app.wsgi_app)

movies = pd.read_csv('processed_movies.csv')
movies_titles = movies['title'].tolist()

def get_suggested_titles(user_input):
    results = process.extract(user_input, movies_titles, limit=5)
    return [result[0] for result in results]

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
    movie_row = movies[movies['title'] == movie]
    
    if movie_row.empty:
        return jsonify({"error": "Movie not found"}), 404

    recommended_indexes = ast.literal_eval(movie_row.iloc[0]['top_recommendations'])
    
    recommended_movies = []
    for counter, i in enumerate(recommended_indexes, start = 1):
        title = movies.iloc[i]['title']
        overview = movies.iloc[i]['overview']
        cast_list = ast.literal_eval(movies.iloc[i]['cast'])
        cast = split_names(', '.join(cast_list))
        crew_list = ast.literal_eval(movies.iloc[i]['crew'])
        crew = split_names(', '.join(crew_list))
        year = str(movies.iloc[i]['year'])
        imdb_score = handle_missing_values(movies.iloc[i]['imdb_score'])
        rt_score = handle_missing_values(movies.iloc[i]['rt_score'])
        poster_html = get_poster_html(movies.iloc[i]['movie_id'])
        movie_title_link_html = get_movie_link_html(title)
        recommended_movies.append({
            "counter": counter,
            "poster_html": poster_html,
            "movie_title_link_html": movie_title_link_html,
            "overview": overview,
            "cast": cast,
            "crew": crew,
            "title": title,
            "year": year,
            'rt_score': rt_score,
            'imdb_score': imdb_score
        })
        
    
    return recommended_movies

@app.route('/recommend', methods=['GET'])
def recommend_movies():
    movie = request.args.get('movie')
    
    # Check if the movie exists exactly in the dataset
    movie_row = movies[movies['title'] == movie]
    
    if movie_row.empty:
        # Fuzzy matching: get closest movie title suggestions
        suggestions = get_suggested_titles(movie)
        closest_match = suggestions[0] if suggestions else None
        print(closest_match)
        if closest_match:
            message = f"Did you mean '{closest_match}'?"
            recommendations = recommendations_list(closest_match)
            return jsonify({
                "flag": "False",
                "message": message,
                "match": closest_match,
                "recommendations": recommendations
            })
        else:
            return jsonify({"error": "No similar movie found for your query."}), 404
    else:
        recommendations = recommendations_list(movie)
        return jsonify({
            "flag": "True",
            "match": movie,
            "recommendations": recommendations
        })

@app.route('/get_suggestions', methods=['GET'])
def get_suggestions():
    user_input = request.args.get('query')
    suggestions = get_suggested_titles(user_input)
    return jsonify({'suggestions': suggestions})

def lambda_handler(event, context):
    from zappa.middleware import ZappaMiddleware
    app.wsgi_app = ZappaMiddleware(app.wsgi_app)
    return app

if __name__ == '__main__':
    app.run(debug=True)