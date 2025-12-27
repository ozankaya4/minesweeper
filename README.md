# 🎮 RogueSweeper

A roguelike Minesweeper game with infinite levels, progressive difficulty, and competitive leaderboards. Built with Django and vanilla JavaScript.

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 About

RogueSweeper combines classic Minesweeper mechanics with roguelike progression. Start with an 8×8 grid and work your way through increasingly challenging levels. Each level adds more rows, columns, and mines. How far can you go?

### Features

- **Infinite Levels** - Progressive difficulty with growing grid sizes and mine counts
- **Clue System** - Use clues to safely reveal cells (more clues at higher levels)
- **Chord Reveal** - Middle-click on numbered cells to reveal all neighbors at once
- **Guest Play** - Play immediately without registration
- **User Accounts** - Sign up to save your scores to the leaderboard
- **Password Reset** - Email-based password recovery via SendGrid
- **Leaderboards** - Compete for the highest scores
- **Bilingual** - Full support for English and Turkish (i18n)
- **Responsive Design** - Works on desktop and mobile

### Clue Distribution

| Level Range | Clues per Level |
|-------------|-----------------|
| 1-5         | 1 clue          |
| 6-10        | 2 clues         |
| 11-15       | 3 clues         |
| 16-20       | 4 clues         |
| 21+         | 5 clues         |

## 🚀 Getting Started

### Prerequisites

- Python 3.12 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ozankaya4/minesweeper.git
   cd minesweeper
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env with your settings (see Configuration section)
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Compile translations** (optional, for Turkish language support)
   ```bash
   python manage.py compilemessages
   ```

7. **Start the development server**
   ```bash
   python manage.py runserver
   ```

8. **Open your browser**
   ```
   http://localhost:8000
   ```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

```env
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite is used by default)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# SendGrid Email Configuration (required for password reset)
SENDGRID_API_KEY=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=your-verified-email@example.com
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
```

### Generating a Secret Key

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Email Setup (Optional)

Password reset functionality requires a SendGrid account:

1. Create a free account at [SendGrid](https://sendgrid.com/)
2. Verify a sender email address
3. Generate an API key
4. Add the API key to your `.env` file

## 🎮 How to Play

| Action | Control |
|--------|---------|
| Reveal cell | Left Click |
| Place/Remove flag | Right Click |
| Chord reveal | Middle Click (on numbered cell) |
| Use clue | Click "Use Clue" button, then click a cell |

### Game Rules

1. Click any cell to start - the first click is always safe
2. Numbers indicate how many mines are adjacent to that cell
3. Flag cells you suspect contain mines
4. Reveal all non-mine cells to win the level
5. Use clues wisely - they safely reveal whether a cell is a mine

## 🏗️ Project Structure

```
minesweeper/
├── game/                   # Main game application
│   ├── static/game/       # CSS and JavaScript
│   ├── templates/game/    # HTML templates
│   ├── models.py          # Database models
│   ├── views.py           # API views
│   ├── engine.py          # Game logic
│   └── ...
├── roguesweeper/          # Django project settings
├── locale/                # Translation files
├── manage.py
├── requirements.txt
└── .env.example
```

## 🛠️ Tech Stack

- **Backend**: Django 5.0+, Django REST Framework
- **Frontend**: Vanilla JavaScript, Bootstrap 5
- **Database**: SQLite (dev), PostgreSQL (production)
- **Email**: SendGrid
- **Internationalization**: Django i18n (English, Turkish)

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

---