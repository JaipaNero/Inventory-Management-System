from flask import render_template, redirect, url_for, flash, request, jsonify, session, current_app
from flask_login import login_required, current_user
from sqlalchemy import and_
from app.blueprints.inventory import inventory_bp
from app.forms.inventory import (
    InventoryItemForm, EditInventoryItemForm, StockAdjustmentForm,
    OutgoingAccessoryForm, TransferItemForm
)
from app.models.db import db, ItemType, TransactionType, UserRole
from app.models.inventory import Inventory
from app.models.store import Store
from app.models.transaction import Transaction
from app import limiter
from app.utils.auth import (
    admin_required, partner_admin_required, login_required_with_store,
    log_security_event, get_user_active_store_context
)
from app.utils.transactions import create_transaction, register_outgoing_accessory


@inventory_bp.route('/')
@login_required
def index():
    """Display inventory dashboard/overview based on user's role."""
    # Get the active store context
    active_store_id, is_valid = get_user_active_store_context()
    
    # If no valid store context exists, redirect to store selection
    if not active_store_id:
        flash('Please select a store to view inventory.', 'warning')
        return redirect(url_for('main.select_store'))
        
    # Get the active store
    active_store = Store.query.get_or_404(active_store_id)
    
    # Filter inventory based on user's role and active store
    query = Inventory.query.filter_by(store_id=active_store_id)
    
    # Apply role-based filtering
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        # Regular users and partner admins can only see accessories
        query = query.filter_by(item_type=ItemType.ACCESSORIES)
    
    # Execute the query and fetch items
    inventory_items = query.all()
    
    return render_template(
        'inventory/index.html', 
        title='Inventory Overview',
        items=inventory_items,
        active_store=active_store
    )


@inventory_bp.route('/items')
@login_required
def items():
    """List all inventory items based on user's role and store context."""
    # Get the active store context
    active_store_id, is_valid = get_user_active_store_context()
    
    # If no valid store context exists, redirect to store selection
    if not active_store_id:
        flash('Please select a store to view inventory items.', 'warning')
        return redirect(url_for('main.select_store'))
        
    # Get the active store
    active_store = Store.query.get_or_404(active_store_id)
    
    # Filter inventory based on user's role and active store
    query = Inventory.query.filter_by(store_id=active_store_id)
    
    # Debug - check how many items exist in this store before filtering
    total_in_store = query.count()
    
    # Apply role-based filtering
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        # Regular users and partner admins can only see accessories
        query = query.filter_by(item_type=ItemType.ACCESSORIES)
    
    # Debug - check how many items match after type filtering
    filtered_count = query.count()
    
    # Log for debugging
    current_app.logger.info(f"Store {active_store.name} (ID: {active_store_id}) - Total items: {total_in_store}, After filtering: {filtered_count}")
    
    # Execute the query and fetch items
    inventory_items = query.order_by(Inventory.part_number).all()
    
    # Add count to template for debugging
    return render_template(
        'inventory/items.html', 
        title='Inventory Items',
        inventory=inventory_items,  # Changed from 'items' to 'inventory' to match template
        active_store=active_store,
        item_type_filter='accessories' if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN else None,
        debug_info={'total_items': total_in_store, 'filtered_items': filtered_count}
    )


@inventory_bp.route('/items/add', methods=['GET', 'POST'])
@login_required
@partner_admin_required
def add_item():
    """Add a new inventory item (admin only)."""
    form = InventoryItemForm()
    
    # Populate store choices
    form.store_id.choices = [(store.id, store.name) for store in Store.query.all()]
    
    # If partner_admin, only allow selecting 'accessories' type
    if current_user.role == UserRole.PARTNER_ADMIN:
        form.item_type.choices = [(ItemType.ACCESSORIES.value, 'Accessories')]
    
    if form.validate_on_submit():
        # Check that partner_admin users can't create clothing items
        if current_user.role == UserRole.PARTNER_ADMIN and form.item_type.data != ItemType.ACCESSORIES.value:
            flash('You are only authorized to add accessory items.', 'danger')
            return render_template('inventory/add_item.html', title='Add Item', form=form)
        
        # Create new inventory item
        item = Inventory(
            part_number=form.part_number.data,
            name=form.name.data,
            description=form.description.data,
            item_type=ItemType(form.item_type.data),
            quantity=form.quantity.data,
            store_id=form.store_id.data
        )
        
        db.session.add(item)
        
        # If initial quantity is greater than 0, create an initial transaction
        if form.quantity.data > 0:
            create_transaction(
                item_id=item.id,
                user_id=current_user.id,
                store_id=item.store_id,
                transaction_type=TransactionType.ADD,
                quantity_change=item.quantity,
                notes="Initial inventory entry"
            )
        
        db.session.commit()
        
        log_security_event(
            'item_created', 
            f"User created inventory item: {item.part_number} - {item.name} - Type: {item.item_type.value} - Qty: {item.quantity}"
        )
        
        flash(f'Inventory item {item.part_number} has been added successfully.', 'success')
        return redirect(url_for('inventory.items'))
    
    return render_template('inventory/add_item.html', title='Add Item', form=form)


@inventory_bp.route('/items/<int:item_id>', methods=['GET'])
@login_required
def view_item(item_id):
    """View details of a specific inventory item."""
    item = Inventory.query.get_or_404(item_id)
    
    # Check if the user has access to this item based on their role
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        if item.item_type != ItemType.ACCESSORIES:
            flash('You do not have permission to view non-accessory items.', 'danger')
            return redirect(url_for('inventory.items'))
    
    # For regular users, check if they're assigned to the item's store
    if current_user.role == UserRole.USER:
        user_store_ids = [store.id for store in current_user.stores]
        if item.store_id not in user_store_ids:
            flash('You do not have permission to view items from this store.', 'danger')
            return redirect(url_for('inventory.items'))
    
    # Get transaction history
    transactions = Transaction.query.filter_by(item_id=item.id).order_by(Transaction.timestamp.desc()).all()
    
    return render_template('inventory/item_details.html', 
                         title=f'Item: {item.part_number}',
                         item=item,
                         transactions=transactions)


@inventory_bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@partner_admin_required
def edit_item(item_id):
    """Edit an existing inventory item."""
    item = Inventory.query.get_or_404(item_id)
    
    # Check permissions based on item type and user role
    if current_user.role == UserRole.PARTNER_ADMIN and item.item_type != ItemType.ACCESSORIES:
        flash('You do not have permission to edit non-accessory items.', 'danger')
        return redirect(url_for('inventory.items'))
    
    form = EditInventoryItemForm(original_part_number=item.part_number)
    
    # Populate store choices
    form.store_id.choices = [(store.id, store.name) for store in Store.query.all()]
    
    # If partner_admin, only allow 'accessories' type
    if current_user.role == UserRole.PARTNER_ADMIN:
        form.item_type.choices = [(ItemType.ACCESSORIES.value, 'Accessories')]
    
    if form.validate_on_submit():
        # Check that partner_admin users can't edit item type to non-accessories
        if current_user.role == UserRole.PARTNER_ADMIN and form.item_type.data != ItemType.ACCESSORIES.value:
            flash('You are only authorized to manage accessory items.', 'danger')
            return render_template('inventory/edit_item.html', title='Edit Item', form=form, item=item)
        
        # Track changes for logging
        changes = []
        if item.part_number != form.part_number.data:
            changes.append(f"Part number: {item.part_number} -> {form.part_number.data}")
        if item.name != form.name.data:
            changes.append(f"Name: {item.name} -> {form.name.data}")
        if item.item_type.value != form.item_type.data:
            changes.append(f"Type: {item.item_type.value} -> {form.item_type.data}")
        if item.store_id != form.store_id.data:
            old_store = Store.query.get(item.store_id).name
            new_store = Store.query.get(form.store_id.data).name
            changes.append(f"Store: {old_store} -> {new_store}")
        
        # Update item
        item.part_number = form.part_number.data
        item.name = form.name.data
        item.description = form.description.data
        item.item_type = ItemType(form.item_type.data)
        
        # If store is changing, need to handle as a transfer
        if item.store_id != form.store_id.data:
            old_store_id = item.store_id
            new_store_id = form.store_id.data
            quantity = item.quantity
            
            # Only create transfer transactions if there's actual inventory
            if quantity > 0:
                # Create a transfer out transaction for the old store
                create_transaction(
                    item_id=item.id,
                    user_id=current_user.id,
                    store_id=old_store_id,
                    transaction_type=TransactionType.TRANSFER_OUT,
                    quantity_change=-quantity,
                    notes=f"Transfer to {Store.query.get(new_store_id).name} (item edit)"
                )
                
                # Create a transfer in transaction for the new store
                create_transaction(
                    item_id=item.id,
                    user_id=current_user.id,
                    store_id=new_store_id,
                    transaction_type=TransactionType.TRANSFER_IN,
                    quantity_change=quantity,
                    notes=f"Transfer from {Store.query.get(old_store_id).name} (item edit)"
                )
            
            # Update the store ID
            item.store_id = new_store_id
        
        db.session.commit()
        
        if changes:
            log_security_event(
                'item_updated', 
                f"User updated inventory item: {item.part_number} - Changes: {', '.join(changes)}"
            )
        
        flash(f'Inventory item {item.part_number} has been updated.', 'success')
        return redirect(url_for('inventory.view_item', item_id=item.id))
        
    elif request.method == 'GET':
        # Populate form with current values
        form.part_number.data = item.part_number
        form.name.data = item.name
        form.description.data = item.description
        form.item_type.data = item.item_type.value
        form.store_id.data = item.store_id
        form.quantity.data = item.quantity
    
    return render_template('inventory/edit_item.html', title='Edit Item', form=form, item=item)


@inventory_bp.route('/items/<int:item_id>/adjust', methods=['GET', 'POST'])
@login_required
@partner_admin_required
def adjust_stock(item_id):
    """Adjust stock level of an inventory item."""
    item = Inventory.query.get_or_404(item_id)
    
    # Check permissions based on item type and user role
    if current_user.role == UserRole.PARTNER_ADMIN and item.item_type != ItemType.ACCESSORIES:
        flash('You do not have permission to adjust non-accessory items.', 'danger')
        return redirect(url_for('inventory.items'))
    
    form = StockAdjustmentForm()
    
    if request.method == 'POST':
        # Check if this is a modal submission (has adjustment_type) or a form submission
        is_modal_submission = request.form.get('adjustment_type') is not None
        
        if is_modal_submission:
            # Process modal submission
            try:
                adjustment_type = request.form.get('adjustment_type')
                quantity = int(request.form.get('quantity', 0))
                notes = request.form.get('notes', '')
                
                if adjustment_type == 'add':
                    # Add to stock - positive adjustment
                    adjustment = quantity
                elif adjustment_type == 'remove':
                    # Remove from stock - negative adjustment
                    adjustment = -quantity
                elif adjustment_type == 'set':
                    # Set exact quantity - calculate adjustment needed
                    adjustment = quantity - item.quantity
                else:
                    flash('Invalid adjustment type.', 'danger')
                    return redirect(url_for('inventory.items'))
                
                # Prevent negative inventory (unless admin)
                if item.quantity + adjustment < 0 and current_user.role != UserRole.ADMIN_GLOBAL:
                    flash('This adjustment would result in negative inventory. Only global admins can set negative inventory.', 'warning')
                    return redirect(url_for('inventory.items'))
                
                # Create transaction record (this will update the item quantity too)
                create_transaction(
                    item_id=item.id,
                    user_id=current_user.id,
                    store_id=item.store_id,
                    transaction_type=TransactionType.STOCK_ADJUSTMENT,
                    quantity_change=adjustment,
                    notes=notes
                )
                
                db.session.commit()
                
                # Get refreshed item for accurate quantity in the log and message
                item = Inventory.query.get(item_id)
                
                log_security_event(
                    'stock_adjusted', 
                    f"User adjusted stock: {item.part_number} - Adjustment: {adjustment} - New Quantity: {item.quantity}"
                )
                
                flash(f'Stock level for {item.part_number} adjusted by {adjustment}. New quantity: {item.quantity}', 'success')
                return redirect(url_for('inventory.items'))
                
            except ValueError:
                flash('Invalid quantity value.', 'danger')
                return redirect(url_for('inventory.items'))
        
        # Process regular form submission from adjust_stock.html
        elif form.validate_on_submit():
            adjustment = form.adjustment.data
            
            # Prevent negative inventory (unless overridden by admin)
            if item.quantity + adjustment < 0 and not request.form.get('force_negative'):
                flash('This adjustment would result in negative inventory. Check "Allow Negative Inventory" to override.', 'warning')
                return render_template('inventory/adjust_stock.html', 
                                    title=f'Adjust Stock: {item.part_number}',
                                    form=form, item=item, adjustment=adjustment)
            
            # Create transaction record (this will update the item quantity too)
            create_transaction(
                item_id=item.id,
                user_id=current_user.id,
                store_id=item.store_id,
                transaction_type=TransactionType.STOCK_ADJUSTMENT,
                quantity_change=adjustment,
                notes=form.reason.data
            )
            
            db.session.commit()
            
            # Get refreshed item for accurate quantity in the log and message
            item = Inventory.query.get(item_id)
            
            log_security_event(
                'stock_adjusted', 
                f"User adjusted stock: {item.part_number} - Adjustment: {adjustment} - New Quantity: {item.quantity} - Reason: {form.reason.data}"
            )
            
            flash(f'Stock level for {item.part_number} adjusted by {adjustment}. New quantity: {item.quantity}', 'success')
            return redirect(url_for('inventory.view_item', item_id=item.id))
        else:
            # If it's a form that didn't validate, show errors
            # But if it's a modal submission that didn't get caught earlier, redirect back to inventory
            if 'adjustment_type' in request.form:
                flash('Please ensure all fields are filled out correctly.', 'danger')
                return redirect(url_for('inventory.items'))
            
            # Otherwise show form validation errors for the regular form
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", 'danger')
    
    # GET request - show the form
    return render_template('inventory/adjust_stock.html', 
                         title=f'Adjust Stock: {item.part_number}',
                         form=form, item=item)


@inventory_bp.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_item(item_id):
    """Delete an inventory item (admin_global only)."""
    item = Inventory.query.get_or_404(item_id)
    
    part_number = item.part_number
    name = item.name
    
    # Delete transactions associated with the item
    Transaction.query.filter_by(item_id=item.id).delete()
    
    # Delete the item
    db.session.delete(item)
    db.session.commit()
    
    log_security_event(
        'item_deleted', 
        f"User deleted inventory item: {part_number} - {name}"
    )
    
    flash(f'Inventory item {part_number} has been deleted.', 'success')
    return redirect(url_for('inventory.items'))


@inventory_bp.route('/outgoing/register', methods=['GET', 'POST'])
@login_required_with_store
def register_outgoing():
    """Register an outgoing accessory item (for regular users)."""
    active_store_id, is_valid = get_user_active_store_context()
    
    if not is_valid:
        flash('Please select a valid store first.', 'warning')
        return redirect(url_for('main.select_store'))
    
    # Get the active store object
    active_store = Store.query.get_or_404(active_store_id)
    
    form = OutgoingAccessoryForm()
    
    # For regular users only showing accessories from their active store with positive quantity
    # Get available accessory items
    available_items = Inventory.query.filter(
        Inventory.store_id == active_store_id,
        Inventory.item_type == ItemType.ACCESSORIES,
        Inventory.quantity > 0
    ).all()
    
    # Debug info - see what items are being found
    current_app.logger.info(f"Found {len(available_items)} accessories with positive quantity in store {active_store.name}")
    
    # Set choices for dropdown
    form.item_id.choices = [(i.id, f"{i.part_number} - {i.name} ({i.quantity} available)") for i in available_items]
    
    if form.validate_on_submit():
        # Process the form submission
        success, message, transaction_data = register_outgoing_accessory(
            item_id=form.item_id.data,
            user_id=current_user.id,
            store_id=active_store_id
        )
        
        if success:
            # Include the accessory part number and name in the success message
            flash(f"Accessory {transaction_data['part_number']} - {transaction_data['item_name']} registered successfully. Ticket: {transaction_data['ticket_number']}", 'success')
            return redirect(url_for('inventory.items'))
        else:
            flash(message, 'danger')
    
    # Get current date for the template
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('inventory/register_outgoing.html',
                         title='Register Outgoing Accessory',
                         form=form,
                         active_store=active_store,
                         current_date=current_date,
                         accessories=available_items)


@inventory_bp.route('/outgoing/quick-register/<int:item_id>', methods=['GET'])
@login_required_with_store
def quick_register_outgoing(item_id):
    """Quickly register an outgoing accessory item directly from the inventory list."""
    active_store_id, is_valid = get_user_active_store_context()
    
    if not is_valid:
        flash('Please select a valid store first.', 'warning')
        return redirect(url_for('main.select_store'))
    
    # Get the item and verify it exists
    item = Inventory.query.get_or_404(item_id)
    
    # Verify it's an accessory item
    if item.item_type != ItemType.ACCESSORIES:
        flash('Only accessory items can be registered as outgoing.', 'danger')
        return redirect(url_for('inventory.items'))
    
    # Verify it belongs to the active store
    if item.store_id != active_store_id:
        flash('This item does not belong to your currently active store.', 'danger')
        return redirect(url_for('inventory.items'))
    
    # Verify there's sufficient quantity
    if item.quantity <= 0:
        flash('This item is out of stock.', 'danger')
        return redirect(url_for('inventory.items'))
    
    # Create confirmation form with pre-selected item
    form = OutgoingAccessoryForm()
    
    # Import datetime for the now function
    from datetime import datetime
    
    # For modal display, we need to get the item details
    return render_template('inventory/confirm_outgoing.html',
                          title='Confirm Outgoing Accessory',
                          item=item,
                          active_store=Store.query.get(active_store_id),
                          form=form,
                          now=datetime.now)


@inventory_bp.route('/outgoing/quick-register/<int:item_id>/confirm', methods=['POST'])
@login_required_with_store
def confirm_quick_outgoing(item_id):
    """Process the quick outgoing registration after confirmation."""
    active_store_id, is_valid = get_user_active_store_context()
    
    if not is_valid:
        flash('Please select a valid store first.', 'warning')
        return redirect(url_for('main.select_store'))
    
    # Process the outgoing registration
    notes = request.form.get('notes', '')
    
    # Register the outgoing accessory
    success, message, transaction_data = register_outgoing_accessory(
        item_id=item_id,
        user_id=current_user.id,
        store_id=active_store_id,
        notes=notes
    )
    
    if success:
        # Include the accessory part number and name in the success message
        flash(f"Accessory {transaction_data['part_number']} - {transaction_data['item_name']} registered successfully. Ticket: {transaction_data['ticket_number']}", 'success')
    else:
        flash(message, 'danger')
    
    return redirect(url_for('inventory.items'))


@inventory_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
@partner_admin_required
def transfer_item():
    """Transfer items between stores."""
    form = TransferItemForm()
    
    # Populate store choices
    stores = Store.query.all()
    form.source_store_id.choices = [(s.id, s.name) for s in stores]
    form.destination_store_id.choices = [(s.id, s.name) for s in stores]
    
    # Default source store to active store if one is selected
    active_store_id = session.get('active_store_id')
    if active_store_id:
        form.source_store_id.data = active_store_id
    
    # Item choices will be populated via AJAX based on selected source store
    
    if form.validate_on_submit():
        item = Inventory.query.get_or_404(form.item_id.data)
        
        # Check permissions based on item type and user role
        if current_user.role == UserRole.PARTNER_ADMIN and item.item_type != ItemType.ACCESSORIES:
            flash('You do not have permission to transfer non-accessory items.', 'danger')
            return redirect(url_for('inventory.items'))
            
        # Check if source matches item's current store
        if item.store_id != form.source_store_id.data:
            flash('Item is not in the selected source store.', 'danger')
            return render_template('inventory/transfer_item.html', title='Transfer Item', form=form)
            
        # Check if enough quantity
        if item.quantity < form.quantity.data:
            flash(f'Not enough quantity available. Current quantity: {item.quantity}', 'danger')
            return render_template('inventory/transfer_item.html', title='Transfer Item', form=form)
            
        # Prepare for transfer
        source_store_id = form.source_store_id.data
        destination_store_id = form.destination_store_id.data
        quantity = form.quantity.data
        notes = form.notes.data or f"Transfer from {Store.query.get(source_store_id).name} to {Store.query.get(destination_store_id).name}"
        
        # Check if item already exists in destination store
        dest_item = Inventory.query.filter_by(
            part_number=item.part_number,
            store_id=destination_store_id
        ).first()
        
        # Begin transaction
        try:
            # Create transfer out transaction
            create_transaction(
                item_id=item.id,
                user_id=current_user.id,
                store_id=source_store_id,
                transaction_type=TransactionType.TRANSFER_OUT,
                quantity_change=-quantity,
                notes=f"Transfer to {Store.query.get(destination_store_id).name}: {notes}"
            )
            
            if dest_item:
                # If item exists in destination, use that for the transfer in transaction
                create_transaction(
                    item_id=dest_item.id,
                    user_id=current_user.id,
                    store_id=destination_store_id,
                    transaction_type=TransactionType.TRANSFER_IN,
                    quantity_change=quantity,
                    notes=f"Transfer from {Store.query.get(source_store_id).name}: {notes}"
                )
            else:
                # Create new item in destination store with the transferred quantity
                new_item = Inventory(
                    part_number=item.part_number,
                    name=item.name,
                    description=item.description,
                    item_type=item.item_type,
                    quantity=quantity,
                    store_id=destination_store_id
                )
                db.session.add(new_item)
                db.session.flush()  # Get the new ID
                
                # Create transfer in transaction for new item
                create_transaction(
                    item_id=new_item.id,
                    user_id=current_user.id,
                    store_id=destination_store_id,
                    transaction_type=TransactionType.TRANSFER_IN,
                    quantity_change=quantity,
                    notes=f"Transfer from {Store.query.get(source_store_id).name}: {notes}"
                )
            
            db.session.commit()
            
            log_security_event(
                'item_transferred', 
                f"User transferred item: {item.part_number} - Qty: {quantity} - From: {Store.query.get(source_store_id).name} - To: {Store.query.get(destination_store_id).name}"
            )
            
            flash(f'Successfully transferred {quantity} units of {item.part_number} to {Store.query.get(destination_store_id).name}', 'success')
            return redirect(url_for('inventory.items'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Transfer error: {str(e)}")
            flash('An error occurred during the transfer.', 'danger')
    
    return render_template('inventory/transfer_item.html', title='Transfer Item', form=form)


@inventory_bp.route('/api/items/by-store/<int:store_id>')
@login_required
def get_items_by_store(store_id):
    """API endpoint to get items by store (for AJAX)."""
    # Check if user has permission for the store
    if current_user.role == UserRole.USER:
        user_store_ids = [store.id for store in current_user.stores]
        if store_id not in user_store_ids:
            return jsonify({'error': 'Not authorized for this store'}), 403
    
    query = Inventory.query.filter_by(store_id=store_id).filter(Inventory.quantity > 0)
    
    # Filter by item type based on role
    if current_user.role == UserRole.USER or current_user.role == UserRole.PARTNER_ADMIN:
        query = query.filter_by(item_type=ItemType.ACCESSORIES)
    
    items = query.all()
    item_list = [{'id': item.id, 'part_number': item.part_number, 
                 'name': item.name, 'quantity': item.quantity} 
                for item in items]
    
    return jsonify(item_list)