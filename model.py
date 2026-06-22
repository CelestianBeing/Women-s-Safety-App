from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)  # for "verified traveler"
    guardians = db.relationship('Guardian', backref='user', lazy=True)

class Guardian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    guardian_email = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80))

class IncidentReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    report_type = db.Column(db.String(50))  # harassment, stalking, poor_lighting, drunk_groups, suspicious, other
    description = db.Column(db.String(500))
    severity = db.Column(db.Integer, default=1)  # 1-5
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)

class ActiveTraveler(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    route_nodes_json = db.Column(db.Text)  # JSON list of OSM node IDs
    route_id = db.Column(db.String(100))
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_update = db.Column(db.DateTime, default=datetime.utcnow)

class EdgeSafety(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edge_key = db.Column(db.String(50), unique=True)  # "u-v-key"
    safety_score = db.Column(db.Float, default=50)
    confidence = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)