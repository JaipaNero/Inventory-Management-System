from app import create_app
from app.models.db import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Update the user roles directly using SQL
    update_query = text("""
    UPDATE users
    SET role = 'partner_admin'
    WHERE role = 'ADMIN_ACCESSORIES'
    """)
    
    # Execute the query and commit
    try:
        result = db.session.execute(update_query)
        affected_rows = result.rowcount
        db.session.commit()
        print(f"Updated {affected_rows} users from 'ADMIN_ACCESSORIES' to 'partner_admin'")
    except Exception as e:
        db.session.rollback()
        print(f"Error updating user roles: {e}")
        
    # Verify the change
    check_query = text("SELECT id, username, role FROM users WHERE role = 'partner_admin'")
    result = db.session.execute(check_query)
    print("\nUsers with updated role:")
    for row in result:
        print(f"ID: {row.id}, Username: {row.username}, Role: {row.role}")