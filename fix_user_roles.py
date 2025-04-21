from app import create_app
from app.models.db import db, UserRole
from sqlalchemy import text

app = create_app()

# Get the expected enum values from the UserRole class
enum_mapping = {
    'USER': UserRole.USER.value,  # Should convert to 'user'
    'user': UserRole.USER.value,
    'ADMIN_ACCESSORIES': UserRole.PARTNER_ADMIN.value,  # Should convert to 'partner_admin'
    'admin_accessories': UserRole.PARTNER_ADMIN.value,
    'PARTNER_ADMIN': UserRole.PARTNER_ADMIN.value,  # Should convert to 'partner_admin'
    'ADMIN_GLOBAL': UserRole.ADMIN_GLOBAL.value,  # Should convert to 'admin_global'
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
            if role in enum_mapping and enum_mapping[role] != role:
                # Raw SQL update to avoid enum validation issues
                fix_query = text(f"UPDATE users SET role = '{enum_mapping[role]}' WHERE role = '{role}'")
                result = db.session.execute(fix_query)
                print(f"Updated {result.rowcount} users with role '{role}' to '{enum_mapping[role]}'")
        
        # Update any remaining ADMIN_ACCESSORIES values that might not have been caught
        fix_query = text(f"UPDATE users SET role = '{UserRole.PARTNER_ADMIN.value}' WHERE role IN ('ADMIN_ACCESSORIES', 'admin_accessories')")
        result = db.session.execute(fix_query)
        if result.rowcount > 0:
            print(f"Updated {result.rowcount} users with old role 'ADMIN_ACCESSORIES' to '{UserRole.PARTNER_ADMIN.value}'")
        
        # Commit the changes
        db.session.commit()
        print("Changes committed successfully.")
        
        # Check what values we have now
        enum_query = text("SELECT DISTINCT role FROM users")
        roles_result = db.session.execute(enum_query)
        print("\nRole values after fix:")
        roles = [row[0] for row in roles_result]
        print(roles)
        
        # Verify all values are now recognized by the UserRole enum
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