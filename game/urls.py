"""
RogueSweeper Game API URLs

This module defines the URL routing for the game API endpoints.

Author: RogueSweeper Team
"""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

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
    SaveProgressView,
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
    
    # Game session management (csrf_exempt for guest access)
    path('api/start/', csrf_exempt(StartGameView.as_view()), name='start-game'),
    path('api/session/', csrf_exempt(GameSessionView.as_view()), name='game-session'),
    path('api/abandon/', csrf_exempt(AbandonGameView.as_view()), name='abandon-game'),
    path('api/save-progress/', csrf_exempt(SaveProgressView.as_view()), name='save-progress'),
    
    # Game actions (csrf_exempt for guest access)
    path('api/action/', csrf_exempt(GameActionView.as_view()), name='game-action'),
    path('api/next-level/', csrf_exempt(NextLevelView.as_view()), name='next-level'),
    path('api/update-time/', csrf_exempt(UpdateTimeView.as_view()), name='update-time'),
    
    # Stats and leaderboard (csrf_exempt for guest access)
    path('api/leaderboard/', csrf_exempt(LeaderboardView.as_view()), name='leaderboard'),
    path('api/stats/', csrf_exempt(PlayerStatsView.as_view()), name='player-stats'),
]
