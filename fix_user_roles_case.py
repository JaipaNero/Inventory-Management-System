from app import create_app
from app.models.db import db, UserRole
from sqlalchemy import text

app = create_app()

# Get the expected enum values from the UserRole class
enum_mapping = {
    # Map all possible cases to their correct values
    'USER': UserRole.USER.value,
    'user': UserRole.USER.value,
    'PARTNER_ADMIN': UserRole.PARTNER_ADMIN.value,
    'partner_admin': UserRole.PARTNER_ADMIN.value,
    'ADMIN_ACCESSORIES': UserRole.PARTNER_ADMIN.value,
    'admin_accessories': UserRole.PARTNER_ADMIN.value,
    'ADMIN_GLOBAL': UserRole.ADMIN_GLOBAL.value,
    'admin_global': UserRole.ADMIN_GLOBAL.value
}

with app.app_context():
    # First, let's understand what enum values are actually in the database
    try:
        enum_query = text("SELECT DISTINCT role FROM users")
        roles_result = db.session.execute(enum_query)
        print("Current role values in database:")
        roles = [row[0] for row in roles_result]
        print(roles)
        
        # Fix each role value to match the exact case defined in the enum
        for role in roles:
            if role in enum_mapping:
                # Use a case-sensitive comparison to avoid unnecessary updates
                if enum_mapping[role] != role:
                    # Raw SQL update to avoid enum validation issues
                    fix_query = text(f"UPDATE users SET role = '{enum_mapping[role]}' WHERE role = '{role}'")
                    result = db.session.execute(fix_query)
                    print(f"Updated {result.rowcount} users with role '{role}' to '{enum_mapping[role]}'")
        
        # Commit the changes
        db.session.commit()
        print("Changes committed successfully.")
        
        # Verify all values are now recognized by the UserRole enum
        enum_query = text("SELECT DISTINCT role FROM users")
        roles_result = db.session.execute(enum_query)
        print("\nRole values after fix:")
        roles = [row[0] for row in roles_result]
        print(roles)
        
        all_valid = True
        for role in roles:
            try:
                enum_value = UserRole(role)
                print(f"Role '{role}' maps to enum {enum_value}")
            except (ValueError, KeyError):
                all_valid = False
                print(f"ERROR: Role '{role}' still doesn't map to a valid enum value")
        
        if all_valid:
            print("\nAll role values in the database are now valid according to the UserRole enum.")
        else:
            print("\nThere are still invalid role values in the database!")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error fixing user roles: {e}")