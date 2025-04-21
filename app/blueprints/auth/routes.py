from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
# Using Python standard library instead of Werkzeug for URL parsing
from urllib.parse import urlparse
from datetime import datetime, timedelta
from app.blueprints.auth import auth_bp
from app.forms.auth import (
    LoginForm, RegistrationForm, PasswordChangeForm, 
    UserCreateForm, UserEditForm, PasswordResetForm
)
from app.models.user import User, PasswordHistory
from app.models.db import db, UserRole
from app.models.store import Store
from app import limiter, login_manager
from app.utils.auth import (
    admin_required, log_security_event, 
    check_password_expiration, validate_password_complexity
)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if user exists
        if not user:
            log_security_event('login_failure', 
                              f'Failed login attempt for non-existent user: {form.username.data}')
            flash('Invalid username or password', 'danger')
            return render_template('auth/login.html', title='Sign In', form=form)
            
        # Check if account is locked
        if user.is_locked:
            log_security_event('login_attempt_locked_account', 
                             f'Login attempt on locked account: {user.username}', 
                             user_id=user.id)
            flash('This account is locked. Please contact an administrator.', 'danger')
            return render_template('auth/login.html', title='Sign In', form=form)
            
        # Check failed login attempts
        max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
        lockout_minutes = current_app.config.get('ACCOUNT_LOCKOUT_MINUTES', 15)
        
        # Reset failed attempts if last attempt was more than lockout_minutes ago
        if user.last_login_attempt_time:
            lockout_time = user.last_login_attempt_time + timedelta(minutes=lockout_minutes)
            if user.failed_login_attempts >= max_attempts and datetime.utcnow() > lockout_time:
                user.failed_login_attempts = 0
        
        # Check password
        if not user.check_password(form.password.data):
            user.failed_login_attempts += 1
            user.last_login_attempt_time = datetime.utcnow()
            
            # Lock account if max attempts reached
            if user.failed_login_attempts >= max_attempts:
                user.is_locked = True
                log_security_event('account_locked', 
                                  f'Account locked after {max_attempts} failed login attempts: {user.username}',
                                  user_id=user.id)
                flash(f'Account locked due to {max_attempts} failed login attempts.', 'danger')
            else:
                remaining = max_attempts - user.failed_login_attempts
                log_security_event('login_failure', 
                                  f'Failed login attempt for user: {user.username}. {remaining} attempts remaining.',
                                  user_id=user.id)
                flash(f'Invalid username or password. {remaining} attempts remaining.', 'danger')
                
            db.session.commit()
            return render_template('auth/login.html', title='Sign In', form=form)
            
        # Reset failed login attempts on successful login
        user.failed_login_attempts = 0
        user.last_login_attempt_time = datetime.utcnow()
        db.session.commit()
        
        # Check if password is expired
        if check_password_expiration(user):
            # Store user ID in session for password change
            session['password_reset_user_id'] = user.id
            log_security_event('password_expired', 
                              f'Password expired for user: {user.username}',
                              user_id=user.id)
            flash('Your password has expired. Please set a new password.', 'warning')
            return redirect(url_for('auth.password_change'))
            
        # Login successful
        login_user(user, remember=form.remember_me.data)
        log_security_event('login_success', 
                          f'Successful login for user: {user.username}',
                          user_id=user.id)
        
        # If user has stores assigned, set the first one as active
        if current_user.stores:
            session['active_store_id'] = current_user.stores[0].id
            
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
            
        return redirect(next_page)
        
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout route."""
    username = current_user.username
    user_id = current_user.id
    log_security_event('logout', f'User logged out: {username}', user_id=user_id)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    """User self-registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, role=UserRole.USER)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Now that user has an ID, create the password history entry
        history_entry = PasswordHistory(user_id=user.id, password_hash=user.password_hash)
        db.session.add(history_entry)
        db.session.commit()
        
        log_security_event('user_registered', 
                          f'New user self-registered: {user.username}',
                          user_id=user.id)
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/password/change', methods=['GET', 'POST'])
@login_required
def password_change():
    """Change password route."""
    form = PasswordChangeForm()
    
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            # Check password history to prevent reuse
            password_history = PasswordHistory.query.filter_by(user_id=current_user.id).order_by(
                PasswordHistory.timestamp.desc()).limit(5).all()
            
            for history in password_history:
                if history.is_same_password(form.new_password.data):
                    flash('Cannot reuse any of your last 5 passwords.', 'danger')
                    return render_template('auth/password_change.html', title='Change Password', form=form)
                    
            # Set new password
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            log_security_event('password_changed', 
                              f'User changed their password: {current_user.username}',
                              user_id=current_user.id)
            flash('Your password has been updated.', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Current password is incorrect.', 'danger')
            
    return render_template('auth/password_change.html', title='Change Password', form=form)

@auth_bp.route('/account', methods=['GET'])
@login_required
def account():
    """User account management route."""
    return render_template('auth/account.html', title='Account')

@auth_bp.route('/users')
@login_required
@admin_required
def users():
    """User management for admin."""
    users_list = User.query.all()
    return render_template('auth/users.html', title='User Management', users=users_list)

@auth_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    """Create new user by admin."""
    form = UserCreateForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            role=UserRole(form.role.data)
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Now that user has an ID, create the password history entry
        history_entry = PasswordHistory(user_id=user.id, password_hash=user.password_hash)
        db.session.add(history_entry)
        db.session.commit()
        
        log_security_event('user_created_by_admin', 
                          f'Admin created new user: {user.username} with role: {user.role.value}',
                          user_id=current_user.id)
        flash(f'User {user.username} has been created successfully!', 'success')
        return redirect(url_for('auth.users'))
        
    return render_template('auth/create_user.html', title='Create User', form=form)

@auth_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user by admin."""
    user = User.query.get_or_404(user_id)
    form = UserEditForm(original_username=user.username)
    
    if form.validate_on_submit():
        old_role = user.role.value if user.role else None
        old_status = "Locked" if user.is_locked else "Active"
        
        user.username = form.username.data
        user.role = UserRole(form.role.data)
        user.is_locked = form.is_locked.data
        
        changes = []
        if old_role != form.role.data:
            changes.append(f"Role changed from {old_role} to {form.role.data}")
            
        if (user.is_locked and old_status != "Locked") or (not user.is_locked and old_status != "Active"):
            new_status = "Locked" if user.is_locked else "Active"
            changes.append(f"Status changed from {old_status} to {new_status}")
            
        # If admin selects reset password, we'll set a temporary password
        if form.reset_password.data:
            temp_password = "ChangeMe123!"  # This meets complexity requirements
            user.set_password(temp_password)
            changes.append("Password has been reset")
            
        db.session.commit()
        
        log_security_event('user_edited_by_admin', 
                          f"Admin edited user {user.username}: {', '.join(changes)}",
                          user_id=current_user.id)
        flash(f'User {user.username} has been updated.', 'success')
        
        if form.reset_password.data:
            flash(f'Temporary password set to: {temp_password}', 'info')
            flash('User will be required to change this password on next login.', 'info')
            
        return redirect(url_for('auth.users'))
    elif request.method == 'GET':
        # Populate form with current values
        form.username.data = user.username
        form.role.data = user.role.value
        form.is_locked.data = user.is_locked
        
    return render_template('auth/edit_user.html', title='Edit User', form=form, user=user)

@auth_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete user by admin."""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('auth.users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    log_security_event('user_deleted_by_admin', 
                      f'Admin deleted user: {username}',
                      user_id=current_user.id)
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('auth.users'))

@auth_bp.route('/users/<int:user_id>/stores', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_user_stores(user_id):
    """Manage store assignments for a user."""
    user = User.query.get_or_404(user_id)
    stores = Store.query.all()
    
    if request.method == 'POST':
        # Get selected store IDs from form
        selected_store_ids = request.form.getlist('stores')
        selected_store_ids = [int(id) for id in selected_store_ids]
        
        # Get current store assignments
        current_store_ids = [store.id for store in user.stores]
        
        # Update user's stores
        user.stores = []
        for store in stores:
            if store.id in selected_store_ids:
                user.stores.append(store)
                
        db.session.commit()
        
        # Log changes
        added = set(selected_store_ids) - set(current_store_ids)
        removed = set(current_store_ids) - set(selected_store_ids)
        
        store_changes = []
        if added:
            added_names = [s.name for s in Store.query.filter(Store.id.in_(added)).all()]
            store_changes.append(f"Added stores: {', '.join(added_names)}")
        if removed:
            removed_names = [s.name for s in Store.query.filter(Store.id.in_(removed)).all()]
            store_changes.append(f"Removed stores: {', '.join(removed_names)}")
            
        if store_changes:
            log_security_event('user_stores_updated', 
                            f"Updated store assignments for user {user.username}: {'; '.join(store_changes)}",
                            user_id=current_user.id)
                            
        flash(f'Store assignments for {user.username} have been updated.', 'success')
        return redirect(url_for('auth.users'))
        
    # GET request - show form with current assignments
    return render_template('auth/manage_user_stores.html', 
                         title=f'Manage Stores for {user.username}', 
                         user=user, 
                         stores=stores)