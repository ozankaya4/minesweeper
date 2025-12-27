"""
RogueSweeper Project Setup Script

This script automates the first-time setup for developers.
Run this script after cloning the repository to set up the project.

Usage:
    python setup_project.py

Author: RogueSweeper Team
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """
    Run a command and print its status.
    
    Args:
        command: Command to run as a list of strings.
        description: Human-readable description of the command.
    
    Returns:
        True if command succeeded, False otherwise.
    """
    print(f"\n{'='*60}")
    print(f"📌 {description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(command)}\n")
    
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=False,
            text=True
        )
        print(f"✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED (exit code: {e.returncode})")
        return False
    except FileNotFoundError:
        print(f"❌ {description} - FAILED (command not found)")
        return False


def create_superuser():
    """
    Create a superuser if one doesn't exist.
    
    This function must be called after Django is configured.
    """
    print(f"\n{'='*60}")
    print("📌 Creating Superuser")
    print(f"{'='*60}")
    
    # Set up Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'roguesweeper.settings')
    
    import django
    django.setup()
    
    from game.models import Player
    
    admin_username = 'admin'
    admin_email = 'admin@example.com'
    admin_password = 'admin123'
    
    if Player.objects.filter(username=admin_username).exists():
        print(f"ℹ️  Superuser '{admin_username}' already exists. Skipping.")
        return True
    
    try:
        superuser = Player.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            is_guest=False
        )
        print(f"✅ Superuser created successfully!")
        print(f"   Username: {admin_username}")
        print(f"   Email: {admin_email}")
        print(f"   Password: {admin_password}")
        print(f"   ⚠️  IMPORTANT: Change this password in production!")
        return True
    except Exception as e:
        print(f"❌ Failed to create superuser: {e}")
        return False


def main():
    """Main setup function."""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   🎮 RogueSweeper Project Setup                               ║
    ║                                                               ║
    ║   This script will set up your development environment.       ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Get the directory where this script is located
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}\n")
    
    # Determine Python executable
    python_exe = sys.executable
    pip_exe = [python_exe, '-m', 'pip']
    
    # Track success/failure
    all_success = True
    
    # Step 1: Install requirements
    if not run_command(
        [*pip_exe, 'install', '-r', 'requirements.txt'],
        "Installing Python dependencies"
    ):
        print("\n⚠️  Failed to install dependencies. Continuing anyway...")
        # Don't fail completely, some deps might already be installed
    
    # Step 2: Make migrations
    if not run_command(
        [python_exe, 'manage.py', 'makemigrations', 'game'],
        "Creating database migrations"
    ):
        all_success = False
    
    # Step 3: Apply migrations
    if not run_command(
        [python_exe, 'manage.py', 'migrate'],
        "Applying database migrations"
    ):
        all_success = False
        print("\n❌ Migration failed. Cannot continue.")
        return 1
    
    # Step 4: Seed data
    if not run_command(
        [python_exe, 'manage.py', 'seed_data'],
        "Seeding database with sample data"
    ):
        print("\n⚠️  Seeding failed or data already exists. Continuing...")
    
    # Step 5: Create superuser
    if not create_superuser():
        print("\n⚠️  Superuser creation failed. You can create one manually with:")
        print("    python manage.py createsuperuser")
    
    # Step 6: Collect static files (optional for development)
    print(f"\n{'='*60}")
    print("📌 Static Files")
    print(f"{'='*60}")
    print("ℹ️  Static files collection skipped (not needed for development)")
    print("   Run 'python manage.py collectstatic' for production deployment.")
    
    # Final summary
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   ✅ Setup Complete!                                          ║
    ║                                                               ║
    ║   To start the development server, run:                       ║
    ║                                                               ║
    ║       python manage.py runserver                              ║
    ║                                                               ║
    ║   Then open http://127.0.0.1:8000 in your browser.            ║
    ║                                                               ║
    ║   Admin panel: http://127.0.0.1:8000/admin/                   ║
    ║   Username: admin | Password: admin123                        ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    return 0 if all_success else 1


if __name__ == '__main__':
    sys.exit(main())
