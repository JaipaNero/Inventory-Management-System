from datetime import datetime
from app.models.db import db

class Store(db.Model):
    __tablename__ = 'stores'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    location = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    inventory_items = db.relationship('Inventory', backref='store', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='store', lazy='dynamic')
    
    def __repr__(self):
        return f'<Store {self.name}>'