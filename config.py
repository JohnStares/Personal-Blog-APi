from dotenv import load_dotenv

import os


load_dotenv()

class Config(object):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    secret_key = os.getenv("secret_key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///blog.db"
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]


class DevelopmentConfig(Config):
    DEBUG = True



class ProductionConfig(Config):
    pass



class TestingConfig(Config):
    TESTING = True