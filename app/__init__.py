import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.models.db import db, migrate

# Initialize extensions
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def create_app(config=None):
    """
    Create and configure the Flask application.
    
    Args:
        config (dict, optional): Configuration dictionary to override defaults.
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure the app with default settings
    app.config.from_mapping(
        SECRET_KEY='dev',  # This should be overridden in production
        TEMPLATES_AUTO_RELOAD=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=False,  # Should be True in production with HTTPS
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=3600,  # 1 hour in seconds
        
        # SQLAlchemy configuration
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(app.instance_path, 'inventory.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
    )
    
    # Override default settings with instance config
    if config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(config)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Initialize extensions with the app
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    limiter.init_app(app)
    
    # Initialize database
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Set up user loader for Flask-Login
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Configure logging
    configure_logging(app)
    
    # Set security headers
    configure_security_headers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_commands(app)
    
    return app

def configure_logging(app):
    """Configure application logging."""
    log_dir = os.path.join(os.path.dirname(app.instance_path), 'logs')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'inventory_app.log')
    
    # Set up file handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=10)  # 10MB max size, keep 10 backups
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    
    # Set up app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Inventory Application startup')

def configure_security_headers(app):
    """Configure security headers for the application."""
    @app.after_request
    def add_security_headers(response):
        # Prevent browsers from incorrectly detecting non-scripts as scripts
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Restrict how the site appears in iframes
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Control how much referrer information is included with requests
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # When HTTPS is enforced, enable HSTS
        if not app.config['DEBUG'] and app.config.get('FORCE_HTTPS', False):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
        # Content Security Policy
        csp = [
            "default-src 'self'",
            "img-src 'self' data:",
            "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com fonts.googleapis.com",  # Allow Materialize CSS and Google Fonts
            "script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com",  # Allow Materialize JS
            "font-src 'self' data: fonts.gstatic.com"  # Allow Material Icons
        ]
        response.headers['Content-Security-Policy'] = '; '.join(csp)
        
        return response

def register_blueprints(app):
    """Register Flask blueprints."""
    from app.blueprints.auth import auth_bp
    from app.blueprints.inventory import inventory_bp
    from app.blueprints.main import main_bp
    from app.blueprints.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

def register_error_handlers(app):
    """Register error handlers."""
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(error):
        from flask import render_template
        app.logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500

def register_commands(app):
    """Register custom CLI commands."""
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize the database."""
        from app.models.init_db import init_database
        init_database()
    
    @app.cli.command('seed-db')
    def seed_db_command():
        """Seed the database with initial data."""
        from app.models.init_db import seed_database
        seed_database()