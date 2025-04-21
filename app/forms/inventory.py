"""
Inventory management forms for the inventory application.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Optional
from app.models.db import ItemType
from app.models.inventory import Inventory
from app.models.store import Store

class InventoryItemForm(FlaskForm):
    part_number = StringField('Part Number', validators=[DataRequired(), Length(min=3, max=50)])
    name = StringField('Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    item_type = SelectField('Item Type', choices=[
        (ItemType.ACCESSORIES.value, 'Accessories'),
        (ItemType.CLOTHING.value, 'Clothing')
    ], validators=[DataRequired()])
    quantity = IntegerField('Initial Quantity', validators=[NumberRange(min=0)], default=0)
    store_id = SelectField('Store', validators=[DataRequired()], coerce=int)
    submit = SubmitField('Save Item')
    
    def __init__(self, *args, **kwargs):
        super(InventoryItemForm, self).__init__(*args, **kwargs)
        # Populate store choices - this is populated in the view function
        self.store_id.choices = []
    
    def validate_part_number(self, part_number):
        """Validate that the part number is unique."""
        item = Inventory.query.filter_by(part_number=part_number.data).first()
        if item:
            # If this is an edit form and the part number hasn't changed, it's ok
            if hasattr(self, 'original_part_number') and self.original_part_number == part_number.data:
                return
            raise ValidationError('This part number is already in use. Please choose a different one.')

class EditInventoryItemForm(InventoryItemForm):
    def __init__(self, original_part_number=None, *args, **kwargs):
        super(EditInventoryItemForm, self).__init__(*args, **kwargs)
        self.original_part_number = original_part_number
        
class StockAdjustmentForm(FlaskForm):
    adjustment = IntegerField('Adjustment Amount', validators=[DataRequired()])
    reason = TextAreaField('Reason for Adjustment', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Submit Adjustment')

class OutgoingAccessoryForm(FlaskForm):
    item_id = SelectField('Item', validators=[DataRequired()], coerce=int)
    submit = SubmitField('Register Outgoing Item')
    
    def __init__(self, *args, **kwargs):
        super(OutgoingAccessoryForm, self).__init__(*args, **kwargs)
        # Populate item choices - this is populated in the view function
        self.item_id.choices = []

class TransferItemForm(FlaskForm):
    item_id = SelectField('Item', validators=[DataRequired()], coerce=int)
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])
    source_store_id = SelectField('Source Store', validators=[DataRequired()], coerce=int)
    destination_store_id = SelectField('Destination Store', validators=[DataRequired()], coerce=int)
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Transfer Item')
    
    def __init__(self, *args, **kwargs):
        super(TransferItemForm, self).__init__(*args, **kwargs)
        # These are populated in the view function
        self.item_id.choices = []
        self.source_store_id.choices = []
        self.destination_store_id.choices = []
        
    def validate_destination_store_id(self, destination_store_id):
        """Validate that source and destination stores are different."""
        if self.source_store_id.data == destination_store_id.data:
            raise ValidationError('Source and destination stores must be different.')