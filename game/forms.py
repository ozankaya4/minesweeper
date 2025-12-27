"""
RogueSweeper Authentication Forms

This module contains forms for user authentication including
signup, login, and password reset functionality.

Author: RogueSweeper Team
"""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Player


class SignUpForm(forms.ModelForm):
    """
    User registration form with email-based authentication.
    
    Password Requirements:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    - Not too similar to your username or email
    - Not a commonly used password
    """
    
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your email'),
            'autofocus': True,
        }),
        help_text=_("We'll use this for password recovery.")
    )
    
    username = forms.CharField(
        label=_("Username"),
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Choose a username'),
        }),
        help_text=_("3-30 characters. Letters, digits and @/./+/-/_ only.")
    )
    
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Create a password'),
        }),
    )
    
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Confirm your password'),
        }),
    )
    
    class Meta:
        model = Player
        fields = ['email', 'username']
    
    def clean_email(self):
        """Validate that the email is not already in use."""
        email = self.cleaned_data.get('email')
        if Player.objects.filter(email=email, is_guest=False).exists():
            raise ValidationError(_("An account with this email already exists."))
        return email
    
    def clean_username(self):
        """Validate username format and uniqueness."""
        username = self.cleaned_data.get('username')
        
        if len(username) < 3:
            raise ValidationError(_("Username must be at least 3 characters long."))
        
        if Player.objects.filter(username=username, is_guest=False).exists():
            raise ValidationError(_("This username is already taken."))
        
        return username
    
    def clean_password1(self):
        """Validate password meets all requirements."""
        password = self.cleaned_data.get('password1')
        
        # Check minimum length
        if len(password) < 8:
            raise ValidationError(_("Password must be at least 8 characters long."))
        
        # Check for uppercase
        if not any(c.isupper() for c in password):
            raise ValidationError(_("Password must contain at least one uppercase letter."))
        
        # Check for lowercase
        if not any(c.islower() for c in password):
            raise ValidationError(_("Password must contain at least one lowercase letter."))
        
        # Check for digit
        if not any(c.isdigit() for c in password):
            raise ValidationError(_("Password must contain at least one digit."))
        
        # Check for special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            raise ValidationError(
                _("Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?).")
            )
        
        return password
    
    def clean(self):
        """Validate password confirmation and Django's built-in validators."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2:
            if password1 != password2:
                self.add_error('password2', _("Passwords don't match."))
            
            # Run Django's built-in password validators
            try:
                # Create a temporary user object for validation
                temp_user = Player(
                    username=cleaned_data.get('username', ''),
                    email=cleaned_data.get('email', '')
                )
                validate_password(password1, temp_user)
            except ValidationError as e:
                for error in e.messages:
                    self.add_error('password1', error)
        
        return cleaned_data
    
    def save(self, commit=True):
        """Create a new user with the provided data."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_guest = False
        
        if commit:
            user.save()
        
        return user


class LoginForm(forms.Form):
    """User login form supporting email or username."""
    
    email_or_username = forms.CharField(
        label=_("Email or Username"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your email or username'),
            'autofocus': True,
        })
    )
    
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your password'),
        })
    )
    
    remember_me = forms.BooleanField(
        label=_("Remember me"),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Authenticate the user."""
        cleaned_data = super().clean()
        email_or_username = cleaned_data.get('email_or_username')
        password = cleaned_data.get('password')
        
        if email_or_username and password:
            # Try to find user by email first, then username
            user = None
            
            # Check if it's an email
            if '@' in email_or_username:
                try:
                    player = Player.objects.get(email=email_or_username, is_guest=False)
                    user = authenticate(
                        self.request,
                        username=player.username,
                        password=password
                    )
                except Player.DoesNotExist:
                    pass
            else:
                # Try username
                user = authenticate(
                    self.request,
                    username=email_or_username,
                    password=password
                )
            
            if user is None:
                raise ValidationError(
                    _("Invalid email/username or password. Please try again.")
                )
            
            if not user.is_active:
                raise ValidationError(_("This account has been deactivated."))
            
            self.user_cache = user
        
        return cleaned_data
    
    def get_user(self):
        """Return the authenticated user."""
        return self.user_cache


class PasswordResetRequestForm(forms.Form):
    """Form to request a password reset email."""
    
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your email address'),
            'autofocus': True,
        }),
        help_text=_("Enter the email address associated with your account.")
    )
    
    def clean_email(self):
        """Validate the email exists in the system."""
        email = self.cleaned_data.get('email')
        # We don't reveal whether the email exists or not for security
        return email


class SetPasswordForm(forms.Form):
    """Form to set a new password after reset."""
    
    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter new password'),
            'autofocus': True,
        })
    )
    
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Confirm new password'),
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_new_password1(self):
        """Validate password meets all requirements."""
        password = self.cleaned_data.get('new_password1')
        
        # Check minimum length
        if len(password) < 8:
            raise ValidationError(_("Password must be at least 8 characters long."))
        
        # Check for uppercase
        if not any(c.isupper() for c in password):
            raise ValidationError(_("Password must contain at least one uppercase letter."))
        
        # Check for lowercase
        if not any(c.islower() for c in password):
            raise ValidationError(_("Password must contain at least one lowercase letter."))
        
        # Check for digit
        if not any(c.isdigit() for c in password):
            raise ValidationError(_("Password must contain at least one digit."))
        
        # Check for special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            raise ValidationError(
                _("Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?).")
            )
        
        return password
    
    def clean(self):
        """Validate password confirmation."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2:
            if password1 != password2:
                self.add_error('new_password2', _("Passwords don't match."))
            
            # Run Django's built-in password validators
            try:
                validate_password(password1, self.user)
            except ValidationError as e:
                for error in e.messages:
                    self.add_error('new_password1', error)
        
        return cleaned_data
    
    def save(self):
        """Set the new password for the user."""
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save()
        return self.user
