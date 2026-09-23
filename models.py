from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Couple(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    couple_id = db.Column(db.Integer, db.ForeignKey('couple.id'), nullable=True)

class DateEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey('couple.id'), nullable=False)
    title = db.Column(db.String(200))
    date = db.Column(db.Date)
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    photo_path = db.Column(db.String(300), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)

class ActiveSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey('couple.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)