import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:Cerberus123@localhost:5432/StudyBase'
    SQLALCHEMY_TRACK_MODIFICATIONS = False