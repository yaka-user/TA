from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime
from zoneinfo import ZoneInfo

db = SQLAlchemy()

follows = db.Table(
    'follows',
    db.Column('follower_id', db.String(255), db.ForeignKey('users.id', onupdate='CASCADE'), primary_key=True),
    db.Column('followee_id', db.String(255), db.ForeignKey('users.id', onupdate='CASCADE'), primary_key=True)
)

task_shares = db.Table(
    'task_shares',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('user_id', db.String(255), db.ForeignKey('users.id', onupdate='CASCADE'), primary_key=True)
)

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.id', onupdate='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    deadline = db.Column(db.DateTime(timezone=True), nullable=False)
    is_shared = db.Column(db.Boolean, nullable=False, default=False)

    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(ZoneInfo("Asia/Tokyo")))

    shared_with = db.relationship(
        'User',
        secondary='task_shares',
        backref=db.backref('shared_tasks', lazy='dynamic')
    )

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.String(255), primary_key=True)
    password_hash = db.Column(db.String(162), nullable=False)
    lastname = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(255), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True)
    followees = db.relationship(
        'User',
        secondary=follows,
        primaryjoin=(follows.c.follower_id == id),
        secondaryjoin=(follows.c.followee_id == id),
        backref=db.backref('followers'),
        lazy=True
    )
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def password(self):
        message = "パスワードは読めません"
        raise AttributeError(message)
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)