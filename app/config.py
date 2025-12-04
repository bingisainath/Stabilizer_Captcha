"""Configuration management for different environments."""

import os
import secrets
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('SESSION_TIMEOUT', 600))
    )
    
    MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', 3))
    FRAME_COUNT = 300
    PASS_FRAME_THRESHOLD = 280
    SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', 600))
    
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


class DevelopmentConfig(Config):
    ENV = 'development'
    DEBUG = True
    TESTING = False
    
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    ENV = 'production'
    DEBUG = False
    TESTING = False
    
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True


class TestingConfig(Config):
    ENV = 'testing'
    DEBUG = True
    TESTING = True
    
    SESSION_TIMEOUT = 60
    MAX_ATTEMPTS = 3


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}