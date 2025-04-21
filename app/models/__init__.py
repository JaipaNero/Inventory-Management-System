from app.models.db import db
from app.models.user import User, PasswordHistory
from app.models.store import Store
from app.models.inventory import Inventory
from app.models.transaction import Transaction
from app.models.security_log import SecurityLog

# This file ensures all models are imported when the models package is imported