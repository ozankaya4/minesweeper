"""
RogueSweeper Authentication Views

This module contains views for user authentication including
signup, login, logout, and password reset functionality.

Author: RogueSweeper Team
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.views import View

from .forms import LoginForm, PasswordResetRequestForm, SetPasswordForm, SignUpForm
from .models import Player


class SignUpView(View):
    """User registration view."""
    
    template_name = 'game/auth/signup.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the signup form."""
        # Redirect if already logged in as non-guest
        if request.user.is_authenticated and not getattr(request.user, 'is_guest', True):
            return redirect('game:index')
        
        form = SignUpForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Process the signup form."""
        form = SignUpForm(request.POST)
        
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                _("Account created successfully! Please log in.")
            )
            return redirect('game:login')
        
        return render(request, self.template_name, {'form': form})


class LoginView(View):
    """User login view."""
    
    template_name = 'game/auth/login.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the login form."""
        # Redirect if already logged in as non-guest
        if request.user.is_authenticated and not getattr(request.user, 'is_guest', True):
            return redirect('game:index')
        
        form = LoginForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Process the login form."""
        form = LoginForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user()
            
            # Clear any guest session data
            if 'guest_user_id' in request.session:
                del request.session['guest_user_id']
            
            # Log in the user
            login(request, user)
            
            # Handle "remember me"
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)  # Browser close
            else:
                request.session.set_expiry(1209600)  # 2 weeks
            
            messages.success(request, _("Welcome back, {}!").format(user.username))
            
            # Redirect to next or index
            next_url = request.GET.get('next', 'game:index')
            return redirect(next_url)
        
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    """User logout view."""
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Log out the user."""
        logout(request)
        messages.info(request, _("You have been logged out."))
        return redirect('game:index')
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Log out the user (POST for CSRF protection)."""
        logout(request)
        messages.info(request, _("You have been logged out."))
        return redirect('game:index')


class PasswordResetRequestView(View):
    """View to request a password reset email."""
    
    template_name = 'game/auth/password_reset.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the password reset request form."""
        form = PasswordResetRequestForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Process the password reset request."""
        form = PasswordResetRequestForm(request.POST)
        
        if form.is_valid():
            email = form.cleaned_data['email']
            
            # Try to find the user
            try:
                user = Player.objects.get(email=email, is_guest=False, is_active=True)
                
                # Generate token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Build reset URL
                reset_url = request.build_absolute_uri(
                    reverse('game:password-reset-confirm', kwargs={'uidb64': uid, 'token': token})
                )
                
                # Send email
                subject = _("Reset Your RogueSweeper Password")
                message = render_to_string('game/auth/password_reset_email.html', {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': 'RogueSweeper',
                })
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                    html_message=message,
                )
                
            except Player.DoesNotExist:
                # Don't reveal that the email doesn't exist
                pass
            except Exception as e:
                # Log the error but don't reveal to user
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send password reset email: {e}")
            
            # Always show success to prevent email enumeration
            messages.success(
                request,
                _("If an account with that email exists, we've sent password reset instructions.")
            )
            return redirect('game:login')
        
        return render(request, self.template_name, {'form': form})


class PasswordResetConfirmView(View):
    """View to confirm password reset and set new password."""
    
    template_name = 'game/auth/password_reset_confirm.html'
    
    def get_user(self, uidb64: str) -> Player | None:
        """Decode the UID and get the user."""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Player.objects.get(pk=uid)
            return user
        except (TypeError, ValueError, OverflowError, Player.DoesNotExist):
            return None
    
    def get(self, request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
        """Display the password reset form if token is valid."""
        user = self.get_user(uidb64)
        
        if user is None or not default_token_generator.check_token(user, token):
            messages.error(
                request,
                _("This password reset link is invalid or has expired.")
            )
            return redirect('game:password-reset')
        
        form = SetPasswordForm(user)
        return render(request, self.template_name, {
            'form': form,
            'validlink': True,
        })
    
    def post(self, request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
        """Process the new password."""
        user = self.get_user(uidb64)
        
        if user is None or not default_token_generator.check_token(user, token):
            messages.error(
                request,
                _("This password reset link is invalid or has expired.")
            )
            return redirect('game:password-reset')
        
        form = SetPasswordForm(user, request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(
                request,
                _("Your password has been reset successfully! Please log in.")
            )
            return redirect('game:login')
        
        return render(request, self.template_name, {
            'form': form,
            'validlink': True,
        })
