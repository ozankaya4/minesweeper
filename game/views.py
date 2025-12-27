"""
RogueSweeper API Views

This module contains Django REST Framework views for the game API.
Views handle game session management, action processing, and
score tracking.

Author: RogueSweeper Team
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.views import View
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


# =============================================================================
# Custom Permissions
# =============================================================================

class IsAuthenticatedOrGuest(BasePermission):
    """
    Allow authenticated users or guests (via session).
    
    Guests can play the game but their scores won't be saved.
    This permission class ensures everyone can access the game.
    """
    
    def has_permission(self, request, view):
        # Allow everyone - guests and authenticated users alike
        # The view logic handles the difference between them
        return True


def is_guest_user(request: Request) -> bool:
    """Check if the current request is from a guest user."""
    return not request.user.is_authenticated


def _get_session(request: Request):
    """Get the Django session from a DRF or Django request."""
    # DRF wraps the Django request, session is on the underlying request
    if hasattr(request, '_request'):
        return request._request.session
    return request.session


def get_guest_session_data(request: Request) -> dict:
    """Get or create guest game session data from the request session."""
    session = _get_session(request)
    
    # Ensure session exists
    if not session.session_key:
        session.create()
    
    if 'guest_game' not in session:
        session['guest_game'] = {
            'id': str(uuid.uuid4()),
            'level_number': 1,
            'score': 0,
            'clues_remaining': get_clues_for_level(1),
            'time_elapsed': 0,
            'cells_revealed': 0,
            'flags_placed': 0,
            'board_state': {},
            'is_active': False,
            'status': 'new',
        }
    return session['guest_game']


def save_guest_session_data(request: Request, data: dict) -> None:
    """Save guest game session data to the request session."""
    session = _get_session(request)
    session['guest_game'] = data
    session.modified = True


# =============================================================================
# Template Views
# =============================================================================

class HomeView(View):
    """
    Main game page view.
    
    Renders the index.html template with the game interface.
    Handles guest player creation for unauthenticated users.
    """
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Render the game home page.
        
        If user is not authenticated, ensures a guest session exists
        by storing guest identifier in session.
        """
        # Ensure session exists for guest players
        if not request.session.session_key:
            request.session.create()
        
        return render(request, 'game/index.html')


class SwitchLanguageView(View):
    """
    View to handle language switching.
    
    Accepts POST requests with a language code, validates it against
    available languages, and sets the django_language cookie.
    """
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """
        Switch the user's language preference.
        
        Args:
            request: HTTP request with 'language' in POST data or JSON body.
        
        Returns:
            JSON response or redirect to referrer.
        """
        # Get language code from POST data or JSON body
        language_code = request.POST.get('language')
        
        if not language_code:
            # Try to get from JSON body
            try:
                body = json.loads(request.body)
                language_code = body.get('language')
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Validate language code
        valid_languages = [code for code, name in settings.LANGUAGES]
        
        if not language_code or language_code not in valid_languages:
            return JsonResponse(
                {'error': 'Invalid language code', 'valid_codes': valid_languages},
                status=400
            )
        
        # Activate the language for this request
        translation.activate(language_code)
        
        # Store in session
        request.session['_language'] = language_code
        
        # Determine response type
        referer = request.META.get('HTTP_REFERER')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                  request.content_type == 'application/json'
        
        if is_ajax:
            response = JsonResponse({'success': True, 'language': language_code})
        else:
            response = redirect(referer) if referer else redirect('game:index')
        
        # Set the language cookie
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language_code,
            max_age=settings.LANGUAGE_COOKIE_AGE if hasattr(settings, 'LANGUAGE_COOKIE_AGE') else 31536000,
            path=settings.LANGUAGE_COOKIE_PATH if hasattr(settings, 'LANGUAGE_COOKIE_PATH') else '/',
            domain=settings.LANGUAGE_COOKIE_DOMAIN if hasattr(settings, 'LANGUAGE_COOKIE_DOMAIN') else None,
            secure=settings.LANGUAGE_COOKIE_SECURE if hasattr(settings, 'LANGUAGE_COOKIE_SECURE') else False,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY if hasattr(settings, 'LANGUAGE_COOKIE_HTTPONLY') else False,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE if hasattr(settings, 'LANGUAGE_COOKIE_SAMESITE') else 'Lax',
        )
        
        return response


from .engine import GameEngine
from .models import GameSession, Player, Score, get_clues_for_level
from .serializers import (
    GameActionSerializer,
    GameSessionSerializer,
    LeaderboardSerializer,
    NextLevelSerializer,
    PlayerSerializer,
    ScoreSerializer,
    StartGameSerializer,
)


class StartGameView(APIView):
    """
    API endpoint to start a new game or retrieve an existing active session.
    
    POST /api/game/start/
    
    Request Body (optional):
        {
            "force_new": false  // If true, abandons existing session
        }
    
    Response:
        - 200: Returns existing active session
        - 201: Returns newly created session
        - 400: Invalid request
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def post(self, request: Request) -> Response:
        """
        Start a new game or return existing active session.
        
        If the user has an active session and force_new is False,
        returns the existing session. Otherwise, creates a new one.
        """
        serializer = StartGameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        force_new = serializer.validated_data.get('force_new', False)
        
        # Handle guest users
        if is_guest_user(request):
            return self._handle_guest_start(request, force_new)
        
        # Handle authenticated users
        player = request.user
        
        # Check for existing active session
        active_session = GameSession.get_active_session(player)
        
        if active_session and not force_new:
            # Return existing session
            response_serializer = GameSessionSerializer(active_session)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        # Abandon existing session if force_new
        if active_session and force_new:
            active_session.status = GameSession.SessionStatus.ABANDONED
            active_session.is_active = False
            active_session.save()
        
        # Create new session
        new_session = GameSession.objects.create(
            player=player,
            level_number=1,
            clues_remaining=get_clues_for_level(1),
            status=GameSession.SessionStatus.ACTIVE,
            is_active=True,
        )
        
        # Increment player's games played counter
        player.increment_games_played()
        
        response_serializer = GameSessionSerializer(new_session)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def _handle_guest_start(self, request: Request, force_new: bool) -> Response:
        """Handle game start for guest users (session-based)."""
        guest_data = get_guest_session_data(request)
        
        # Return existing active session if not forcing new
        if guest_data.get('is_active') and not force_new:
            return Response(self._format_guest_response(guest_data), status=status.HTTP_200_OK)
        
        # Create new guest session
        guest_data = {
            'id': str(uuid.uuid4()),
            'level_number': 1,
            'score': 0,
            'clues_remaining': get_clues_for_level(1),
            'time_elapsed': 0,
            'cells_revealed': 0,
            'flags_placed': 0,
            'board_state': {},
            'is_active': True,
            'status': 'active',
        }
        save_guest_session_data(request, guest_data)
        
        return Response(self._format_guest_response(guest_data), status=status.HTTP_201_CREATED)
    
    def _format_guest_response(self, guest_data: dict) -> dict:
        """Format guest session data for API response."""
        board = guest_data.get('board_state', {})
        level = guest_data['level_number']
        rows = board.get('rows', getattr(settings, 'ROGUESWEEPER_BASE_ROWS', 8))
        cols = board.get('cols', getattr(settings, 'ROGUESWEEPER_BASE_COLS', 8))
        
        return {
            'id': guest_data['id'],
            'level_number': level,
            'score': guest_data['score'],
            'clues_remaining': guest_data['clues_remaining'],
            'clues_total': get_clues_for_level(level),
            'time_elapsed': guest_data['time_elapsed'],
            'cells_revealed': guest_data['cells_revealed'],
            'flags_placed': guest_data['flags_placed'],
            'is_active': guest_data['is_active'],
            'status': guest_data['status'],
            'board': GameEngine.render_for_frontend(board) if board.get('initialized') else {
                'rows': rows,
                'cols': cols,
                'cells': [['hidden'] * cols for _ in range(rows)],
                'game_over': False,
                'won': False,
            },
            'is_guest': True,
        }


class GameSessionView(APIView):
    """
    API endpoint to retrieve the current game session state.
    
    GET /api/game/session/
    
    Response:
        - 200: Returns current active session
        - 404: No active session found
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def get(self, request: Request) -> Response:
        """
        Get the current active game session.
        """
        # Handle guest users
        if is_guest_user(request):
            guest_data = get_guest_session_data(request)
            if not guest_data.get('is_active'):
                return Response(
                    {"detail": "No active game session found. Start a new game."},
                    status=status.HTTP_404_NOT_FOUND
                )
            return Response(self._format_guest_response(guest_data), status=status.HTTP_200_OK)
        
        # Handle authenticated users
        player = request.user
        active_session = GameSession.get_active_session(player)
        
        if not active_session:
            return Response(
                {"detail": "No active game session found. Start a new game."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = GameSessionSerializer(active_session)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def _format_guest_response(self, guest_data: dict) -> dict:
        """Format guest session data for API response."""
        board = guest_data.get('board_state', {})
        level = guest_data['level_number']
        rows = board.get('rows', getattr(settings, 'ROGUESWEEPER_BASE_ROWS', 8))
        cols = board.get('cols', getattr(settings, 'ROGUESWEEPER_BASE_COLS', 8))
        
        return {
            'id': guest_data['id'],
            'level_number': level,
            'score': guest_data['score'],
            'clues_remaining': guest_data['clues_remaining'],
            'clues_total': get_clues_for_level(level),
            'time_elapsed': guest_data['time_elapsed'],
            'cells_revealed': guest_data['cells_revealed'],
            'flags_placed': guest_data['flags_placed'],
            'is_active': guest_data['is_active'],
            'status': guest_data['status'],
            'board': GameEngine.render_for_frontend(board) if board.get('initialized') else {
                'rows': rows,
                'cols': cols,
                'cells': [['hidden'] * cols for _ in range(rows)],
                'game_over': False,
                'won': False,
            },
            'is_guest': True,
        }


class GameActionView(APIView):
    """
    API endpoint to perform game actions (reveal, flag, chord, clue).
    
    POST /api/game/action/
    
    Request Body:
        {
            "row": 4,
            "col": 5,
            "action": "reveal"  // One of: reveal, flag, chord, clue
        }
    
    Response:
        - 200: Action performed successfully, returns updated session
        - 400: Invalid action or coordinates
        - 404: No active session found
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def post(self, request: Request) -> Response:
        """
        Process a game action.
        
        Validates the action, updates the board state, checks for
        win/loss conditions, and returns the updated session.
        """
        # Validate input
        serializer = GameActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        row = serializer.validated_data['row']
        col = serializer.validated_data['col']
        action = serializer.validated_data['action']
        
        # Handle guest users
        if is_guest_user(request):
            return self._handle_guest_action(request, row, col, action)
        
        # Get active session for authenticated users
        player = request.user
        session = GameSession.get_active_session(player)
        
        if not session:
            return Response(
                {"detail": "No active game session found. Start a new game."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if game is already over
        if session.board_state.get('game_over', False):
            return Response(
                {"detail": "Game is already over. Start a new game or advance to next level."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate coordinates against board dimensions
        board = session.board_state
        rows = board.get('rows', 0) or session.calculate_grid_size()[0]
        cols = board.get('cols', 0) or session.calculate_grid_size()[1]
        
        if row >= rows or col >= cols:
            return Response(
                {"detail": f"Coordinates ({row}, {col}) out of bounds. Board is {rows}x{cols}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get mine count for potential board initialization
        mine_count = session.calculate_mine_count()
        
        # Track clues used for scoring
        clue_used = False
        
        # Process action
        try:
            if action == 'reveal':
                board = GameEngine.reveal_cell(board, row, col, mine_count)
            
            elif action == 'flag':
                board = GameEngine.toggle_flag(board, row, col)
            
            elif action == 'chord':
                board = GameEngine.chord_reveal(board, row, col)
            
            elif action == 'clue':
                # Check if clues are available
                if session.clues_remaining <= 0:
                    return Response(
                        {"detail": "No clues remaining for this level."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Apply clue
                board = GameEngine.apply_clue(board, row, col, mine_count)
                
                # Decrement clue count
                session.clues_remaining -= 1
                clue_used = True
            
            else:
                return Response(
                    {"detail": f"Unknown action: {action}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update session with new board state
        session.board_state = board
        session.cells_revealed = len(board.get('revealed', []))
        session.flags_placed = len(board.get('flagged', []))
        
        # Check for game over (win or loss)
        if board.get('game_over', False):
            won = board.get('won', False)
            
            # Update session status
            session.status = (
                GameSession.SessionStatus.WON if won
                else GameSession.SessionStatus.LOST
            )
            session.is_active = not won  # Keep active if won (for next level)
            
            # Calculate score
            clues_per_level = get_clues_for_level(session.level_number)
            clues_used_count = clues_per_level - session.clues_remaining
            
            level_score = GameEngine.calculate_score(
                level=session.level_number,
                cells_revealed=session.cells_revealed,
                time_elapsed=session.time_elapsed,
                clues_used=clues_used_count,
                won=won
            )
            
            # Update session score
            session.score += level_score
            
            # Create Score record
            if not won:
                # Game over - create final score record
                Score.create_from_session(session)
                session.is_active = False
            
            # Update player stats
            if won:
                player.increment_games_won()
                player.current_level = session.level_number
                player.save(update_fields=['current_level', 'updated_at'])
        
        session.save()
        
        # Return updated session
        response_serializer = GameSessionSerializer(session)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def _handle_guest_action(self, request: Request, row: int, col: int, action: str) -> Response:
        """Handle game action for guest users."""
        guest_data = get_guest_session_data(request)
        
        if not guest_data.get('is_active'):
            return Response(
                {"detail": "No active game session found. Start a new game."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        board = guest_data.get('board_state', {})
        level = guest_data['level_number']
        
        # Calculate grid size and mine count for this level
        base_rows = getattr(settings, 'ROGUESWEEPER_BASE_ROWS', 8)
        base_cols = getattr(settings, 'ROGUESWEEPER_BASE_COLS', 8)
        base_mines = getattr(settings, 'ROGUESWEEPER_BASE_MINES', 10)
        row_inc = getattr(settings, 'ROGUESWEEPER_ROW_INCREMENT', 1)
        col_inc = getattr(settings, 'ROGUESWEEPER_COL_INCREMENT', 1)
        mine_inc = getattr(settings, 'ROGUESWEEPER_MINE_INCREMENT', 2)
        max_rows = getattr(settings, 'ROGUESWEEPER_MAX_ROWS', 30)
        max_cols = getattr(settings, 'ROGUESWEEPER_MAX_COLS', 30)
        
        rows = min(base_rows + (level - 1) * row_inc, max_rows)
        cols = min(base_cols + (level - 1) * col_inc, max_cols)
        mine_count = base_mines + (level - 1) * mine_inc
        
        # Initialize board if empty
        if not board:
            board = {'rows': rows, 'cols': cols, 'initialized': False}
        
        # Check if game is already over
        if board.get('game_over', False):
            return Response(
                {"detail": "Game is already over. Start a new game or advance to next level."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process action
        try:
            if action == 'reveal':
                board = GameEngine.reveal_cell(board, row, col, mine_count)
            elif action == 'flag':
                board = GameEngine.toggle_flag(board, row, col)
            elif action == 'chord':
                board = GameEngine.chord_reveal(board, row, col)
            elif action == 'clue':
                if guest_data['clues_remaining'] <= 0:
                    return Response(
                        {"detail": "No clues remaining for this level."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                board = GameEngine.apply_clue(board, row, col, mine_count)
                guest_data['clues_remaining'] -= 1
            else:
                return Response(
                    {"detail": f"Unknown action: {action}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update guest session data
        guest_data['board_state'] = board
        guest_data['cells_revealed'] = len(board.get('revealed', []))
        guest_data['flags_placed'] = len(board.get('flagged', []))
        
        # Check for game over
        if board.get('game_over', False):
            won = board.get('won', False)
            guest_data['status'] = 'won' if won else 'lost'
            guest_data['is_active'] = won  # Keep active if won for next level
            
            # Calculate score (for display only, not saved)
            clues_per_level = getattr(settings, 'ROGUESWEEPER_CLUES_PER_LEVEL', 1)
            clues_used = clues_per_level - guest_data['clues_remaining']
            level_score = GameEngine.calculate_score(
                level=guest_data['level_number'],
                cells_revealed=guest_data['cells_revealed'],
                time_elapsed=guest_data['time_elapsed'],
                clues_used=clues_used,
                won=won
            )
            guest_data['score'] += level_score
        
        save_guest_session_data(request, guest_data)
        return Response(self._format_guest_response(guest_data), status=status.HTTP_200_OK)
    
    def _format_guest_response(self, guest_data: dict) -> dict:
        """Format guest session data for API response."""
        board = guest_data.get('board_state', {})
        rows = board.get('rows', getattr(settings, 'ROGUESWEEPER_BASE_ROWS', 8))
        cols = board.get('cols', getattr(settings, 'ROGUESWEEPER_BASE_COLS', 8))
        
        return {
            'id': guest_data['id'],
            'level_number': guest_data['level_number'],
            'score': guest_data['score'],
            'clues_remaining': guest_data['clues_remaining'],
            'time_elapsed': guest_data['time_elapsed'],
            'cells_revealed': guest_data['cells_revealed'],
            'flags_placed': guest_data['flags_placed'],
            'is_active': guest_data['is_active'],
            'status': guest_data['status'],
            'board': GameEngine.render_for_frontend(board) if board.get('initialized') else {
                'rows': rows,
                'cols': cols,
                'cells': [['hidden'] * cols for _ in range(rows)],
                'game_over': False,
                'won': False,
            },
            'is_guest': True,
        }


class NextLevelView(APIView):
    """
    API endpoint to advance to the next level after winning.
    
    POST /api/game/next-level/
    
    Request Body:
        {
            "confirm": true
        }
    
    Response:
        - 200: Advanced to next level, returns updated session
        - 400: Cannot advance (game not won, etc.)
        - 404: No active session found
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def post(self, request: Request) -> Response:
        """
        Advance to the next level after winning the current one.
        """
        serializer = NextLevelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Handle guest users
        if is_guest_user(request):
            return self._handle_guest_next_level(request)
        
        player = request.user
        
        # Find the won session (might still be marked as "active" for progression)
        session = GameSession.objects.filter(
            player=player,
            status=GameSession.SessionStatus.WON
        ).order_by('-updated_at').first()
        
        if not session:
            return Response(
                {"detail": "No won game session found. Win a level first."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Advance to next level
        session.advance_to_next_level()
        session.status = GameSession.SessionStatus.ACTIVE
        session.is_active = True
        session.save()
        
        # Update player's current level
        player.current_level = session.level_number
        player.save(update_fields=['current_level', 'updated_at'])
        
        response_serializer = GameSessionSerializer(session)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def _handle_guest_next_level(self, request: Request) -> Response:
        """Handle next level for guest users."""
        guest_data = get_guest_session_data(request)
        
        if guest_data.get('status') != 'won':
            return Response(
                {"detail": "No won game session found. Win a level first."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Advance to next level
        new_level = guest_data['level_number'] + 1
        guest_data['level_number'] = new_level
        guest_data['clues_remaining'] = get_clues_for_level(new_level)
        guest_data['time_elapsed'] = 0
        guest_data['cells_revealed'] = 0
        guest_data['flags_placed'] = 0
        guest_data['board_state'] = {}
        guest_data['is_active'] = True
        guest_data['status'] = 'active'
        
        save_guest_session_data(request, guest_data)
        return Response(self._format_guest_response(guest_data), status=status.HTTP_200_OK)
    
    def _format_guest_response(self, guest_data: dict) -> dict:
        """Format guest session data for API response."""
        board = guest_data.get('board_state', {})
        level = guest_data['level_number']
        
        base_rows = getattr(settings, 'ROGUESWEEPER_BASE_ROWS', 8)
        base_cols = getattr(settings, 'ROGUESWEEPER_BASE_COLS', 8)
        row_inc = getattr(settings, 'ROGUESWEEPER_ROW_INCREMENT', 1)
        col_inc = getattr(settings, 'ROGUESWEEPER_COL_INCREMENT', 1)
        max_rows = getattr(settings, 'ROGUESWEEPER_MAX_ROWS', 30)
        max_cols = getattr(settings, 'ROGUESWEEPER_MAX_COLS', 30)
        
        rows = min(base_rows + (level - 1) * row_inc, max_rows)
        cols = min(base_cols + (level - 1) * col_inc, max_cols)
        
        return {
            'id': guest_data['id'],
            'level_number': level,
            'score': guest_data['score'],
            'clues_remaining': guest_data['clues_remaining'],
            'clues_total': get_clues_for_level(level),
            'time_elapsed': guest_data['time_elapsed'],
            'cells_revealed': guest_data['cells_revealed'],
            'flags_placed': guest_data['flags_placed'],
            'is_active': guest_data['is_active'],
            'status': guest_data['status'],
            'board': GameEngine.render_for_frontend(board) if board.get('initialized') else {
                'rows': rows,
                'cols': cols,
                'cells': [['hidden'] * cols for _ in range(rows)],
                'game_over': False,
                'won': False,
            },
            'is_guest': True,
        }


class UpdateTimeView(APIView):
    """
    API endpoint to update the elapsed time for a session.
    
    POST /api/game/update-time/
    
    Request Body:
        {
            "time_elapsed": 125  // Time in seconds
        }
    
    This is called periodically by the frontend to track game duration.
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def post(self, request: Request) -> Response:
        """
        Update the elapsed time for the active session.
        """
        time_elapsed = request.data.get('time_elapsed')
        
        if time_elapsed is None or not isinstance(time_elapsed, int):
            return Response(
                {"detail": "time_elapsed must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if time_elapsed < 0:
            return Response(
                {"detail": "time_elapsed cannot be negative."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle guest users
        if is_guest_user(request):
            guest_data = get_guest_session_data(request)
            if guest_data.get('is_active'):
                guest_data['time_elapsed'] = time_elapsed
                save_guest_session_data(request, guest_data)
            return Response({"time_elapsed": time_elapsed}, status=status.HTTP_200_OK)
        
        # Handle authenticated users
        player = request.user
        session = GameSession.get_active_session(player)
        
        if not session:
            return Response(
                {"detail": "No active game session found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        session.time_elapsed = time_elapsed
        session.save(update_fields=['time_elapsed', 'updated_at'])
        
        return Response({"time_elapsed": session.time_elapsed}, status=status.HTTP_200_OK)


class LeaderboardView(APIView):
    """
    API endpoint to retrieve the global leaderboard.
    
    GET /api/game/leaderboard/
    
    Query Parameters:
        limit: Maximum number of entries to return (default: 10, max: 100)
    
    Response:
        - 200: Returns list of top scores
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def get(self, request: Request) -> Response:
        """
        Get the top scores leaderboard.
        """
        limit = request.query_params.get('limit', 10)
        
        try:
            limit = int(limit)
            limit = min(max(1, limit), 100)  # Clamp between 1 and 100
        except (ValueError, TypeError):
            limit = 10
        
        top_scores = Score.get_leaderboard(limit=limit)
        
        # Build leaderboard entries with rank
        leaderboard_data = []
        for rank, score in enumerate(top_scores, start=1):
            leaderboard_data.append({
                'rank': rank,
                'player_name': str(score.player),
                'final_score': score.final_score,
                'level_reached': score.level_reached,
                'time_taken': score.time_taken,
                'completed_at': score.completed_at,
            })
        
        serializer = LeaderboardSerializer(leaderboard_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PlayerStatsView(APIView):
    """
    API endpoint to retrieve player statistics.
    
    GET /api/game/stats/
    
    Response:
        - 200: Returns player stats and best score
        - 403: Guest users cannot view stats
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request: Request) -> Response:
        """
        Get the current player's statistics.
        
        Note: This endpoint requires authentication. Guest users
        cannot view stats since their data isn't saved.
        """
        player = request.user
        best_score = Score.get_player_best(player)
        
        player_data = PlayerSerializer(player).data
        
        response_data = {
            'player': player_data,
            'best_score': ScoreSerializer(best_score).data if best_score else None,
            'recent_scores': ScoreSerializer(
                Score.objects.filter(player=player).order_by('-completed_at')[:5],
                many=True
            ).data,
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class SaveProgressView(APIView):
    """
    API endpoint to save the current game progress for logged-in users.
    
    POST /api/save-progress/
    
    This saves the player's current level and updates high score if applicable.
    Only available for authenticated (non-guest) users.
    
    Response:
        - 200: Progress saved successfully
        - 401: User must be logged in
        - 404: No active session found
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def post(self, request: Request) -> Response:
        """
        Save the current game progress.
        """
        # Guest users cannot save progress
        if is_guest_user(request):
            return Response(
                {"detail": "You must be logged in to save progress."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get authenticated user's active session
        player = request.user
        session = GameSession.get_active_session(player)
        
        if not session:
            return Response(
                {"detail": "No active game session found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Save current level to player
        player.current_level = session.level_number
        
        # Update high score if current score is higher
        score_updated = player.update_high_score(session.score)
        
        player.save(update_fields=['current_level', 'updated_at'])
        
        return Response({
            "detail": "Progress saved successfully.",
            "level": session.level_number,
            "score": session.score,
            "high_score": player.high_score,
            "high_score_updated": score_updated
        }, status=status.HTTP_200_OK)


class AbandonGameView(APIView):
    """
    API endpoint to abandon the current game session.
    
    POST /api/game/abandon/
    
    Response:
        - 200: Game abandoned successfully
        - 404: No active session to abandon
    """
    
    permission_classes = [IsAuthenticatedOrGuest]
    
    def post(self, request: Request) -> Response:
        """
        Abandon the current active game session.
        """
        # Handle guest users
        if is_guest_user(request):
            guest_data = get_guest_session_data(request)
            if not guest_data.get('is_active'):
                return Response(
                    {"detail": "No active game session to abandon."},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Reset guest session (no score saved for guests)
            guest_data['is_active'] = False
            guest_data['status'] = 'abandoned'
            if guest_data.get('board_state'):
                guest_data['board_state']['game_over'] = True
                guest_data['board_state']['won'] = False
            save_guest_session_data(request, guest_data)
            return Response(
                {"detail": "Game abandoned successfully."},
                status=status.HTTP_200_OK
            )
        
        # Handle authenticated users
        player = request.user
        session = GameSession.get_active_session(player)
        
        if not session:
            return Response(
                {"detail": "No active game session to abandon."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Mark as abandoned and create score record
        session.status = GameSession.SessionStatus.ABANDONED
        session.is_active = False
        session.board_state['game_over'] = True
        session.board_state['won'] = False
        session.save()
        
        # Create score record for the abandoned game
        Score.create_from_session(session)
        
        return Response(
            {"detail": "Game abandoned successfully."},
            status=status.HTTP_200_OK
        )
