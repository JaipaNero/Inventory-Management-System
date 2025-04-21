"""
Authentication forms for the inventory application.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Email
from app.models.user import User
from app.models.db import UserRole
from app.utils.auth import validate_password_complexity

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=64)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken. Please choose a different one.')
            
    def validate_password(self, password):
        valid, message = validate_password_complexity(password.data)
        if not valid:
            raise ValidationError(message)

class UserCreateForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=64)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[
        (UserRole.USER.value, 'User'),
        (UserRole.PARTNER_ADMIN.value, 'Partner Admin'),
        (UserRole.ADMIN_GLOBAL.value, 'Global Admin')
    ])
    submit = SubmitField('Create User')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken. Please choose a different one.')
            
    def validate_password(self, password):
        valid, message = validate_password_complexity(password.data)
        if not valid:
            raise ValidationError(message)

class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8, max=64)])
    confirm_password = PasswordField('Confirm New Password', 
                                    validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')
    
    def validate_new_password(self, new_password):
        valid, message = validate_password_complexity(new_password.data)
        if not valid:
            raise ValidationError(message)

class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8, max=64)])
    confirm_password = PasswordField('Confirm Password', 
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')
    
    def validate_password(self, password):
        valid, message = validate_password_complexity(password.data)
        if not valid:
            raise ValidationError(message)

class UserEditForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    role = SelectField('Role', choices=[
        (UserRole.USER.value, 'User'),
        (UserRole.PARTNER_ADMIN.value, 'Partner Admin'),
        (UserRole.ADMIN_GLOBAL.value, 'Global Admin')
    ])
    is_locked = BooleanField('Account Locked')
    reset_password = BooleanField('Reset Password')
    submit = SubmitField('Update User')

    def __init__(self, original_username=None, *args, **kwargs):
        super(UserEditForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Username is already taken. Please choose a different one.')