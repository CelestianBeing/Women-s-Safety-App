import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///safety.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OSMNX_CACHE_FOLDER = 'data'
    GRAPH_FILE = os.path.join(OSMNX_CACHE_FOLDER, 'graph.pkl')
    MODEL_FILE = os.path.join(OSMNX_CACHE_FOLDER, 'risk_model.joblib')
    # Sample area: Connaught Place, New Delhi
    PLACE_NAME = "Connaught Place, New Delhi, India"
    # Map center for frontend
    MAP_CENTER = [28.6304, 77.2177]
    MAP_ZOOM = 15