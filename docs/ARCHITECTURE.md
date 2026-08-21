# Speechly Architecture Documentation

## Overview

Speechly has been refactored from a monolithic application into a clean, modular architecture following industry best practices.

## Design Principles

1. **Separation of Concerns**: Clear boundaries between routes, services, repositories, and models
2. **Dependency Injection**: All external dependencies are injectable for testing
3. **Environment-Based Configuration**: Easy switching between dev/test/prod
4. **Repository Pattern**: Data access abstracted from business logic
5. **Testability**: Comprehensive test coverage with mocked dependencies

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Clients                         │
│              (Browser, Mobile, API consumers)           │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Flask Routes (app/routes/)             │
│  ┌────────┬───────────┬────────────┬─────────────┐     │
│  │ Health │ Sessions  │ Recordings │ Evaluation  │     │
│  └────────┴───────────┴────────────┴─────────────┘     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Services (app/services/)                   │
│  ┌────────────────┬──────────────────┬──────────────┐  │
│  │ Feedback       │ Transcription    │ Evaluation   │  │
│  │ Service        │ Service          │ Service      │  │
│  └────────────────┴──────────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│           Repositories (app/repositories/)              │
│  ┌────────────────┬──────────────────┬──────────────┐  │
│  │ Session        │ Recording        │ Speech       │  │
│  │ Repository     │ Repository       │ History Repo │  │
│  └────────────────┴──────────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│               Models (app/models/)                      │
│  ┌────────────────┬──────────────────┬──────────────┐  │
│  │ Session        │ Recording        │ SpeechHistory│  │
│  │ (SQLAlchemy)   │ (SQLAlchemy)     │ (SQLAlchemy) │  │
│  └────────────────┴──────────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Database                             │
│         (SQLite for dev, PostgreSQL for prod)           │
└─────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Routes Layer (app/routes/)

**Responsibility**: Handle HTTP requests and responses

**Files**:
- `health.py` - Health check endpoints
- `sessions.py` - Session management (CRUD)
- `recordings.py` - Recording management
- `evaluation.py` - Speech evaluation endpoints
- `frontend.py` - Serve static frontend files

**Key Patterns**:
- Blueprint pattern for modular routes
- Request validation at entry point
- Dependency injection via `current_app.container`
- Consistent error responses

**Example**:
```python
@bp.route('/session', methods=['GET'])
def get_session_data():
    session_id = get_session_id(request)
    recording_repo = current_app.container.get_recording_repository()
    recordings = recording_repo.get_session_recordings(session_id)
    return jsonify({'success': True, 'recordings': [r.to_dict() for r in recordings]})
```

### 2. Services Layer (app/services/)

**Responsibility**: Business logic and orchestration

**Files**:
- `feedback_service.py` - AI feedback generation
- `transcription_service.py` - Speech-to-text conversion
- `evaluation_service.py` - Orchestrates full evaluation workflow

**Key Patterns**:
- Constructor injection for dependencies
- Pure functions where possible
- No direct database access (uses repositories)
- Configuration injected via constructor

**Example**:
```python
class FeedbackService:
    def __init__(self, openai_client, translation_service, config):
        self.client = openai_client  # Injected!
        self.translation_service = translation_service
        self.config = config

    def generate_feedback(self, topic, speech_type, transcription, ...):
        # Business logic here
```

### 3. Repositories Layer (app/repositories/)

**Responsibility**: Data access and persistence

**Files**:
- `base.py` - Base repository with common operations
- `session_repository.py` - Session CRUD
- `recording_repository.py` - Recording CRUD with dual-write
- `speech_history_repository.py` - History tracking

**Key Patterns**:
- Repository pattern (abstraction over database)
- Dual-write capability for migration
- Transaction management
- Query optimization

**Example**:
```python
class RecordingRepository(BaseRepository):
    def save_recording(self, session_id, filename, topic, ...):
        recording = self.create(session_id=session_id, filename=filename, ...)

        # Dual-write to legacy JSON (during migration)
        if self.legacy_json_file:
            self._write_to_legacy_json(recording)

        return recording
```

### 4. Models Layer (app/models/)

**Responsibility**: Database schema and ORM

**Files**:
- `database.py` - Database initialization
- `session.py` - Session model
- `recording.py` - Recording model
- `speech_history.py` - History model

**Key Features**:
- SQLAlchemy ORM
- Relationships and constraints
- Automatic timestamps
- JSON serialization via `to_dict()`

**Example**:
```python
class Recording(db.Model):
    __tablename__ = 'recordings'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'))
    filename = db.Column(db.String(255), unique=True, nullable=False)
    # ... more fields

    session = db.relationship('Session', back_populates='recordings')
```

## Dependency Injection

### ServiceContainer

The `ServiceContainer` class in `app/__init__.py` manages all dependencies:

```python
class ServiceContainer:
    def get_feedback_service(self):
        client = self.get_openai_client()  # Real or mock based on config
        translation = self.get_translation_service()
        return FeedbackService(client, translation, self.config)
```

### Benefits

1. **Testability**: Easy to inject mocks for testing
2. **Flexibility**: Swap implementations without changing code
3. **Centralized**: All dependency creation in one place
4. **Lazy Loading**: Services created only when needed

## Configuration Management

### Three Environments

1. **Development** (`app/config/development.py`)
   - SQLite database (`dev.db`)
   - File-based audio storage
   - Debug mode enabled
   - SQL query logging

2. **Production** (`app/config/production.py`)
   - PostgreSQL database
   - Base64 audio storage (no filesystem)
   - Optimized settings
   - Strong secret key required

3. **Testing** (`app/config/testing.py`)
   - In-memory SQLite
   - Mocked external APIs
   - Fast test execution

### Loading Configuration

```python
# Set environment
export FLASK_ENV=production

# App factory loads correct config
app = create_app()  # Automatically loads ProductionConfig
```

## Database Schema

### Entity-Relationship Diagram

```
┌─────────────┐
│   Session   │
│─────────────│
│ id (PK)     │────┐
│ created_at  │    │
│ updated_at  │    │
│ last_access │    │
└─────────────┘    │
                   │ 1:N
                   │
                   ▼
         ┌──────────────────┐
         │    Recording     │
         │──────────────────│
         │ id (PK)          │────┐
         │ session_id (FK)  │    │
         │ filename         │    │
         │ topic            │    │
         │ speech_type      │    │
         │ transcription    │    │ 1:N
         │ feedback         │    │
         │ duration         │    │
         │ audio_data       │    │
         │ file_path        │    │
         └──────────────────┘    │
                                  │
                                  ▼
                     ┌───────────────────┐
                     │  SpeechHistory    │
                     │───────────────────│
                     │ id (PK)           │
                     │ recording_id (FK) │
                     │ score             │
                     │ metadata          │
                     │ created_at        │
                     └───────────────────┘
```

### Key Relationships

- One Session has many Recordings
- One Recording can have many SpeechHistory entries
- Recordings can reference previous recordings (repeat mode)

## Testing Strategy

### Test Pyramid

```
         ╱╲
        ╱  ╲         Unit Tests (80%)
       ╱────╲        - Services
      ╱      ╲       - Repositories
     ╱────────╲      - Models
    ╱          ╲
   ╱────────────╲    Integration Tests (15%)
  ╱              ╲   - API endpoints
 ╱────────────────╲  - Database operations
```

### Mocking Strategy

All external dependencies are mocked:

1. **OpenAI API** → `MockOpenAIClient`
2. **Google Speech** → `MockRecognizer`
3. **Database** → In-memory SQLite
4. **File System** → Temporary directories

### Test Fixtures

```python
@pytest.fixture
def client(app):
    """Test client for API requests"""
    return app.test_client()

@pytest.fixture
def mock_openai(monkeypatch):
    """Inject mock OpenAI client"""
    mock = MockOpenAIClient()
    monkeypatch.setattr('openai.OpenAI', lambda **kw: mock)
    return mock
```

## Request Flow Example

### POST /api/record

```
1. Request arrives → evaluation.py:record_and_evaluate()
2. Extract session_id from headers
3. Validate request data
4. Save audio to temporary file
5. Call evaluation_service.evaluate_audio_file()
   │
   ├── 5a. transcription_service.transcribe_audio()
   │       └── Uses injected speech_recognizer (real or mock)
   │
   └── 5b. feedback_service.generate_feedback()
           └── Uses injected openai_client (real or mock)
6. Save to database via recording_repository
7. Return JSON response
```

## Migration Strategy

### Dual-Write Pattern

During migration from JSON to database, repositories write to both:

```python
class RecordingRepository:
    def save_recording(self, ...):
        # Write to database
        recording = self.create(...)

        # Also write to legacy JSON (backward compatibility)
        if self.legacy_json_file:
            self._write_to_legacy_json(recording)

        return recording
```

This allows:
- Zero downtime migration
- Rollback capability
- Gradual transition

## Security Considerations

1. **Input Validation**: All user inputs validated
2. **SQL Injection**: SQLAlchemy ORM prevents injection
3. **XSS**: Frontend properly escapes output
4. **CORS**: Configured per environment
5. **Secret Management**: Environment variables, never committed

## Performance Optimizations

1. **Lazy Loading**: Services created only when needed
2. **Connection Pooling**: SQLAlchemy manages connections
3. **Caching**: ServiceContainer caches service instances
4. **Async Support**: Ready for async/await (future enhancement)

## Future Enhancements

1. **Async Processing**: Use Celery for background tasks
2. **Caching Layer**: Redis for session data
3. **API Versioning**: `/api/v1/`, `/api/v2/`
4. **Authentication**: JWT-based auth
5. **Rate Limiting**: Protect against abuse
6. **Monitoring**: Prometheus metrics
7. **Logging**: Structured logging with correlation IDs

## Glossary

- **Blueprint**: Flask's way of organizing routes into modules
- **Repository**: Pattern that abstracts data access
- **Service**: Business logic layer
- **Dependency Injection**: Passing dependencies to objects rather than creating them internally
- **ORM**: Object-Relational Mapping (SQLAlchemy)
- **Dual-Write**: Writing to both old and new systems during migration
