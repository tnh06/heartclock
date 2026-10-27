from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    """Current UTC time as a naive datetime. Every time in the database is stored this way."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Couple(db.Model):
    """Two people who share one timeline. A partner joins using the invite code."""
    __tablename__ = 'couple'

    id = db.Column(db.Integer, primary_key=True)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey('couple.id'), nullable=True)

    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)


class DateEntry(db.Model):
    """One date. Clocked dates always have times, and dates added by hand can have them too."""
    __tablename__ = 'date_entry'

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey('couple.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # empty if the author deleted their account

    title = db.Column(db.String(200))
    date = db.Column(db.Date)
    notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    author = db.relationship('User', foreign_keys=[author_id])
    photos = db.relationship('Photo', back_populates='entry',
                             cascade='all, delete-orphan', order_by='Photo.id')


class ActiveSession(db.Model):
    """A date that is running right now. It is deleted when the couple clocks out."""
    __tablename__ = 'active_session'

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey('couple.id'), nullable=False)

    started_at = db.Column(db.DateTime, default=utc_now)


class Photo(db.Model):
    """One uploaded photo. The file itself lives in instance/uploads/."""
    __tablename__ = 'photo'

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('date_entry.id'), nullable=False)

    filename = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    entry = db.relationship('DateEntry', back_populates='photos')