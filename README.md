# Speechly - AI Speech Evaluator

An AI-powered speech evaluation platform that helps users improve their public speaking skills through structured feedback on delivery, content, and structure.

## Features

- 🎤 Record practice speeches on various topics
- 🤖 AI-powered feedback using GPT-4o-mini
- 📝 Automatic speech transcription
- 🌍 Support for 15+ languages
- 📊 Track speech history and progress
- 🎯 Practice scenarios (elevator pitch, interview, debate, etc.)
- 🔄 Repeat mode to track improvements

## Quick Start

### Prerequisites

- Python 3.7+
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd speechly
   ```

2. **Create virtual environment**
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

   # For development/testing
   pip install -r requirements-dev.txt
   ```

4. **Configure environment**
   ```bash
   # Copy example environment file
   cp .env.example .env

   # Edit .env and add your OpenAI API key
   # OPENAI_API_KEY=your-api-key-here
   ```

5. **Initialize database**
   ```bash
   python -m alembic upgrade head
   ```

6. **Run the application**
   ```bash
   python run.py
   ```

7. **Open in browser**
   ```
   http://localhost:5001
   ```

That's it! The application should now be running.

## Configuration

### Environment Variables

Create a `.env` file in the root directory with:

```bash
# Flask Environment (development, production, or testing)
FLASK_ENV=development

# OpenAI API Key (required)
OPENAI_API_KEY=your-openai-api-key-here

# Secret Key for Flask sessions (change in production!)
SECRET_KEY=your-secret-key-here

# Database URL (optional - defaults to SQLite for development)
# DATABASE_URL=postgresql://user:password@host:port/database

# Storage Configuration
STORAGE_MODE=database  # 'database' or 'file'
AUDIO_STORAGE=file     # 'file' (local) or 'base64' (cloud)

# CORS Origins (for production)
# CORS_ORIGINS=https://your-frontend.com,https://another-domain.com
```

### Configuration Modes

The application supports three environments:

- **Development**: SQLite database, file-based audio storage, debug mode
- **Production**: PostgreSQL database, base64 audio storage, optimized
- **Testing**: In-memory SQLite, mocked external APIs

Set the environment using:
```bash
export FLASK_ENV=development  # or production, testing
```

## Architecture

The application has been refactored with a clean, scalable architecture:

```
speechly/
├── app/
│   ├── __init__.py              # Flask app factory with DI container
│   ├── config/                  # Environment-based configs
│   ├── models/                  # SQLAlchemy models
│   ├── repositories/            # Data access layer
│   ├── services/                # Business logic (injectable)
│   └── routes/                  # Flask blueprints
├── static/                      # Frontend (HTML/CSS/JS)
├── tests/                       # Pytest tests with mocks
├── migrations/                  # Alembic database migrations
├── scripts/                     # Utility scripts
├── run.py                       # Main entry point
└── requirements.txt             # Dependencies
```

### Key Design Patterns

- **Dependency Injection**: All services are injectable for easy testing
- **Repository Pattern**: Data access abstracted from business logic
- **Flask Blueprints**: Routes organized by functionality
- **App Factory**: Create Flask app with different configurations
- **Configuration Objects**: Environment-specific settings

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

### Run Specific Tests

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_services/test_feedback_service.py
```

### Key Features

- ✅ **No API keys required** - All external APIs are mocked
- ✅ **Fast** - In-memory database for tests
- ✅ **Isolated** - Each test gets a clean database
- ✅ **Comprehensive** - Unit + integration tests

## Database

### Migrations

Create a new migration after modifying models:

```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:

```bash
alembic upgrade head
```

Rollback migration:

```bash
alembic downgrade -1
```

### Data Migration from JSON

If you have existing data in JSON files, migrate it to the database:

```bash
python scripts/migrate_json_to_db.py
```

This will:
1. Backup existing JSON files to `data/backup/`
2. Import all recordings and history to database
3. Preserve file references for local audio files

## Deployment

### Local Deployment

```bash
# Set production environment
export FLASK_ENV=production
export SECRET_KEY=strong-random-secret-key
export OPENAI_API_KEY=your-api-key

# Run with gunicorn (production WSGI server)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 "app:create_app()"
```

### Cloud Deployment (Heroku, Railway, etc.)

1. Set environment variables in your platform:
   - `FLASK_ENV=production`
   - `SECRET_KEY=<generate-strong-key>`
   - `OPENAI_API_KEY=<your-key>`
   - `DATABASE_URL=<provided-by-platform>`

2. The app will automatically:
   - Use PostgreSQL from `DATABASE_URL`
   - Store audio as base64 in database
   - Enable production optimizations

3. Deploy:
   ```bash
   git push heroku main
   ```

## API Endpoints

### Health Check
```
GET /api/health
```

### Session Management
```
POST   /api/session/new          # Create new session
GET    /api/session              # Get session data
DELETE /api/session              # Clear session
POST   /api/session/cleanup      # Cleanup old sessions
```

### Recordings
```
GET    /api/recordings           # List all recordings
GET    /api/recordings/<filename>  # Get specific recording
DELETE /api/recordings/<filename>  # Delete recording
DELETE /api/recordings           # Delete all recordings
```

### Evaluation
```
POST /api/record                 # Record and evaluate speech
GET  /api/stream-feedback/<session_id>/<filename>  # Stream feedback (SSE)
```

## Development

### Project Structure

- **app/config/** - Configuration classes for each environment
- **app/models/** - Database models (Session, Recording, SpeechHistory)
- **app/repositories/** - Data access layer with dual-write support
- **app/services/** - Business logic (feedback, transcription, evaluation)
- **app/routes/** - API endpoints organized by domain
- **static/** - Frontend assets (HTML, CSS, JavaScript)
- **tests/** - Test suites with mocked dependencies

### Adding a New Feature

1. **Create model** (if needed) in `app/models/`
2. **Create repository** in `app/repositories/`
3. **Create service** in `app/services/`
4. **Create routes** in `app/routes/`
5. **Register blueprint** in `app/__init__.py`
6. **Write tests** in `tests/`

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

## Supported Languages

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Russian (ru)
- Japanese (ja)
- Korean (ko)
- Chinese Simplified (zh-CN)
- Mandarin Chinese (zh)
- Arabic (ar)
- Hindi (hi)
- Turkish (tr)
- Dutch (nl)
- Bengali (bn)

## Troubleshooting

### Database Issues

**Problem**: `sqlalchemy.exc.OperationalError: no such table`

**Solution**: Run migrations
```bash
alembic upgrade head
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'app'`

**Solution**: Install in development mode
```bash
pip install -e .
```

### API Key Errors

**Problem**: `ValueError: OPENAI_API_KEY not found`

**Solution**: Create `.env` file with your API key
```bash
echo "OPENAI_API_KEY=your-key-here" > .env
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

[Your License Here]

## Acknowledgments

- OpenAI for GPT-4o-mini and Whisper APIs
- Google for Speech Recognition
- Flask and SQLAlchemy communities
