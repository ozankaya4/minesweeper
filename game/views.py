"""
RogueSweeper API Views

This module contains Django REST Framework views for the game API.
Views handle game session management, action processing, and
score tracking.

Author: RogueSweeper Team
"""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.views import View
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


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
        request.session[translation.LANGUAGE_SESSION_KEY] = language_code
        
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
from .models import GameSession, Player, Score
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
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request) -> Response:
        """
        Start a new game or return existing active session.
        
        If the user has an active session and force_new is False,
        returns the existing session. Otherwise, creates a new one.
        """
        serializer = StartGameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        force_new = serializer.validated_data.get('force_new', False)
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
            clues_remaining=getattr(settings, 'ROGUESWEEPER_CLUES_PER_LEVEL', 1),
            status=GameSession.SessionStatus.ACTIVE,
            is_active=True,
        )
        
        # Increment player's games played counter
        player.increment_games_played()
        
        response_serializer = GameSessionSerializer(new_session)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class GameSessionView(APIView):
    """
    API endpoint to retrieve the current game session state.
    
    GET /api/game/session/
    
    Response:
        - 200: Returns current active session
        - 404: No active session found
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request: Request) -> Response:
        """
        Get the current active game session.
        """
        player = request.user
        active_session = GameSession.get_active_session(player)
        
        if not active_session:
            return Response(
                {"detail": "No active game session found. Start a new game."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = GameSessionSerializer(active_session)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
    
    permission_classes = [IsAuthenticated]
    
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
        
        # Get active session
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
            clues_per_level = getattr(settings, 'ROGUESWEEPER_CLUES_PER_LEVEL', 1)
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
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request) -> Response:
        """
        Advance to the next level after winning the current one.
        """
        serializer = NextLevelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
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
    
    permission_classes = [IsAuthenticated]
    
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
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request: Request) -> Response:
        """
        Get the current player's statistics.
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


class AbandonGameView(APIView):
    """
    API endpoint to abandon the current game session.
    
    POST /api/game/abandon/
    
    Response:
        - 200: Game abandoned successfully
        - 404: No active session to abandon
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request) -> Response:
        """
        Abandon the current active game session.
        """
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
