"""
Configuration management with environment-based configs
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration - common settings for all environments"""
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///price_monitor.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    # Price check settings
    PRICE_CHECK_INTERVAL_HOURS = int(os.environ.get('PRICE_CHECK_INTERVAL_MINUTES', 1))
    PRICE_CHECK_INTERVAL_SECONDS = PRICE_CHECK_INTERVAL_HOURS * 0

    # Alert settings
    ALERT_THRESHOLD_PERCENT = int(os.environ.get('ALERT_THRESHOLD_PERCENT', 10))

    # Mock price settings (for development)
    MOCK_PRICE_MIN_FLUCTUATION = float(os.environ.get('MOCK_PRICE_MIN_FLUCTUATION', 0.8))
    MOCK_PRICE_MAX_FLUCTUATION = float(os.environ.get('MOCK_PRICE_MAX_FLUCTUATION', 1.2))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

    # More verbose logging in development
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True

    # Use in-memory SQLite for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # Disable pool settings for testing
    SQLALCHEMY_ENGINE_OPTIONS = {}

    # Shorter check interval for testing
    PRICE_CHECK_INTERVAL_HOURS = 0.0167  # ~1 minute
    PRICE_CHECK_INTERVAL_SECONDS = 60


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

    # More secure settings for production
    PREFERRED_URL_SCHEME = 'https'
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    # Less verbose logging in production
    LOG_LEVEL = 'WARNING'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get the current configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])