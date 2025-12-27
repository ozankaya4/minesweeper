"""
RogueSweeper Middleware

This module contains custom middleware for the game application,
including guest player authentication handling.

Author: RogueSweeper Team
"""

from __future__ import annotations

import secrets
import string
from typing import Callable

from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse

from .models import Player


class GuestPlayerMiddleware:
    """
    Middleware that automatically creates and authenticates guest players.
    
    This middleware ensures that all users can play the game immediately
    without requiring registration. If a user is not authenticated, a
    guest account is created and associated with their session.
    
    Flow:
        1. If user is already authenticated → proceed without changes
        2. If session has guest_user_id → retrieve and login that player
        3. If no guest exists → create new guest player and login
    
    Must be placed after AuthenticationMiddleware and SessionMiddleware
    in the MIDDLEWARE setting.
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """
        Initialize the middleware.
        
        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and ensure user is authenticated.
        
        Args:
            request: The incoming HTTP request.
        
        Returns:
            The HTTP response from the view or next middleware.
        """
        # Skip if user is already authenticated
        if request.user.is_authenticated:
            return self.get_response(request)
        
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        # Try to retrieve existing guest user from session
        guest_user_id = request.session.get('guest_user_id')
        
        if guest_user_id:
            # Try to get existing guest player
            try:
                guest_player = Player.objects.get(
                    id=guest_user_id,
                    is_guest=True,
                    is_active=True
                )
                # Log in the guest player
                login(request, guest_player)
                return self.get_response(request)
            except Player.DoesNotExist:
                # Guest player no longer exists, clear invalid ID
                del request.session['guest_user_id']
        
        # Create new guest player
        guest_player = self._create_guest_player()
        
        # Store guest ID in session
        request.session['guest_user_id'] = str(guest_player.id)
        
        # Log in the guest player
        login(request, guest_player)
        
        return self.get_response(request)
    
    def _create_guest_player(self) -> Player:
        """
        Create a new guest player with a random username.
        
        Generates a unique username in the format "Guest-XXXX" where
        XXXX is a random alphanumeric string.
        
        Returns:
            The newly created guest Player instance.
        """
        # Generate random suffix for username
        suffix = ''.join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(6)
        )
        username = f"Guest-{suffix}"
        
        # Ensure username is unique (very unlikely to collide with 6 chars)
        while Player.objects.filter(username=username).exists():
            suffix = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(6)
            )
            username = f"Guest-{suffix}"
        
        # Create the guest player
        guest_player = Player.objects.create_user(
            username=username,
            is_guest=True,
        )
        
        return guest_player
