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
    HomeView,
    LeaderboardView,
    NextLevelView,
    PlayerStatsView,
    StartGameView,
    SwitchLanguageView,
    UpdateTimeView,
)

app_name = 'game'

urlpatterns = [
    # Template views
    path('', HomeView.as_view(), name='index'),
    path('switch-language/', SwitchLanguageView.as_view(), name='switch-language'),
    
    # Game session management
    path('api/start/', StartGameView.as_view(), name='start-game'),
    path('api/session/', GameSessionView.as_view(), name='game-session'),
    path('api/abandon/', AbandonGameView.as_view(), name='abandon-game'),
    
    # Game actions
    path('api/action/', GameActionView.as_view(), name='game-action'),
    path('api/next-level/', NextLevelView.as_view(), name='next-level'),
    path('api/update-time/', UpdateTimeView.as_view(), name='update-time'),
    
    # Stats and leaderboard
    path('api/leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('api/stats/', PlayerStatsView.as_view(), name='player-stats'),
]
