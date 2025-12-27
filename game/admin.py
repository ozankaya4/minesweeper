"""
Django Admin configuration for RogueSweeper game models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import GameSession, Player, Score


@admin.register(Player)
class PlayerAdmin(UserAdmin):
    """Admin configuration for the Player model."""
    
    list_display = (
        'username', 'email', 'high_score', 'current_level',
        'is_guest', 'total_games_played', 'is_active'
    )
    list_filter = ('is_guest', 'is_staff', 'is_active', 'preferred_language')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-high_score', '-date_joined')
    
    fieldsets = UserAdmin.fieldsets + (
        (_('Game Stats'), {
            'fields': (
                'current_level', 'high_score', 'is_guest',
                'preferred_language', 'total_games_played', 'total_games_won'
            )
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Game Stats'), {
            'fields': ('is_guest', 'preferred_language')
        }),
    )


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    """Admin configuration for the GameSession model."""
    
    list_display = (
        'id', 'player', 'level_number', 'score',
        'status', 'is_active', 'created_at'
    )
    list_filter = ('status', 'is_active', 'level_number')
    search_fields = ('player__username', 'id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-updated_at',)
    
    fieldsets = (
        (None, {
            'fields': ('id', 'player', 'status', 'is_active')
        }),
        (_('Game State'), {
            'fields': (
                'level_number', 'score', 'clues_remaining',
                'time_elapsed', 'cells_revealed', 'flags_placed'
            )
        }),
        (_('Board'), {
            'fields': ('board_state',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    """Admin configuration for the Score model."""
    
    list_display = (
        'player', 'final_score', 'level_reached',
        'time_taken', 'was_victory', 'completed_at'
    )
    list_filter = ('was_victory', 'level_reached')
    search_fields = ('player__username',)
    readonly_fields = ('id', 'completed_at')
    ordering = ('-final_score', '-level_reached')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'player', 'session')
        }),
        (_('Score Details'), {
            'fields': (
                'final_score', 'level_reached', 'time_taken',
                'cells_revealed_total', 'clues_used', 'was_victory'
            )
        }),
        (_('Timestamps'), {
            'fields': ('completed_at',),
        }),
    )
