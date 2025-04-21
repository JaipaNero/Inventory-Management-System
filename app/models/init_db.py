"""
Database initialization utilities for the inventory application.
This module provides functions for initializing and seeding the database.
"""

from app.models.db import db, UserRole, ItemType, TransactionType
from app.models.user import User, PasswordHistory
from app.models.store import Store 
from app.models.inventory import Inventory
from app.models.transaction import Transaction
from app.models.security_log import SecurityLog
from datetime import datetime, timedelta
import random

def init_database():
    """Initialize the database by creating all tables."""
    db.create_all()
    print("Initialized the database tables.")

def seed_database():
    """Seed the database with initial test data."""
    print("Seeding the database with test data...")
    
    # Clear existing data
    SecurityLog.query.delete()
    Transaction.query.delete()
    Inventory.query.delete()
    PasswordHistory.query.delete()
    User.query.delete()
    Store.query.delete()
    db.session.commit()
    
    # Create users with different roles
    users = {
        'admin': User(username='admin', role=UserRole.ADMIN_GLOBAL),
        'partner_admin': User(username='partner_admin', role=UserRole.PARTNER_ADMIN),
        'user1': User(username='user1', role=UserRole.USER),
        'user2': User(username='user2', role=UserRole.USER),
        'user3': User(username='user3', role=UserRole.USER),
        'user4': User(username='user4', role=UserRole.USER),
    }
    
    # Set passwords for all users (in a real app, use strong passwords)
    for user in users.values():
        user.password_hash = 'placeholder'  # Will be set properly below
        db.session.add(user)
    
    # Flush to generate IDs
    db.session.flush()
    
    # Set actual passwords
    users['admin'].set_password('admin123')
    users['partner_admin'].set_password('partner123')
    users['user1'].set_password('user123')
    users['user2'].set_password('user123')
    users['user3'].set_password('user123')
    users['user4'].set_password('user123')
    
    # Create stores
    stores = {
        'main': Store(name='Main Warehouse', location='123 Main St, Anytown, USA'),
        'downtown': Store(name='Downtown Store', location='456 Central Ave, Anytown, USA'),
        'mall': Store(name='Shopping Mall Branch', location='789 Mall Blvd, Anytown, USA'),
        'outlet': Store(name='Outlet Center', location='321 Discount Way, Anytown, USA'),
    }
    
    for store in stores.values():
        db.session.add(store)
    
    # Flush to generate IDs
    db.session.flush()
    
    # Assign users to stores
    users['user1'].stores.append(stores['main'])
    users['user2'].stores.append(stores['downtown'])
    users['user3'].stores.append(stores['mall'])
    users['user3'].stores.append(stores['outlet'])  # One user with multiple stores
    users['user4'].stores.append(stores['outlet'])
    users['partner_admin'].stores.append(stores['main'])
    users['partner_admin'].stores.append(stores['downtown'])
    # Note: admin_global doesn't need explicit store assignments as they can access all
    
    # Create inventory items
    inventory_items = []
    
    # Accessories items
    accessories = [
        ('ACC-001', 'Premium Headphones', 'Noise-canceling over-ear headphones', ItemType.ACCESSORIES, 25, stores['main']),
        ('ACC-002', 'Wireless Mouse', 'Ergonomic wireless mouse', ItemType.ACCESSORIES, 30, stores['main']),
        ('ACC-003', 'USB-C Cable', 'Fast charging USB-C cable, 6ft', ItemType.ACCESSORIES, 50, stores['downtown']),
        ('ACC-004', 'Phone Holder', 'Adjustable desk phone holder', ItemType.ACCESSORIES, 15, stores['mall']),
        ('ACC-005', 'Laptop Sleeve', 'Protective 15-inch laptop sleeve', ItemType.ACCESSORIES, 20, stores['outlet']),
        ('ACC-006', 'Wireless Earbuds', 'True wireless earbuds with charging case', ItemType.ACCESSORIES, 40, stores['main']),
        ('ACC-007', 'Power Bank', '10,000mAh fast-charging power bank', ItemType.ACCESSORIES, 35, stores['downtown']),
        ('ACC-008', 'Screen Protector', 'Tempered glass screen protector', ItemType.ACCESSORIES, 100, stores['mall']),
    ]
    
    # Clothing items
    clothing = [
        ('CLO-001', 'Company T-shirt S', 'Small company logo t-shirt', ItemType.CLOTHING, 20, stores['main']),
        ('CLO-002', 'Company T-shirt M', 'Medium company logo t-shirt', ItemType.CLOTHING, 25, stores['main']),
        ('CLO-003', 'Company T-shirt L', 'Large company logo t-shirt', ItemType.CLOTHING, 25, stores['downtown']),
        ('CLO-004', 'Company T-shirt XL', 'Extra large company logo t-shirt', ItemType.CLOTHING, 15, stores['mall']),
        ('CLO-005', 'Company Hoodie S', 'Small company logo hoodie', ItemType.CLOTHING, 10, stores['outlet']),
        ('CLO-006', 'Company Hoodie M', 'Medium company logo hoodie', ItemType.CLOTHING, 15, stores['main']),
        ('CLO-007', 'Company Hoodie L', 'Large company logo hoodie', ItemType.CLOTHING, 15, stores['downtown']),
        ('CLO-008', 'Company Hoodie XL', 'Extra large company logo hoodie', ItemType.CLOTHING, 10, stores['mall']),
    ]
    
    # Add all inventory items
    for part_num, name, desc, item_type, qty, store in accessories + clothing:
        item = Inventory(
            part_number=part_num,
            name=name,
            description=desc,
            item_type=item_type,
            quantity=qty,
            store=store
        )
        inventory_items.append(item)
        db.session.add(item)
    
    db.session.flush()
    
    # Generate transactions for inventory items
    transactions = []
    
    # Initial stock transactions (sample only a few items)
    for i, item in enumerate(random.sample(inventory_items, 6)):
        # Create an initial "add" transaction to represent stocking
        trans = Transaction(
            ticket_number=f'INIT-{i+1:04d}',
            item=item,
            user=users['admin'],
            store=item.store,
            transaction_type=TransactionType.ADD,
            quantity_change=item.quantity,
            timestamp=datetime.utcnow() - timedelta(days=random.randint(10, 30)),
            notes='Initial inventory stocking'
        )
        transactions.append(trans)
        db.session.add(trans)
    
    # Some random transactions (add, remove, etc.)
    transaction_types = [
        TransactionType.ADD,
        TransactionType.REMOVE,
        TransactionType.STOCK_ADJUSTMENT
    ]
    
    for i in range(10):
        item = random.choice(inventory_items)
        t_type = random.choice(transaction_types)
        
        # Determine quantity change based on transaction type
        if t_type == TransactionType.ADD:
            qty_change = random.randint(1, 10)
        elif t_type == TransactionType.REMOVE:
            qty_change = -random.randint(1, min(5, item.quantity))  # Don't remove more than available
        else:  # STOCK_ADJUSTMENT
            qty_change = random.randint(-3, 5)  # Could be positive or negative adjustment
        
        # Skip if it would make quantity negative
        if item.quantity + qty_change < 0:
            continue
            
        # Create the transaction
        trans = Transaction(
            ticket_number=f'TRANS-{i+1:04d}',
            item=item,
            user=random.choice(list(users.values())),
            store=item.store,
            transaction_type=t_type,
            quantity_change=qty_change,
            timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 9)),
            notes=f'Random {t_type.value} transaction'
        )
        transactions.append(trans)
        db.session.add(trans)
        
        # Update item quantity
        item.quantity += qty_change
    
    # Add a few transfer transactions between stores
    for i in range(3):
        # Pick two different stores
        stores_list = list(stores.values())
        source_store = random.choice(stores_list)
        dest_store = random.choice([s for s in stores_list if s != source_store])
        
        # Find items in source store
        source_items = [item for item in inventory_items if item.store_id == source_store.id and item.quantity > 0]
        
        if source_items:
            item = random.choice(source_items)
            transfer_qty = random.randint(1, min(3, item.quantity))
            
            # Create transfer out transaction
            trans_out = Transaction(
                ticket_number=f'TROUT-{i+1:04d}',
                item=item,
                user=users['admin'],
                store=source_store,
                transaction_type=TransactionType.TRANSFER_OUT,
                quantity_change=-transfer_qty,
                timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 5)),
                notes=f'Transfer to {dest_store.name}'
            )
            db.session.add(trans_out)
            
            # Create transfer in transaction
            trans_in = Transaction(
                ticket_number=f'TRIN-{i+1:04d}',
                item=item,
                user=users['admin'],
                store=dest_store,
                transaction_type=TransactionType.TRANSFER_IN,
                quantity_change=transfer_qty,
                timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 5)),
                notes=f'Transfer from {source_store.name}'
            )
            db.session.add(trans_in)
            
            # Update item quantity in source store
            item.quantity -= transfer_qty
    
    # Create security log entries
    security_events = [
        'login_success', 'login_failure', 'password_change',
        'inventory_update', 'user_creation', 'role_change'
    ]
    
    for i in range(20):
        event = random.choice(security_events)
        user = random.choice(list(users.values()) + [None])  # Sometimes no user (anonymous event)
        
        log = SecurityLog(
            user_id=user.id if user else None,
            ip_address=f'192.168.1.{random.randint(1, 254)}',
            event_type=event,
            description=f'Sample security event: {event}',
            timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 30), 
                                                    hours=random.randint(0, 23))
        )
        db.session.add(log)
    
    # Commit all changes
    db.session.commit()
    print("Database seeded with test data successfully!")