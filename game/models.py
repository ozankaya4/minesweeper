"""
RogueSweeper Game Models

This module contains the core database models for the RogueSweeper game:
- Player: Custom user model extending AbstractUser with game-specific fields
- GameSession: Represents an active game run with board state persistence
- Score: Historical record of completed game runs

Author: RogueSweeper Team
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Player(AbstractUser):
    """
    Custom User model for RogueSweeper players.
    
    Extends Django's AbstractUser to include game-specific fields
    for tracking player progress and identifying guest accounts.
    
    Attributes:
        current_level: The highest level the player has reached in their current run.
        high_score: The player's all-time highest score across all runs.
        is_guest: Flag indicating if this is a temporary guest account.
        preferred_language: Player's preferred language for i18n (en/tr).
        created_at: Timestamp when the player account was created.
        updated_at: Timestamp when the player account was last modified.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for the player.")
    )
    
    current_level = models.PositiveIntegerField(
        default=1,
        help_text=_("Current level in the active run.")
    )
    
    high_score = models.PositiveIntegerField(
        default=0,
        help_text=_("All-time highest score achieved.")
    )
    
    is_guest = models.BooleanField(
        default=False,
        help_text=_("Whether this is a temporary guest account.")
    )
    
    preferred_language = models.CharField(
        max_length=5,
        choices=[('en', 'English'), ('tr', 'Türkçe')],
        default='en',
        help_text=_("Preferred language for the game interface.")
    )
    
    total_games_played = models.PositiveIntegerField(
        default=0,
        help_text=_("Total number of game runs started.")
    )
    
    total_games_won = models.PositiveIntegerField(
        default=0,
        help_text=_("Total number of levels successfully completed.")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when account was created.")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when account was last updated.")
    )
    
    class Meta:
        verbose_name = _("Player")
        verbose_name_plural = _("Players")
        ordering = ['-high_score', '-current_level']
    
    def __str__(self) -> str:
        """Return string representation of the player."""
        if self.is_guest:
            return f"Guest ({str(self.id)[:8]})"
        return self.username
    
    def update_high_score(self, score: int) -> bool:
        """
        Update the player's high score if the new score is higher.
        
        Args:
            score: The new score to compare against the current high score.
            
        Returns:
            True if the high score was updated, False otherwise.
        """
        if score > self.high_score:
            self.high_score = score
            self.save(update_fields=['high_score', 'updated_at'])
            return True
        return False
    
    def increment_games_played(self) -> None:
        """Increment the total games played counter."""
        self.total_games_played += 1
        self.save(update_fields=['total_games_played', 'updated_at'])
    
    def increment_games_won(self) -> None:
        """Increment the total games won counter."""
        self.total_games_won += 1
        self.save(update_fields=['total_games_won', 'updated_at'])


class GameSession(models.Model):
    """
    Represents an active game session/run.
    
    Stores the complete state of a game in progress, allowing players
    to save and resume their roguelike runs. Each session tracks the
    board state, current level, and available power-ups.
    
    Attributes:
        player: The player who owns this session.
        board_state: JSON representation of the game board including mines,
                    revealed cells, flags, and adjacent mine counts.
        level_number: Current level in this run (1-indexed).
        clues_remaining: Number of "Clue" power-ups available this level.
        score: Accumulated score for this run.
        is_active: Whether this session is currently in progress.
        is_paused: Whether the game is paused (for save/resume).
        time_elapsed: Total time spent on this run in seconds.
        created_at: When this session was started.
        updated_at: When this session was last modified.
    
    Board State Structure:
        {
            "rows": int,
            "cols": int,
            "mines": [[row, col], ...],  # Mine positions
            "revealed": [[row, col], ...],  # Revealed cell positions
            "flagged": [[row, col], ...],  # Flagged cell positions
            "adjacent_counts": {  # Pre-calculated adjacent mine counts
                "row,col": int,
                ...
            },
            "game_over": bool,
            "won": bool
        }
    """
    
    class SessionStatus(models.TextChoices):
        """Enum for game session status."""
        ACTIVE = 'active', _('Active')
        PAUSED = 'paused', _('Paused')
        WON = 'won', _('Won')
        LOST = 'lost', _('Lost')
        ABANDONED = 'abandoned', _('Abandoned')
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for the game session.")
    )
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='game_sessions',
        help_text=_("The player who owns this session.")
    )
    
    board_state = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("JSON representation of the game board state.")
    )
    
    level_number = models.PositiveIntegerField(
        default=1,
        help_text=_("Current level number in this run.")
    )
    
    clues_remaining = models.PositiveIntegerField(
        default=1,
        help_text=_("Number of 'Clue' power-ups remaining for this level.")
    )
    
    score = models.PositiveIntegerField(
        default=0,
        help_text=_("Accumulated score for this run.")
    )
    
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
        help_text=_("Current status of the game session.")
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this session is currently active.")
    )
    
    time_elapsed = models.PositiveIntegerField(
        default=0,
        help_text=_("Total time elapsed in seconds.")
    )
    
    cells_revealed = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of cells revealed in this session.")
    )
    
    flags_placed = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of flags currently placed.")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when session was created.")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when session was last updated.")
    )
    
    class Meta:
        verbose_name = _("Game Session")
        verbose_name_plural = _("Game Sessions")
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['player', 'is_active']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self) -> str:
        """Return string representation of the session."""
        return f"Session {str(self.id)[:8]} - Level {self.level_number} ({self.status})"
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Override save to ensure board_state has a valid default structure.
        
        If board_state is empty or None, initializes it with the default
        empty board structure based on the current level.
        """
        if not self.board_state:
            self.board_state = self._get_default_board_state()
        super().save(*args, **kwargs)
    
    def _get_default_board_state(self) -> dict[str, Any]:
        """
        Generate the default empty board state structure.
        
        Returns:
            A dictionary representing an empty board with dimensions
            calculated based on the current level.
        """
        rows, cols = self.calculate_grid_size()
        return {
            "rows": rows,
            "cols": cols,
            "mines": [],
            "revealed": [],
            "flagged": [],
            "adjacent_counts": {},
            "game_over": False,
            "won": False,
            "initialized": False,  # Board not yet populated with mines
        }
    
    def calculate_grid_size(self) -> tuple[int, int]:
        """
        Calculate grid dimensions based on current level.
        
        Grid size increases with level number up to maximum limits
        defined in settings.
        
        Returns:
            Tuple of (rows, cols) for the grid.
        """
        base_rows = getattr(settings, 'ROGUESWEEPER_BASE_ROWS', 8)
        base_cols = getattr(settings, 'ROGUESWEEPER_BASE_COLS', 8)
        row_increment = getattr(settings, 'ROGUESWEEPER_ROW_INCREMENT', 1)
        col_increment = getattr(settings, 'ROGUESWEEPER_COL_INCREMENT', 1)
        max_rows = getattr(settings, 'ROGUESWEEPER_MAX_ROWS', 30)
        max_cols = getattr(settings, 'ROGUESWEEPER_MAX_COLS', 30)
        
        rows = min(base_rows + (self.level_number - 1) * row_increment, max_rows)
        cols = min(base_cols + (self.level_number - 1) * col_increment, max_cols)
        
        return rows, cols
    
    def calculate_mine_count(self) -> int:
        """
        Calculate number of mines based on current level.
        
        Mine count increases with level number, scaled to grid size.
        
        Returns:
            Number of mines for this level.
        """
        base_mines = getattr(settings, 'ROGUESWEEPER_BASE_MINES', 10)
        mine_increment = getattr(settings, 'ROGUESWEEPER_MINE_INCREMENT', 2)
        
        rows, cols = self.calculate_grid_size()
        max_mines = (rows * cols) // 4  # Max 25% of cells can be mines
        
        mines = base_mines + (self.level_number - 1) * mine_increment
        return min(mines, max_mines)
    
    def advance_to_next_level(self) -> None:
        """
        Advance the session to the next level.
        
        Increments level number, resets clues, and initializes
        a new empty board state for the next level.
        """
        self.level_number += 1
        self.clues_remaining = getattr(settings, 'ROGUESWEEPER_CLUES_PER_LEVEL', 1)
        self.board_state = self._get_default_board_state()
        self.cells_revealed = 0
        self.flags_placed = 0
        self.save()
    
    def use_clue(self) -> bool:
        """
        Use one clue power-up if available.
        
        Returns:
            True if clue was used, False if no clues remaining.
        """
        if self.clues_remaining > 0:
            self.clues_remaining -= 1
            self.save(update_fields=['clues_remaining', 'updated_at'])
            return True
        return False
    
    def end_session(self, won: bool = False) -> None:
        """
        End the current game session.
        
        Args:
            won: Whether the player won (completed the level) or lost.
        """
        self.is_active = False
        self.status = self.SessionStatus.WON if won else self.SessionStatus.LOST
        
        if self.board_state:
            self.board_state['game_over'] = True
            self.board_state['won'] = won
        
        self.save()
    
    @classmethod
    def get_active_session(cls, player: Player) -> Optional['GameSession']:
        """
        Get the active session for a player, if one exists.
        
        Args:
            player: The player to find an active session for.
            
        Returns:
            The active GameSession or None if no active session exists.
        """
        return cls.objects.filter(
            player=player,
            is_active=True,
            status=cls.SessionStatus.ACTIVE
        ).first()


class Score(models.Model):
    """
    Historical record of completed game runs.
    
    Stores the final results of each game run for leaderboards
    and player statistics.
    
    Attributes:
        player: The player who achieved this score.
        session: Optional reference to the original game session.
        level_reached: The highest level reached in this run.
        final_score: The total score achieved.
        time_taken: Total time spent on this run in seconds.
        cells_revealed_total: Total cells revealed across all levels.
        clues_used: Total clues used during the run.
        completed_at: When this run was completed.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for the score record.")
    )
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='scores',
        help_text=_("The player who achieved this score.")
    )
    
    session = models.OneToOneField(
        GameSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='final_score',
        help_text=_("Reference to the original game session.")
    )
    
    level_reached = models.PositiveIntegerField(
        default=1,
        db_index=True,
        help_text=_("Highest level reached in this run.")
    )
    
    final_score = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text=_("Total score achieved in this run.")
    )
    
    time_taken = models.PositiveIntegerField(
        default=0,
        help_text=_("Total time taken in seconds.")
    )
    
    cells_revealed_total = models.PositiveIntegerField(
        default=0,
        help_text=_("Total cells revealed across all levels.")
    )
    
    clues_used = models.PositiveIntegerField(
        default=0,
        help_text=_("Total clues used during the run.")
    )
    
    was_victory = models.BooleanField(
        default=False,
        help_text=_("Whether the run ended in victory (vs game over).")
    )
    
    completed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("Timestamp when this run was completed.")
    )
    
    class Meta:
        verbose_name = _("Score")
        verbose_name_plural = _("Scores")
        ordering = ['-final_score', '-level_reached', 'time_taken']
        indexes = [
            models.Index(fields=['player', '-final_score']),
            models.Index(fields=['-final_score', '-level_reached']),
        ]
    
    def __str__(self) -> str:
        """Return string representation of the score."""
        return f"{self.player} - Level {self.level_reached} - Score: {self.final_score}"
    
    @classmethod
    def create_from_session(cls, session: GameSession) -> 'Score':
        """
        Create a Score record from a completed GameSession.
        
        Args:
            session: The completed game session to record.
            
        Returns:
            The newly created Score instance.
        """
        # Calculate clues used (total possible - remaining at end)
        total_clues = session.level_number * getattr(
            settings, 'ROGUESWEEPER_CLUES_PER_LEVEL', 1
        )
        clues_used = total_clues - session.clues_remaining
        
        score = cls.objects.create(
            player=session.player,
            session=session,
            level_reached=session.level_number,
            final_score=session.score,
            time_taken=session.time_elapsed,
            cells_revealed_total=session.cells_revealed,
            clues_used=max(0, clues_used),
            was_victory=(session.status == GameSession.SessionStatus.WON),
        )
        
        # Update player's high score if applicable
        session.player.update_high_score(session.score)
        
        return score
    
    @classmethod
    def get_leaderboard(cls, limit: int = 10) -> models.QuerySet:
        """
        Get the top scores for the leaderboard.
        
        Args:
            limit: Maximum number of scores to return.
            
        Returns:
            QuerySet of top Score records.
        """
        return cls.objects.select_related('player').order_by(
            '-final_score', '-level_reached', 'time_taken'
        )[:limit]
    
    @classmethod
    def get_player_best(cls, player: Player) -> Optional['Score']:
        """
        Get a player's best score.
        
        Args:
            player: The player to get the best score for.
            
        Returns:
            The player's highest Score or None if no scores exist.
        """
        return cls.objects.filter(player=player).order_by(
            '-final_score', '-level_reached'
        ).first()
