"""
RogueSweeper Game API URLs

This module defines the URL routing for the game API endpoints.

Author: RogueSweeper Team
"""

from django.urls import path

from .auth_views import (
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    SignUpView,
)
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
    
    # Authentication views
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
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
