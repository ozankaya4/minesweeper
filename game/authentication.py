"""
RogueSweeper Custom Authentication

This module contains custom authentication classes for the game API.

Author: RogueSweeper Team
"""

from rest_framework.authentication import BaseAuthentication


class DjangoSessionAuthentication(BaseAuthentication):
    """
    Authentication class that uses Django's session authentication.
    
    This class:
    - Uses Django's AuthenticationMiddleware to get the user
    - Never raises AuthenticationFailed (allows anonymous access)
    - Does NOT enforce CSRF (allows guest POST requests)
    
    This enables both logged-in users and guests to use the API.
    """
    
    def authenticate(self, request):
        """
        Return the Django session user if authenticated, None otherwise.
        
        This method never raises AuthenticationFailed, allowing anonymous
        users to proceed (permission classes determine access).
        """
        # Get the underlying Django request
        django_request = getattr(request, '_request', request)
        
        # Get the user from Django's AuthenticationMiddleware
        user = getattr(django_request, 'user', None)
        
        # Return authenticated user, or None for anonymous
        if user and user.is_authenticated:
            return (user, None)
        
        return None
