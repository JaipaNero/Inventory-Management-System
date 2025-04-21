"""
Utility functions for managing inventory transactions.
"""
from sqlalchemy import func
from flask import current_app
from app.models.db import db, TransactionType
from app.models.transaction import Transaction
from app.models.inventory import Inventory
from app.utils.auth import log_security_event
from datetime import datetime

def generate_ticket_number():
    """
    Generate a unique 10-digit ticket number starting with '33'.
    Format: 33XXXXXXXX where X is a digit
    """
    # Find the maximum existing ticket number that starts with '33'
    max_query = db.session.query(
        func.max(
            func.cast(
                func.substr(Transaction.ticket_number, 3),
                db.Integer
            )
        )
    ).filter(Transaction.ticket_number.like('33%'))
    
    max_number = max_query.scalar()
    
    # If no tickets exist yet, start with 1
    if max_number is None:
        max_number = 0
        
    # Generate the new ticket number
    new_number = max_number + 1
    ticket_number = f'33{new_number:08d}'
    
    return ticket_number

def create_transaction(item_id, user_id, store_id, transaction_type, quantity_change, notes=None):
    """
    Create a new transaction record.
    
    Args:
        item_id (int): ID of the inventory item
        user_id (int): ID of the user creating the transaction
        store_id (int): ID of the store where the transaction occurs
        transaction_type (TransactionType): Type of transaction
        quantity_change (int): Change in quantity (positive for additions, negative for removals)
        notes (str, optional): Additional notes about the transaction
        
    Returns:
        Transaction: The created transaction record
    """
    # Generate a unique ticket number
    ticket_number = generate_ticket_number()
    
    # Create the transaction record
    transaction = Transaction(
        ticket_number=ticket_number,
        item_id=item_id,
        user_id=user_id,
        store_id=store_id,
        transaction_type=transaction_type,
        quantity_change=quantity_change,
        timestamp=datetime.utcnow(),
        notes=notes
    )
    
    db.session.add(transaction)
    
    # Update the inventory item quantity
    item = Inventory.query.get(item_id)
    if item:
        item.quantity += quantity_change
        
        # Log the transaction
        log_security_event(
            'inventory_transaction', 
            f"{transaction_type.value} transaction: {ticket_number} - Item: {item.part_number} - Qty: {quantity_change}"
        )
    
    db.session.commit()
    
    return transaction

def register_outgoing_accessory(item_id, user_id, store_id, notes=None):
    """
    Register an outgoing accessory item with quantity 1.
    Specifically for use by regular users.
    
    Args:
        item_id (int): ID of the inventory item
        user_id (int): ID of the user registering the transaction
        store_id (int): ID of the store
        notes (str, optional): Additional notes for the transaction
        
    Returns:
        tuple: (success, message, transaction_data)
            success (bool): Whether the transaction was successful
            message (str): Success or error message
            transaction_data (dict): Transaction details if successful, None otherwise
    """
    # Verify the item exists and is an accessory
    item = Inventory.query.get(item_id)
    
    if not item:
        return False, "Item not found", None
        
    if item.item_type.value != 'accessories':
        return False, "Only accessories can be registered through this function", None
        
    if item.store_id != store_id:
        return False, "Item not found in the selected store", None
        
    if item.quantity <= 0:
        return False, "Item is out of stock", None
    
    # Create the outgoing transaction with quantity fixed at -1
    try:
        transaction = create_transaction(
            item_id=item_id,
            user_id=user_id,
            store_id=store_id,
            transaction_type=TransactionType.REMOVE,
            quantity_change=-1,
            notes=notes if notes else "User-registered outgoing accessory"
        )
        
        # Return the transaction details
        transaction_data = {
            'ticket_number': transaction.ticket_number,
            'item_name': item.name,
            'part_number': item.part_number,
            'timestamp': transaction.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return True, "Item registered successfully", transaction_data
        
    except Exception as e:
        current_app.logger.error(f"Error registering outgoing accessory: {str(e)}")
        db.session.rollback()
        return False, "An error occurred while registering the item", None