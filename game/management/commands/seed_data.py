"""
Seed Data Management Command

This command populates the database with sample players and scores
for testing and demonstration purposes.

Usage:
    python manage.py seed_data
    python manage.py seed_data --force  # Override existing data

Author: RogueSweeper Team
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.models import Player, Score


class Command(BaseCommand):
    """
    Django management command to seed the database with sample data.
    
    Creates dummy players and score entries to populate the leaderboard
    for testing and demonstration purposes.
    """
    
    help = 'Seeds the database with sample players and scores for the leaderboard.'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force seeding even if data already exists.',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        force = options['force']
        
        # Check if data already exists
        if Score.objects.exists() and not force:
            self.stdout.write(
                self.style.WARNING('Data already exists. Use --force to override.')
            )
            return
        
        if force:
            self.stdout.write(self.style.WARNING('Force mode: Clearing existing seed data...'))
            # Only delete non-guest, non-staff players (seed data)
            seed_usernames = [
                'RogueMaster', 'SweeperKing', 'MineHunter', 'BombDefuser',
                'GridWarrior', 'FlagMaster', 'SafeCell', 'ClueWizard',
                'LevelCrusher', 'ScoreChaser'
            ]
            Player.objects.filter(username__in=seed_usernames).delete()
        
        self.stdout.write(self.style.NOTICE('Seeding database...'))
        
        # Create sample players
        players_data = [
            {'username': 'RogueMaster', 'high_score': 15000, 'total_games_played': 50, 'total_games_won': 35},
            {'username': 'SweeperKing', 'high_score': 12500, 'total_games_played': 45, 'total_games_won': 30},
            {'username': 'MineHunter', 'high_score': 10000, 'total_games_played': 40, 'total_games_won': 25},
            {'username': 'BombDefuser', 'high_score': 8500, 'total_games_played': 35, 'total_games_won': 20},
            {'username': 'GridWarrior', 'high_score': 7000, 'total_games_played': 30, 'total_games_won': 18},
            {'username': 'FlagMaster', 'high_score': 6000, 'total_games_played': 28, 'total_games_won': 15},
            {'username': 'SafeCell', 'high_score': 5000, 'total_games_played': 25, 'total_games_won': 12},
            {'username': 'ClueWizard', 'high_score': 4000, 'total_games_played': 20, 'total_games_won': 10},
            {'username': 'LevelCrusher', 'high_score': 3000, 'total_games_played': 15, 'total_games_won': 8},
            {'username': 'ScoreChaser', 'high_score': 2000, 'total_games_played': 10, 'total_games_won': 5},
        ]
        
        created_players = []
        for player_data in players_data:
            player, created = Player.objects.get_or_create(
                username=player_data['username'],
                defaults={
                    'high_score': player_data['high_score'],
                    'total_games_played': player_data['total_games_played'],
                    'total_games_won': player_data['total_games_won'],
                    'is_guest': False,
                }
            )
            if created:
                self.stdout.write(f'  Created player: {player.username}')
            else:
                # Update existing player stats
                player.high_score = player_data['high_score']
                player.total_games_played = player_data['total_games_played']
                player.total_games_won = player_data['total_games_won']
                player.save()
                self.stdout.write(f'  Updated player: {player.username}')
            created_players.append(player)
        
        # Create sample scores for leaderboard
        scores_data = [
            # (player_index, level_reached, final_score, time_taken, cells_revealed, clues_used, was_victory)
            (0, 12, 15000, 1800, 450, 8, True),   # RogueMaster - best run
            (0, 10, 12000, 1500, 380, 6, True),   # RogueMaster - second best
            (1, 11, 12500, 1650, 420, 7, True),   # SweeperKing - best run
            (1, 9, 9500, 1400, 340, 5, False),    # SweeperKing - lost on level 9
            (2, 10, 10000, 1550, 390, 6, True),   # MineHunter - best run
            (2, 8, 7500, 1200, 300, 4, True),     # MineHunter - earlier run
            (3, 9, 8500, 1350, 320, 5, True),     # BombDefuser - best run
            (4, 8, 7000, 1250, 280, 4, True),     # GridWarrior - best run
            (5, 7, 6000, 1100, 250, 3, True),     # FlagMaster - best run
            (6, 6, 5000, 950, 220, 3, True),      # SafeCell - best run
            (7, 5, 4000, 800, 180, 2, True),      # ClueWizard - best run
            (8, 4, 3000, 650, 140, 2, True),      # LevelCrusher - best run
            (9, 3, 2000, 500, 100, 1, True),      # ScoreChaser - best run
            (9, 2, 1200, 350, 70, 1, False),      # ScoreChaser - early loss
        ]
        
        scores_created = 0
        for player_idx, level, score, time, cells, clues, victory in scores_data:
            player = created_players[player_idx]
            
            # Check if similar score already exists
            existing = Score.objects.filter(
                player=player,
                level_reached=level,
                final_score=score
            ).exists()
            
            if not existing:
                Score.objects.create(
                    player=player,
                    level_reached=level,
                    final_score=score,
                    time_taken=time,
                    cells_revealed_total=cells,
                    clues_used=clues,
                    was_victory=victory,
                    completed_at=timezone.now()
                )
                scores_created += 1
        
        self.stdout.write(f'  Created {scores_created} score entries')
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSeeding complete! Created {len(created_players)} players and {scores_created} scores.')
        )
