import os
from flask import Flask
from app.database import init_db
from app.seed_data import seed_database
from app.routes.views import views_bp
from app.routes.api import api_bp

def create_app():
    # Base directories for templates and static files
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    static_dir = os.path.join(os.path.dirname(__file__), 'static')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'warehouse-spark-secret-key-2026-xyz')
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB max upload

    # Ensure database initialized and seeded
    init_db()
    seed_database(reset=False)

    # Register Blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)

    return app
