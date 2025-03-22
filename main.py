import numpy as np
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import csr_matrix
import sqlite3
import json
from bs4 import BeautifulSoup
import urllib.request
import pickle
import requests
from datetime import datetime

# Load the NLP model and TF-IDF vectorizer
filename = 'nlp_model.pkl'
with open(filename, 'rb') as f:
    clf = pickle.load(f)

with open('transform.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

# Flask Application
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key


# Initialize SQLite Database for Authentication
# Update SQLite Database Schema for Search History
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS search_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        movie TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (username) REFERENCES users(username))''')
    conn.commit()
    conn.close()


init_db()


# Save Search Query
def save_search(username, movie):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO search_history (username, movie) VALUES (?, ?)", (username, movie))
    conn.commit()
    conn.close()


# Get Search History
def get_search_history(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT movie, timestamp FROM search_history WHERE username = ? ORDER BY timestamp DESC",
                   (username,))
    history = cursor.fetchall()
    conn.close()
    return history


# Get Trending Movies
def get_trending_movies():
    api_key = "351aef8735cc66f2cd77af1e485fd71c"  # Replace with your TMDb API key
    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={api_key}"

    response = requests.get(url)
    data = response.json()

    if response.status_code == 200:
        return data.get('results', [])
    else:
        return []


# Movie Recommendation System Functions
def create_similarity():
    data = pd.read_csv('main_data.csv')
    cv = CountVectorizer()
    count_matrix = cv.fit_transform(data['comb'])
    similarity = cosine_similarity(count_matrix)
    return data, similarity


def rcmd(m, data=None, similarity=None):
    m = m.lower()
    try:
        data.head()
        similarity.shape
    except AttributeError:
        data, similarity = create_similarity()

    if m not in data['movie_title'].str.lower().unique():
        return 'Sorry! Try another movie name.'
    else:
        i = data[data['movie_title'].str.lower() == m].index[0]
        lst = list(enumerate(similarity[i]))
        lst = sorted(lst, key=lambda x: x[1], reverse=True)
        lst = lst[1:11]
        recommendations = [data['movie_title'][x[0]] for x in lst]
        return recommendations


def convert_to_list(my_list):
    if isinstance(my_list, str):
        my_list = my_list.strip('[]').split('","')
        my_list = [item.replace('"', '').strip() for item in my_list]
    return my_list


def get_suggestions():
    data = pd.read_csv('main_data.csv')
    return list(data['movie_title'].str.capitalize())


# Routes
@app.route("/")
@app.route("/home")
def home():
    if 'username' in session:
        suggestions = get_suggestions()
        history = get_search_history(session['username'])
        trending = get_trending_movies()
        return render_template('home.html', suggestions=suggestions, username=session['username'], history=history, trending=trending, current_year=datetime.now().year)
    else:
        return redirect(url_for('login'))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if validate_user(username, password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html')


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if register_user(username, password):
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for('login'))
        else:
            flash("Username already exists. Please try a different one.", "danger")
    return render_template('signup.html')


@app.route("/logout")
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))


# User Authentication and Registration Helpers
def validate_user(username, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user


def register_user(username, password):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


# Route to display search history
@app.route("/history")
def history():
    if 'username' in session:
        history = get_search_history(session['username'])
        return render_template('history.html', history=history)
    else:
        flash("You need to log in to view your history.", "danger")
        return redirect(url_for('login'))


# Route to display trending movies
@app.route("/trending")
def trending():
    trending_movies = get_trending_movies()
    return render_template('trending.html', trending=trending_movies)


# Route to handle movie similarity search and saving search history
@app.route("/similarity", methods=["POST"])
def similarity():
    movie = request.form['name']

    # Save search to history if the user is logged in
    if 'username' in session:
        save_search(session['username'], movie)

    # Get movie recommendations
    rc = rcmd(movie)

    if isinstance(rc, str):
        return rc  # If no recommendations, return the error message
    else:
        return "---".join(rc)  # Return the recommended movies joined by '---'


# Helper function to fetch and scrape reviews
def get_reviews(imdb_id):
    reviews_list = []
    reviews_status = []
    try:
        url = f'https://www.imdb.com/title/{imdb_id}/reviews?ref_=tt_ov_rt'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
        req = urllib.request.Request(url, headers=headers)
        sauce = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(sauce, 'lxml')
        soup_result = soup.find_all("h3", {"class": "ipc-title__text"})
        reviews_list = [review.get_text() for review in soup_result]

        # Sentiment Analysis
        for review in reviews_list:
            movie_review_list = np.array([review])
            movie_vector = vectorizer.transform(movie_review_list)
            pred = clf.predict(movie_vector)
            reviews_status.append('Good' if pred else 'Bad')
    except Exception as e:
        print("Error in scraping or sentiment analysis:", e)

    return list(zip(reviews_list, reviews_status))


# Route to display movie recommendations with details
@app.route("/recommend", methods=["POST"])
def recommend():
    # Extract movie and cast information
    title = request.form['title']
    cast_ids = request.form['cast_ids']
    cast_names = request.form['cast_names']
    cast_chars = request.form['cast_chars']
    cast_bdays = request.form['cast_bdays']
    cast_bios = request.form['cast_bios']
    cast_places = request.form['cast_places']
    cast_profiles = request.form['cast_profiles']
    imdb_id = request.form['imdb_id']
    poster = request.form['poster']
    genres = request.form['genres']
    overview = request.form['overview']
    vote_average = request.form['rating']
    vote_count = request.form['vote_count']
    release_date = request.form['release_date']
    runtime = request.form['runtime']
    status = request.form['status']
    rec_movies = request.form['rec_movies']
    rec_posters = request.form['rec_posters']

    suggestions = get_suggestions()

    rec_movies = convert_to_list(rec_movies)
    rec_posters = convert_to_list(rec_posters)
    cast_names = convert_to_list(cast_names)
    cast_chars = convert_to_list(cast_chars)
    cast_profiles = convert_to_list(cast_profiles)
    cast_bdays = convert_to_list(cast_bdays)
    cast_bios = convert_to_list(cast_bios)
    cast_places = convert_to_list(cast_places)
    cast_ids = [item.strip() for item in cast_ids.strip('[]').split(',')]

    cast_bios = [bio.replace(r'\n', '\n').replace(r'\"', '\"') for bio in cast_bios]

    movie_cards = {rec_posters[i]: rec_movies[i] for i in range(len(rec_posters))}
    casts = {cast_names[i]: [cast_ids[i], cast_chars[i], cast_profiles[i]] for i in range(len(cast_profiles))}
    cast_details = {cast_names[i]: [cast_ids[i], cast_profiles[i], cast_bdays[i], cast_places[i], cast_bios[i]]
                    for i in range(len(cast_places))}

    # Fetch reviews and sentiment analysis
    movie_reviews = get_reviews(imdb_id)

    return render_template(
        'recommend.html',
        title=title,
        poster=poster,
        overview=overview,
        vote_average=vote_average,
        vote_count=vote_count,
        release_date=release_date,
        runtime=runtime,
        status=status,
        genres=genres,
        movie_cards=movie_cards,
        reviews=movie_reviews,
        casts=casts,
        cast_details=cast_details,
    )


if __name__ == '__main__':
    app.run(debug=True)
