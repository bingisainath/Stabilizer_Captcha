"""
Reactor Stabilizer - Application Entry Point

This is the main entry point for running the Flask application.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=app.config['DEBUG']
    )