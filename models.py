from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_verified   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)

    guardians      = db.relationship('Guardian',       backref='user', lazy='dynamic',
                                     cascade='all, delete-orphan')
    reports        = db.relationship('IncidentReport', backref='reporter', lazy='dynamic',
                                     cascade='all, delete-orphan')
    active_traveler = db.relationship('ActiveTraveler', backref='user', uselist=False,
                                      cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'


class Guardian(db.Model):
    __tablename__ = 'guardians'

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                                nullable=False, index=True)
    guardian_email = db.Column(db.String(120), nullable=False)
    name           = db.Column(db.String(80))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'guardian_email', name='uq_guardian_email'),
    )


class IncidentReport(db.Model):
    __tablename__ = 'incident_reports'

    id          = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                             nullable=True, index=True)
    latitude    = db.Column(db.Float, nullable=False)
    longitude   = db.Column(db.Float, nullable=False)
    report_type = db.Column(db.String(50), nullable=False)   # enum-like
    description = db.Column(db.String(1000), default='')
    severity    = db.Column(db.Integer, default=1)           # 1-5
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved    = db.Column(db.Boolean, default=False)

    VALID_TYPES = {
        'harassment', 'stalking', 'poor_lighting',
        'drunk_groups', 'suspicious', 'other',
    }

    def to_dict(self):
        return {
            'id':          self.id,
            'lat':         self.latitude,
            'lng':         self.longitude,
            'type':        self.report_type,
            'severity':    self.severity,
            'description': self.description,
            'timestamp':   self.timestamp.isoformat(),
            'resolved':    self.resolved,
        }


class ActiveTraveler(db.Model):
    __tablename__ = 'active_travelers'

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                                  unique=True, nullable=False, index=True)
    latitude         = db.Column(db.Float, nullable=False)
    longitude        = db.Column(db.Float, nullable=False)
    route_nodes_json = db.Column(db.Text, default='[]')
    route_id         = db.Column(db.String(100))
    start_time       = db.Column(db.DateTime, default=datetime.utcnow)
    last_update      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def route_nodes(self):
        try:
            return json.loads(self.route_nodes_json or '[]')
        except (ValueError, TypeError):
            return []

    @route_nodes.setter
    def route_nodes(self, value):
        self.route_nodes_json = json.dumps(value)


class EdgeSafety(db.Model):
    __tablename__ = 'edge_safety'

    id           = db.Column(db.Integer, primary_key=True)
    edge_key     = db.Column(db.String(80), unique=True, nullable=False, index=True)
    safety_score = db.Column(db.Float, default=50.0)
    confidence   = db.Column(db.Float, default=0.0)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow,
                              onupdate=datetime.utcnow)
