from flask import Flask
from flask_cors import CORS
from app.models import db
from app.config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app)
    
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Register API blueprints (routes)
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    return app