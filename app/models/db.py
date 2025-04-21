from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import enum

db = SQLAlchemy()
migrate = Migrate()

# Define user roles as an enum for type safety
class UserRole(enum.Enum):
    USER = 'user'
    PARTNER_ADMIN = 'partner_admin'  # Renamed from admin_accessories
    ADMIN_GLOBAL = 'admin_global'

# Define transaction types as an enum for type safety
class TransactionType(enum.Enum):
    ADD = 'add'
    REMOVE = 'remove'
    TRANSFER_IN = 'transfer_in'
    TRANSFER_OUT = 'transfer_out'
    STOCK_ADJUSTMENT = 'stock_adjustment'

# Define item types as an enum for type safety
class ItemType(enum.Enum):
    ACCESSORIES = 'accessories'
    CLOTHING = 'clothing'