"""Flask application factory and configuration."""

import os
import logging
from flask import Flask
from datetime import timedelta


def create_app(config_name=None):
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    from .config import config
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    if config_name == 'production' and not os.environ.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY environment variable must be set in production")
    
    setup_logging(app)
    
    from .routes import main_bp
    app.register_blueprint(main_bp)
    
    app.logger.info(f"Reactor Stabilizer starting in {config_name} mode")
    app.logger.info(f"Secret key configured: {'Yes' if app.config['SECRET_KEY'] else 'No'}")
    
    return app


def setup_logging(app):
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'app.log')
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    ))
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(levelname)s: %(message)s'
    ))
    
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    
    if app.config['ENV'] == 'production':
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)