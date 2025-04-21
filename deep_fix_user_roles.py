from app import create_app
from app.models.db import db, UserRole
from sqlalchemy import text, inspect
import sqlite3

app = create_app()

def get_db_path():
    """Get the SQLite database path from Flask app config"""
    with app.app_context():
        # Extract the database path from the URI
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            return db_uri[10:]  # Remove sqlite:///
    return "instance/inventory.db"  # Default path

def direct_inspect_db():
    """Inspect the database directly using sqlite3"""
    db_path = get_db_path()
    print(f"Connecting directly to SQLite database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check users table structure
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("\nUsers table structure:")
        for col in columns:
            print(f"Column: {col[1]}, Type: {col[2]}")
        
        # Check actual role values (as raw data)
        cursor.execute("SELECT id, username, role FROM users")
        users = cursor.fetchall()
        print("\nUsers in database (raw data):")
        for user in users:
            print(f"ID: {user[0]}, Username: {user[1]}, Role (raw): '{user[2]}'")
        
        # Direct fix using SQLite
        print("\nFixing user roles directly in SQLite...")
        
        # Update all uppercase ADMIN_GLOBAL to lowercase admin_global
        cursor.execute("UPDATE users SET role = 'admin_global' WHERE role = 'ADMIN_GLOBAL'")
        admin_global_count = cursor.rowcount
        print(f"Updated {admin_global_count} users from 'ADMIN_GLOBAL' to 'admin_global'")
        
        # Update all uppercase USER to lowercase user
        cursor.execute("UPDATE users SET role = 'user' WHERE role = 'USER'")
        user_count = cursor.rowcount
        print(f"Updated {user_count} users from 'USER' to 'user'")
        
        # Update all uppercase PARTNER_ADMIN to lowercase partner_admin
        cursor.execute("UPDATE users SET role = 'partner_admin' WHERE role = 'PARTNER_ADMIN'")
        partner_admin_count = cursor.rowcount
        print(f"Updated {partner_admin_count} users from 'PARTNER_ADMIN' to 'partner_admin'")
        
        # Also handle the old admin_accessories role if it exists
        cursor.execute("UPDATE users SET role = 'partner_admin' WHERE role IN ('ADMIN_ACCESSORIES', 'admin_accessories')")
        accessories_count = cursor.rowcount
        if accessories_count > 0:
            print(f"Updated {accessories_count} users from 'ADMIN_ACCESSORIES' to 'partner_admin'")
        
        # Commit changes
        conn.commit()
        
        # Verify fixes
        cursor.execute("SELECT id, username, role FROM users")
        fixed_users = cursor.fetchall()
        print("\nUsers after fixes (raw data):")
        for user in fixed_users:
            print(f"ID: {user[0]}, Username: {user[1]}, Role (raw): '{user[2]}'")
        
    except Exception as e:
        print(f"Error in direct inspection: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Execute the direct inspection and fix
direct_inspect_db()

# Also run the original check with SQLAlchemy to ensure it works
with app.app_context():
    try:
        # Verify with SQLAlchemy
        print("\n=== Verifying with SQLAlchemy ===")
        from app.models.user import User
        
        users = User.query.all()
        print("\nUsers retrieved via SQLAlchemy:")
        for user in users:
            print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}")
            
        print("\nSQLAlchemy verification successful!")
    except Exception as e:
        print(f"Error in SQLAlchemy verification: {e}")