from flask import Flask
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from config import DevelopmentConfig
from .models import db


migrate = Migrate()
jwt = JWTManager()


def create_blog():
    bg_app = Flask(__name__)
    bg_app.config.from_object(DevelopmentConfig())
    CORS(bg_app)

    db.init_app(bg_app)
    migrate.init_app(bg_app, db)
    jwt.init_app(bg_app)

    from .routes import bp
    bg_app.register_blueprint(bp, url_prefix='/v1')

    with bg_app.app_context():
        db.create_all()
    return bg_app