from flask import render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app.blueprints.admin import admin_bp
from app.models.db import db, UserRole
from app.models.store import Store
from app.models.user import User
from app.models.security_log import SecurityLog
from app.models.inventory import Inventory
from app.models.transaction import Transaction
from app.utils.auth import admin_required, partner_admin_required, log_security_event
from sqlalchemy import func, desc
from datetime import datetime, timedelta

@admin_bp.route('/')
@login_required
@admin_required
def index():
    """Admin dashboard route."""
    return render_template('admin/index.html', title='Admin Dashboard')

@admin_bp.route('/stores')
@login_required
@admin_required
def stores():
    """Manage stores route."""
    stores_list = Store.query.all()
    return render_template('admin/stores.html', title='Manage Stores', stores=stores_list)

@admin_bp.route('/stores/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_store():
    """Add a new store route."""
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        
        if not name:
            flash('Store name is required.', 'danger')
            return redirect(url_for('admin.add_store'))
        
        # Check if store name already exists
        existing_store = Store.query.filter_by(name=name).first()
        if existing_store:
            flash('A store with this name already exists.', 'danger')
            return redirect(url_for('admin.add_store'))
        
        store = Store(name=name, location=location)
        db.session.add(store)
        db.session.commit()
        
        log_security_event(
            'store_created',
            f"Admin created new store: {name}"
        )
        
        flash(f'Store {name} has been added successfully.', 'success')
        return redirect(url_for('admin.stores'))
    
    return render_template('admin/add_store.html', title='Add Store')

@admin_bp.route('/stores/<int:store_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_store(store_id):
    """Edit an existing store route."""
    store = Store.query.get_or_404(store_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        
        if not name:
            flash('Store name is required.', 'danger')
            return redirect(url_for('admin.edit_store', store_id=store_id))
        
        # Check if store name already exists (excluding current store)
        existing_store = Store.query.filter(Store.name == name, Store.id != store_id).first()
        if existing_store:
            flash('A store with this name already exists.', 'danger')
            return redirect(url_for('admin.edit_store', store_id=store_id))
        
        # Track changes for logging
        changes = []
        if store.name != name:
            changes.append(f"Name: {store.name} -> {name}")
        if store.location != location:
            changes.append(f"Location: {store.location} -> {location}")
        
        # Update store
        store.name = name
        store.location = location
        db.session.commit()
        
        if changes:
            log_security_event(
                'store_updated',
                f"Admin updated store: {store.name} - Changes: {', '.join(changes)}"
            )
        
        flash(f'Store {store.name} has been updated.', 'success')
        return redirect(url_for('admin.stores'))
    
    return render_template('admin/edit_store.html', title='Edit Store', store=store)

@admin_bp.route('/stores/<int:store_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_store(store_id):
    """Delete a store route."""
    store = Store.query.get_or_404(store_id)
    
    # Check if store has inventory items
    inventory_count = Inventory.query.filter_by(store_id=store_id).count()
    if inventory_count > 0:
        flash(f'Cannot delete store with {inventory_count} inventory items. Transfer or delete items first.', 'danger')
        return redirect(url_for('admin.stores'))
    
    # Store name for logging
    store_name = store.name
    
    # Delete store
    db.session.delete(store)
    db.session.commit()
    
    log_security_event(
        'store_deleted',
        f"Admin deleted store: {store_name}"
    )
    
    flash(f'Store {store_name} has been deleted.', 'success')
    return redirect(url_for('admin.stores'))

@admin_bp.route('/security-logs')
@login_required
@admin_required
def security_logs():
    """View security logs route."""
    # Get filter parameters
    event_type = request.args.get('event_type')
    user_id = request.args.get('user_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Base query
    query = SecurityLog.query
    
    # Apply filters
    if event_type:
        query = query.filter_by(event_type=event_type)
    if user_id and user_id.isdigit():
        query = query.filter_by(user_id=int(user_id))
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(SecurityLog.timestamp >= date_from_obj)
        except ValueError:
            flash('Invalid date format for From Date.', 'warning')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Include the entire day
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(SecurityLog.timestamp < date_to_obj)
        except ValueError:
            flash('Invalid date format for To Date.', 'warning')
    
    # Order by timestamp descending
    logs = query.order_by(SecurityLog.timestamp.desc()).paginate(
        page=request.args.get('page', 1, type=int), 
        per_page=50,
        error_out=False
    )
    
    # Get unique event types for filter dropdown
    event_types = db.session.query(SecurityLog.event_type).distinct().all()
    event_types = [et[0] for et in event_types]
    
    # Get users for filter dropdown
    users = User.query.all()
    
    return render_template(
        'admin/security_logs.html',
        title='Security Logs',
        logs=logs,
        event_types=event_types,
        users=users,
        selected_event_type=event_type,
        selected_user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        max=max,  # Add built-in max function to the template context
        min=min   # Add built-in min function to the template context
    )

@admin_bp.route('/reports/inventory')
@login_required
@partner_admin_required
def inventory_report():
    """Inventory report route."""
    # Get parameters
    store_id = request.args.get('store_id', type=int)
    item_type = request.args.get('item_type')
    
    # Base query
    query = Inventory.query
    
    # Apply filters
    if store_id:
        query = query.filter_by(store_id=store_id)
    if item_type:
        query = query.filter_by(item_type=item_type)
    
    # Filter by accessories for non-global admins
    if current_user.role == UserRole.PARTNER_ADMIN:
        query = query.filter_by(item_type='accessories')
    
    # Get inventory items
    inventory_items = query.order_by(Inventory.part_number).all()
    
    # Get stores for filter
    stores = Store.query.all()
    
    # Item types available for filter (only for admin_global)
    item_types = []
    if current_user.role == UserRole.ADMIN_GLOBAL:
        from app.models.db import ItemType
        item_types = [(t.value, t.value.capitalize()) for t in ItemType]
    
    return render_template(
        'admin/inventory_report.html',
        title='Inventory Report',
        inventory_items=inventory_items,
        stores=stores,
        selected_store_id=store_id,
        selected_item_type=item_type,
        item_types=item_types
    )

@admin_bp.route('/reports/transactions')
@login_required
@partner_admin_required
def transaction_report():
    """Transaction report route."""
    # Get parameters
    store_id = request.args.get('store_id', type=int)
    transaction_type = request.args.get('transaction_type')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Base query - join with Inventory to get item details
    query = db.session.query(Transaction).join(
        Inventory, Transaction.item_id == Inventory.id
    )
    
    # Apply filters
    if store_id:
        query = query.filter(Transaction.store_id == store_id)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Transaction.timestamp >= date_from_obj)
        except ValueError:
            flash('Invalid date format for From Date.', 'warning')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Include the entire day
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(Transaction.timestamp < date_to_obj)
        except ValueError:
            flash('Invalid date format for To Date.', 'warning')
    
    # Filter to accessories for non-global admins
    if current_user.role == UserRole.PARTNER_ADMIN:
        query = query.filter(Inventory.item_type == 'accessories')
    
    # Order by timestamp descending
    transactions = query.order_by(Transaction.timestamp.desc()).paginate(
        page=request.args.get('page', 1, type=int), 
        per_page=50,
        error_out=False
    )
    
    # Get stores for filter
    stores = Store.query.all()
    
    # Transaction types for filter
    from app.models.db import TransactionType
    transaction_types = [(t.value, t.value.replace('_', ' ').capitalize()) for t in TransactionType]
    
    return render_template(
        'admin/transaction_report.html',
        title='Transaction Report',
        transactions=transactions,
        stores=stores,
        transaction_types=transaction_types,
        selected_store_id=store_id,
        selected_transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        max=max,  # Add built-in max function to the template context
        min=min   # Add built-in min function to the template context
    )