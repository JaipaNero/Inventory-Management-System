"""
Authentication and authorization utilities for the inventory application.
"""
from functools import wraps
from flask import abort, request, current_app, session
from flask_login import current_user
from app.models.db import UserRole
from app.models.security_log import SecurityLog
from app.models.db import db
import datetime

def admin_required(f):
    """Decorator for routes that require admin_global role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN_GLOBAL:
            log_security_event('unauthorized_access_attempt', 
                              f"User attempted to access admin-only resource: {request.path}")
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def partner_admin_required(f):
    """Decorator for routes that require partner_admin or higher role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or (
            current_user.role != UserRole.ADMIN_GLOBAL and 
            current_user.role != UserRole.PARTNER_ADMIN):
            log_security_event('unauthorized_access_attempt', 
                              f"User attempted to access partner admin resource: {request.path}")
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def login_required_with_store(f):
    """Decorator for routes that require login and an active store context."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            log_security_event('unauthorized_access_attempt', 
                              f"Unauthenticated user attempted to access protected resource: {request.path}")
            abort(401)  # Unauthorized
        
        # Check if user has an active store selected
        active_store_id = session.get('active_store_id')
        
        if not active_store_id:
            log_security_event('missing_store_context', 
                              f"User attempted to access resource without store context: {request.path}")
            abort(400, description="No active store selected")
            
        # For regular users, verify they're assigned to this store
        if current_user.role == UserRole.USER:
            user_store_ids = [store.id for store in current_user.stores]
            if active_store_id not in user_store_ids:
                log_security_event('unauthorized_store_access', 
                                  f"User attempted to access unassigned store: {active_store_id}")
                abort(403, description="Not authorized for this store")
                
        return f(*args, **kwargs)
    return decorated_function

def check_password_expiration(user):
    """Check if the user's password has expired (older than 90 days)."""
    if not user.password_last_changed:
        return True  # No record of change, assume expired
    
    expiration_days = current_app.config.get('PASSWORD_EXPIRATION_DAYS', 90)
    expiration_date = user.password_last_changed + datetime.timedelta(days=expiration_days)
    
    return datetime.datetime.utcnow() > expiration_date

def validate_password_complexity(password):
    """
    Validate password complexity requirements.
    Returns tuple: (is_valid, error_message)
    """
    # Check length
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    # Check for at least one special character
    special_chars = "!@#$%^&*()-_=+[]{}|;:,.<>?/~"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password meets complexity requirements"

def log_security_event(event_type, description, user_id=None):
    """
    Log a security event to the security_logs table.
    If user_id is not provided but user is authenticated, use current_user.id.
    """
    if user_id is None and current_user.is_authenticated:
        user_id = current_user.id
        
    log = SecurityLog(
        user_id=user_id,
        ip_address=request.remote_addr,
        event_type=event_type,
        description=description
    )
    
    db.session.add(log)
    db.session.commit()
    
    # Also log to application logger for immediate visibility
    current_app.logger.info(f"SECURITY: {event_type} - {description} - User: {user_id} - IP: {request.remote_addr}")
    
    return log

def get_user_active_store_context():
    """
    Get the user's active store context from the session.
    For admin users, this could be any store.
    For regular users, this must be one of their assigned stores.
    
    Returns tuple: (store_id, is_valid)
    """
    active_store_id = session.get('active_store_id')
    
    # If no active store is set
    if not active_store_id:
        return None, False
        
    # For regular users, verify they're assigned to this store
    if current_user.role == UserRole.USER:
        user_store_ids = [store.id for store in current_user.stores]
        if active_store_id not in user_store_ids:
            return None, False
    
    return active_store_id, True