from dotenv import load_dotenv

import os


load_dotenv()


database_password = os.getenv("DATABASE_PASSWORD")

class Config(object):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    secret_key = os.getenv("secret_key")
    UPLOAD_EXTENSIONS = ["jpg", "png", "gif", "ai", "tiff", "psd", "esp", "svg", "pdf", "jpeg"]
    UPLOAD_PATH = "uploaded_images"
    SQLALCHEMY_DATABASE_URI = f"mysql://root:{database_password}@localhost:3306/blog"
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]


class DevelopmentConfig(Config):
    DEBUG = True



class ProductionConfig(Config):
    pass



class TestingConfig(Config):
    TESTING = True