"""
RogueSweeper Middleware

This module contains custom middleware for the game application,
including guest player handling without database records.

Author: RogueSweeper Team
"""

from __future__ import annotations

import secrets
import string
from typing import Callable

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse


class GuestUser(AnonymousUser):
    """
    A guest user that can play the game without a database record.
    
    This class extends AnonymousUser to provide guest-specific properties
    while keeping the user unauthenticated in Django's auth system.
    Guest users can play the game but their scores are not saved.
    """
    
    def __init__(self, session_id: str):
        super().__init__()
        self._session_id = session_id
        self._guest_name = f"Guest-{session_id[:6].upper()}"
    
    @property
    def is_guest(self) -> bool:
        """Return True to identify this as a guest user."""
        return True
    
    @property
    def username(self) -> str:
        """Return the guest username."""
        return self._guest_name
    
    @property
    def id(self) -> str:
        """Return the session ID as the user ID."""
        return self._session_id
    
    def __str__(self) -> str:
        """Return string representation."""
        return self._guest_name


class GuestPlayerMiddleware:
    """
    Middleware that provides guest user functionality without database records.
    
    This middleware ensures that all users can play the game immediately
    without requiring registration. Guests are identified by their session
    but no Player record is created in the database.
    
    Flow:
        1. If user is already authenticated → proceed without changes
        2. If user is not authenticated → attach GuestUser to request
    
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
        Process the request and provide guest user for unauthenticated requests.
        
        Args:
            request: The incoming HTTP request.
        
        Returns:
            The HTTP response from the view or next middleware.
        """
        # Skip if user is already authenticated (logged in)
        if request.user.is_authenticated:
            return self.get_response(request)
        
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        # Create a guest user object (not saved to database)
        guest_user = GuestUser(request.session.session_key)
        
        # Attach guest user to request for easy access
        request.guest_user = guest_user
        
        return self.get_response(request)

