import uuid
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # 'admin' or 'employee'
    folder_id = db.Column(db.String(100), nullable=True)  # Only employees need folders
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, nullable=True)
    password_reset_token = db.Column(db.String(100), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    
    # Relationships - explicitly specify foreign keys
    reports = db.relationship('Report', 
                             foreign_keys='Report.employee_id',
                             backref='user',
                             lazy=True, 
                             cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<User {self.name}>'
    
    def is_admin(self):
        return self.role == 'admin'

class Employee(object):
    """Legacy compatibility model"""
    @classmethod
    def query(cls):
        return User.query.filter_by(role='employee')
    
    @classmethod
    def get(cls, user_id):
        return User.query.get(user_id)
    
    @classmethod
    def get_employees(cls):
        return User.query.filter_by(role='employee').all()

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    submission_date = db.Column(db.DateTime, default=datetime.now)
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='submitted')  # 'submitted', 'approved', 'rejected'
    feedback = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    reviewer = db.relationship('User', 
                              foreign_keys=[reviewed_by],
                              backref='reviewed_reports',
                              lazy=True)
    
    def __repr__(self):
        return f'<Report {self.filename}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info')  # 'info', 'warning', 'success', 'danger'
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications', lazy=True)
    
    def __repr__(self):
        return f'<Notification {self.id}>'

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    ip_address = db.Column(db.String(45), nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='activities', lazy=True)
    
    def __repr__(self):
        return f'<ActivityLog {self.action}>'