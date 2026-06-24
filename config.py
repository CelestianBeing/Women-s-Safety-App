import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # ── Security ────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'CHANGE-ME-IN-PRODUCTION-USE-RANDOM-256-BIT'
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # ── Database ─────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'safety.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ── Email (SOS alerts) ───────────────────────────────────────────────────
    MAIL_SERVER   = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_FROM     = os.environ.get('MAIL_FROM', 'noreply@safetyroute.app')

    # ── OSM / Graph ──────────────────────────────────────────────────────────
    DATA_DIR   = os.path.join(BASE_DIR, 'data')
    GRAPH_FILE = os.path.join(DATA_DIR, 'graph.graphml')
    MODEL_FILE = os.path.join(DATA_DIR, 'risk_model.joblib')

    # Default area — override with PLACE_NAME env var
    PLACE_NAME = os.environ.get('PLACE_NAME', 'Connaught Place, New Delhi, India')
    MAP_CENTER = [28.6304, 77.2177]
    MAP_ZOOM   = 15

    # ── Rate limiting & pagination ───────────────────────────────────────────
    REPORTS_PER_USER_PER_HOUR = 10
    MAX_INCIDENT_REPORTS_PAGE = 50

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE  = os.path.join(BASE_DIR, 'logs', 'app.log')


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
