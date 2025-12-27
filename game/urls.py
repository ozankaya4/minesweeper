"""
RogueSweeper Game API URLs

This module defines the URL routing for the game API endpoints.

Author: RogueSweeper Team
"""

from django.urls import path

from .views import (
    AbandonGameView,
    GameActionView,
    GameSessionView,
    LeaderboardView,
    NextLevelView,
    PlayerStatsView,
    StartGameView,
    UpdateTimeView,
)

app_name = 'game'

urlpatterns = [
    # Game session management
    path('start/', StartGameView.as_view(), name='start-game'),
    path('session/', GameSessionView.as_view(), name='game-session'),
    path('abandon/', AbandonGameView.as_view(), name='abandon-game'),
    
    # Game actions
    path('action/', GameActionView.as_view(), name='game-action'),
    path('next-level/', NextLevelView.as_view(), name='next-level'),
    path('update-time/', UpdateTimeView.as_view(), name='update-time'),
    
    # Stats and leaderboard
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('stats/', PlayerStatsView.as_view(), name='player-stats'),
]
