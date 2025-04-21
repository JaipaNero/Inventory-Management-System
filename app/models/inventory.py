from datetime import datetime
from app.models.db import db, ItemType
import sqlalchemy as sa

class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    item_type = db.Column(sa.Enum(ItemType), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='item', lazy='dynamic')
    
    def __repr__(self):
        return f'<Inventory {self.part_number} - {self.name}>'