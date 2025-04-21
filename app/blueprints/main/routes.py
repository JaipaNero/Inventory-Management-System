from flask import render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app.blueprints.main import main_bp
from app.models.db import db, ItemType, UserRole, TransactionType
from app.models.store import Store
from app.models.inventory import Inventory
from app.models.transaction import Transaction
from app.models.user import User
from app.utils.auth import log_security_event
from sqlalchemy import func
from datetime import datetime, timedelta

@main_bp.route('/')
def index():
    """Home page route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html', title='Welcome')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard route."""
    # Check if user has an active store selected
    active_store_id = session.get('active_store_id')
    
    # If user is an admin (any type), they should be able to see the admin dashboard 
    # only when they don't have an active store selected
    if current_user.role in [UserRole.ADMIN_GLOBAL, UserRole.PARTNER_ADMIN] and not active_store_id:
        # For admins without a specific store context, show a global overview
        stores_count = Store.query.count()
        users_count = User.query.count()
        inventory_count = Inventory.query.count()
        
        # Get all available stores based on user role
        if current_user.role == UserRole.ADMIN_GLOBAL:
            # Global admins can access all stores
            stores = Store.query.all()
        else:
            # Partner admins can only access their assigned stores
            stores = current_user.stores
        
        # Define admin endpoints based on role
        admin_endpoints = []
        if current_user.role == UserRole.ADMIN_GLOBAL:
            admin_endpoints = [
                {'name': 'Manage Stores', 'url': url_for('admin.stores')},
                {'name': 'View Security Logs', 'url': url_for('admin.security_logs')}
            ]
        elif current_user.role == UserRole.PARTNER_ADMIN:
            admin_endpoints = [
                {'name': 'View Security Logs', 'url': url_for('admin.security_logs')}
            ]
            
        # Create empty dashboard data structure
        dashboard_data = {
            'inventory_count': inventory_count,
            'low_stock_count': 0,
            'out_of_stock_count': 0,
            'recent_transactions': [],
            'transaction_count_7d': 0
        }
            
        return render_template(
            'main/admin_dashboard.html',
            title='Admin Dashboard',
            stores_count=stores_count,
            users_count=users_count,
            inventory_count=inventory_count,
            admin_endpoints=admin_endpoints,
            stores=stores,
            data=dashboard_data
        )
    
    # If no store is selected and the user has stores assigned, redirect to store selection
    if not active_store_id:
        if current_user.stores:
            return redirect(url_for('main.select_store'))
        elif current_user.role == UserRole.USER:  # Regular users without store assignments
            flash('You do not have any store assignments. Please contact an administrator.', 'warning')
            return render_template('main/no_stores.html', title='No Stores Assigned')
    
    # Get the active store
    active_store = Store.query.get_or_404(active_store_id)
    
    # Get all available stores based on user role
    if current_user.role == UserRole.ADMIN_GLOBAL:
        # Global admins can access all stores
        stores = Store.query.all()
    else:
        # Regular users and partner admins can only access their assigned stores
        stores = current_user.stores
    
    # Choose template based on user role
    template = 'main/admin_dashboard.html' if current_user.role in [UserRole.ADMIN_GLOBAL, UserRole.PARTNER_ADMIN] else 'main/dashboard.html'
    
    # Build dashboard data based on role
    dashboard_data = {}
    
    # Query base for inventory in the active store
    query = Inventory.query.filter_by(store_id=active_store_id)
    
    # Apply role-based filtering for inventory
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        query = query.filter_by(item_type=ItemType.ACCESSORIES)
    
    # Get inventory summary
    inventory_count = query.count()
    low_stock_count = query.filter(Inventory.quantity <= 5).count()
    out_of_stock_count = query.filter(Inventory.quantity <= 0).count()
    
    dashboard_data.update({
        'inventory_count': inventory_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count
    })
    
    # Get recent transactions for this store
    transaction_query = Transaction.query.filter_by(store_id=active_store_id)
    
    # If user is regular user or partner admin, filter to only accessories transactions
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        # Join with inventory to filter by item type
        transaction_query = transaction_query.join(
            Inventory, Transaction.item_id == Inventory.id
        ).filter(Inventory.item_type == ItemType.ACCESSORIES)
    
    # Get recent transactions
    recent_transactions = transaction_query.order_by(
        Transaction.timestamp.desc()
    ).limit(5).all()
    
    # Get transaction count for the past 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    transaction_count = transaction_query.filter(
        Transaction.timestamp >= week_ago
    ).count()
    
    dashboard_data.update({
        'recent_transactions': recent_transactions,
        'transaction_count_7d': transaction_count
    })
    
    return render_template(
        template,
        title='Dashboard',
        active_store=active_store,
        stores=stores,
        data=dashboard_data
    )

@main_bp.route('/select-store')
@login_required
def select_store():
    """Store selection route."""
    # Get stores available to the user
    if current_user.role == UserRole.ADMIN_GLOBAL:
        # Global admins can access all stores
        stores = Store.query.all()
    else:
        # Partner admins and regular users can only access their assigned stores
        stores = current_user.stores
    
    return render_template(
        'main/select_store.html',
        title='Select Store',
        stores=stores
    )

@main_bp.route('/set-active-store/<int:store_id>')
@login_required
def set_active_store(store_id):
    """Set the active store in the session."""
    store = Store.query.get_or_404(store_id)
    
    # For partner admin users and regular users, check if they have access to this store
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        user_store_ids = [s.id for s in current_user.stores]
        if store_id not in user_store_ids:
            flash('You do not have access to this store.', 'danger')
            return redirect(url_for('main.select_store'))
    
    # Set the active store in the session
    session['active_store_id'] = store_id
    
    log_security_event(
        'store_context_changed',
        f"User switched active store to: {store.name}"
    )
    
    flash(f'Active store set to {store.name}', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    """API endpoint for dashboard statistics."""
    # Get the active store context
    active_store_id = session.get('active_store_id')
    
    if not active_store_id:
        return jsonify({'error': 'No active store selected'}), 400
        
    # Build query based on role
    query = Inventory.query.filter_by(store_id=active_store_id)
    
    # Apply role-based filtering
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        query = query.filter_by(item_type=ItemType.ACCESSORIES)
    
    # Get total inventory count
    total_count = query.count()
    
    # Get item counts by quantity ranges
    out_of_stock = query.filter(Inventory.quantity <= 0).count()
    low_stock = query.filter(Inventory.quantity.between(1, 5)).count()
    healthy_stock = query.filter(Inventory.quantity > 5).count()
    
    # Get inventory breakdown by type (only for admin_global)
    type_breakdown = {}
    if current_user.role == UserRole.ADMIN_GLOBAL:
        for item_type in ItemType:
            count = query.filter_by(item_type=item_type).count()
            type_breakdown[item_type.value] = count
    
    # Get recent transaction counts by type
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    transaction_query = Transaction.query.filter_by(store_id=active_store_id)
    
    # Apply role-based filtering for transactions
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        transaction_query = transaction_query.join(
            Inventory, Transaction.item_id == Inventory.id
        ).filter(Inventory.item_type == ItemType.ACCESSORIES)
    
    transaction_query = transaction_query.filter(Transaction.timestamp >= week_ago)
    
    transactions_by_type = {}
    for t_type in TransactionType:
        count = transaction_query.filter_by(transaction_type=t_type).count()
        transactions_by_type[t_type.value] = count
    
    return jsonify({
        'inventory': {
            'total': total_count,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'healthy_stock': healthy_stock,
            'by_type': type_breakdown if current_user.role == UserRole.ADMIN_GLOBAL else None
        },
        'transactions': {
            'by_type': transactions_by_type
        }
    })