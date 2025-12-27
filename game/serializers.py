"""
RogueSweeper API Serializers

This module contains Django REST Framework serializers for the game API.
Serializers handle validation of incoming data and sanitization of
outgoing data to prevent cheating.

Author: RogueSweeper Team
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .engine import GameEngine
from .models import GameSession, Player, Score, get_clues_for_level


class GameActionSerializer(serializers.Serializer):
    """
    Serializer for validating game action inputs.
    
    Used to validate move requests from the frontend including
    cell reveals, flag toggles, chord reveals, and clue usage.
    
    Fields:
        row: Row index of the target cell (0-indexed).
        col: Column index of the target cell (0-indexed).
        action: The type of action to perform.
    """
    
    ACTION_CHOICES = [
        ('reveal', 'Reveal cell'),
        ('flag', 'Toggle flag'),
        ('chord', 'Chord reveal'),
        ('clue', 'Use clue power-up'),
    ]
    
    row = serializers.IntegerField(
        min_value=0,
        help_text="Row index of the target cell (0-indexed)."
    )
    col = serializers.IntegerField(
        min_value=0,
        help_text="Column index of the target cell (0-indexed)."
    )
    action = serializers.ChoiceField(
        choices=ACTION_CHOICES,
        help_text="The type of action to perform on the cell."
    )
    
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validate that coordinates are within board bounds.
        
        The actual bounds check happens in the view where we have
        access to the board dimensions.
        """
        if attrs['row'] < 0 or attrs['col'] < 0:
            raise serializers.ValidationError(
                "Row and column must be non-negative integers."
            )
        return attrs


class GameSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for outputting game session state.
    
    Provides a sanitized view of the game session, ensuring that
    mine locations are hidden from the client to prevent cheating.
    
    Fields:
        id: Unique session identifier.
        level_number: Current level in the run.
        clues_remaining: Number of clue power-ups available.
        score: Current accumulated score.
        status: Session status (active, paused, won, lost, abandoned).
        time_elapsed: Total time elapsed in seconds.
        board: Sanitized board representation (mines hidden).
        created_at: When the session was created.
        updated_at: When the session was last modified.
    """
    
    board = serializers.SerializerMethodField(
        help_text="Sanitized board state with mines hidden."
    )
    clues_total = serializers.SerializerMethodField(
        help_text="Total clues available for this level."
    )
    
    class Meta:
        model = GameSession
        fields = [
            'id',
            'level_number',
            'clues_remaining',
            'clues_total',
            'score',
            'status',
            'time_elapsed',
            'cells_revealed',
            'flags_placed',
            'board',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_clues_total(self, obj: GameSession) -> int:
        """Get total clues available for the current level."""
        return get_clues_for_level(obj.level_number)
    
    def get_board(self, obj: GameSession) -> dict[str, Any]:
        """
        Get sanitized board representation for the frontend.
        
        Uses GameEngine.render_for_frontend() to ensure mine
        locations are hidden unless the game is over.
        
        Args:
            obj: The GameSession instance.
        
        Returns:
            Sanitized board dictionary safe for client consumption.
        """
        if not obj.board_state:
            # Return empty board structure if not initialized
            rows, cols = obj.calculate_grid_size()
            return {
                "rows": rows,
                "cols": cols,
                "cells": [["hidden"] * cols for _ in range(rows)],
                "game_over": False,
                "won": False,
                "flags_count": 0,
                "mines_count": obj.calculate_mine_count(),
                "revealed_count": 0,
                "initialized": False,
            }
        
        # Use GameEngine to sanitize the board
        return GameEngine.render_for_frontend(obj.board_state)


class ScoreSerializer(serializers.ModelSerializer):
    """
    Serializer for score records.
    
    Used for leaderboards and player statistics.
    """
    
    player_name = serializers.SerializerMethodField(
        help_text="Display name of the player."
    )
    
    class Meta:
        model = Score
        fields = [
            'id',
            'player_name',
            'level_reached',
            'final_score',
            'time_taken',
            'cells_revealed_total',
            'clues_used',
            'was_victory',
            'completed_at',
        ]
        read_only_fields = fields
    
    def get_player_name(self, obj: Score) -> str:
        """Get the display name of the player."""
        return str(obj.player)


class PlayerSerializer(serializers.ModelSerializer):
    """
    Serializer for player profile information.
    """
    
    class Meta:
        model = Player
        fields = [
            'id',
            'username',
            'current_level',
            'high_score',
            'total_games_played',
            'total_games_won',
            'preferred_language',
            'is_guest',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'current_level',
            'high_score',
            'total_games_played',
            'total_games_won',
            'created_at',
        ]


class LeaderboardSerializer(serializers.Serializer):
    """
    Serializer for leaderboard entries.
    """
    
    rank = serializers.IntegerField(help_text="Position on the leaderboard.")
    player_name = serializers.CharField(help_text="Player display name.")
    final_score = serializers.IntegerField(help_text="Score achieved.")
    level_reached = serializers.IntegerField(help_text="Highest level reached.")
    time_taken = serializers.IntegerField(help_text="Time taken in seconds.")
    completed_at = serializers.DateTimeField(help_text="When the run was completed.")


class StartGameSerializer(serializers.Serializer):
    """
    Serializer for start game request.
    
    Optional field to force starting a new game even if one exists.
    """
    
    force_new = serializers.BooleanField(
        default=False,
        required=False,
        help_text="If True, abandons any existing session and starts fresh."
    )


class NextLevelSerializer(serializers.Serializer):
    """
    Serializer for advancing to the next level.
    """
    
    confirm = serializers.BooleanField(
        default=True,
        help_text="Confirm advancing to the next level."
    )
