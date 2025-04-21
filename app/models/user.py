from datetime import datetime
from flask_login import UserMixin
from app.models.db import db, UserRole
from werkzeug.security import generate_password_hash, check_password_hash
import sqlalchemy as sa

# Association table for User-Store many-to-many relationship
user_stores = db.Table('user_stores',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('store_id', db.Integer, db.ForeignKey('stores.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    # Modified: Use String type with direct enum values instead of SQLAlchemy's Enum type
    _role = db.Column('role', db.String(20), nullable=False, default=UserRole.USER.value)
    failed_login_attempts = db.Column(db.Integer, default=0)
    last_login_attempt_time = db.Column(db.DateTime, nullable=True)
    is_locked = db.Column(db.Boolean, default=False)
    password_last_changed = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    password_history = db.relationship('PasswordHistory', backref='user', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic')
    security_logs = db.relationship('SecurityLog', backref='user', lazy='dynamic')
    
    # Many-to-many relationship with stores
    stores = db.relationship('Store', 
                            secondary=user_stores,
                            lazy='subquery',
                            backref=db.backref('users', lazy=True))
    
    # Property getter for role - converts string to enum
    @property
    def role(self):
        # Find the matching enum by value
        for role_enum in UserRole:
            if role_enum.value == self._role:
                return role_enum
        return None
        
    # Property setter for role - converts enum to string
    @role.setter
    def role(self, value):
        if isinstance(value, UserRole):
            self._role = value.value
        elif isinstance(value, str):
            # Validate that the string is a valid enum value
            valid_values = [r.value for r in UserRole]
            if value in valid_values:
                self._role = value
            else:
                raise ValueError(f"Invalid role value: {value}. Valid values: {valid_values}")
        else:
            raise TypeError(f"Expected UserRole enum or string, got {type(value)}")
    
    def set_password(self, password):
        """Set the user's password hash and record it in the password history."""
        self.password_hash = generate_password_hash(password)
        self.password_last_changed = datetime.utcnow()
        
        # Only add to password history if the user already exists in the database (has an ID)
        # For new users, the history will be created after the user is committed to the database
        if self.id is not None:
            history_entry = PasswordHistory(user_id=self.id, password_hash=self.password_hash)
            db.session.add(history_entry)
    
    def check_password(self, password):
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class PasswordHistory(db.Model):
    __tablename__ = 'password_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_same_password(self, password):
        """Check if the provided password matches this history entry."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<PasswordHistory user_id={self.user_id} timestamp={self.timestamp}>'