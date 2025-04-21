import os
import secrets

# Generate a secure random secret key
SECRET_KEY = secrets.token_hex(32)

# Security settings
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False  # Set to True when using HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'

# Flask settings
DEBUG = True  # Set to False in production
TESTING = False

# Application settings
SITE_NAME = "Inventory Management System"