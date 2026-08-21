"""
Data migration script to import existing JSON data into the database.

This script reads from:
- data/session_data.json
- data/speech_history.json

And imports them into the SQLite/PostgreSQL database.
"""
import os
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.models import db, Session, Recording, SpeechHistory


def migrate_session_data(app):
    """Migrate session data from JSON to database."""
    json_file = os.path.join(app.config['DATA_DIR'], 'session_data.json')

    if not os.path.exists(json_file):
        print(f"No session data file found at {json_file}")
        return 0

    print(f"Reading session data from {json_file}...")

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    with app.app_context():
        for session_id, recordings in data.items():
            # Create session
            session = Session.query.filter_by(id=session_id).first()
            if not session:
                session = Session(id=session_id)
                db.session.add(session)

            # Create recordings
            for recording_data in recordings:
                # Check if recording already exists
                existing = Recording.query.filter_by(
                    filename=recording_data['filename']
                ).first()

                if existing:
                    print(f"  Skipping existing recording: {recording_data['filename']}")
                    continue

                recording = Recording(
                    session_id=session_id,
                    filename=recording_data['filename'],
                    topic=recording_data.get('topic', ''),
                    speech_type=recording_data.get('speech_type', 'practice'),
                    language=recording_data.get('language', 'en'),
                    transcription=recording_data.get('transcription'),
                    feedback=recording_data.get('feedback'),
                    duration=recording_data.get('duration'),
                    is_repeat=recording_data.get('is_repeat', False)
                )

                # Check if file exists
                recordings_dir = app.config.get('RECORDINGS_DIR', 'recordings')
                file_path = os.path.join(recordings_dir, recording.filename)
                if os.path.exists(file_path):
                    recording.file_path = file_path

                db.session.add(recording)
                count += 1

        db.session.commit()

    print(f"Migrated {count} recordings")
    return count


def migrate_speech_history(app):
    """Migrate speech history from JSON to database."""
    json_file = os.path.join(app.config['DATA_DIR'], 'speech_history.json')

    if not os.path.exists(json_file):
        print(f"No speech history file found at {json_file}")
        return 0

    print(f"Reading speech history from {json_file}...")

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    with app.app_context():
        for entry in data:
            # Try to find the recording by filename
            filename = entry.get('filename')
            if not filename:
                continue

            recording = Recording.query.filter_by(filename=filename).first()
            if not recording:
                print(f"  Warning: Recording not found for {filename}, skipping history entry")
                continue

            history_entry = SpeechHistory(
                recording_id=recording.id,
                score=entry.get('score'),
                metadata=entry.get('metadata', {})
            )
            db.session.add(history_entry)
            count += 1

        db.session.commit()

    print(f"Migrated {count} speech history entries")
    return count


def backup_json_files(app):
    """Backup JSON files before migration."""
    data_dir = app.config.get('DATA_DIR', 'data')
    backup_dir = os.path.join(data_dir, 'backup')

    os.makedirs(backup_dir, exist_ok=True)

    files_to_backup = ['session_data.json', 'speech_history.json']

    for filename in files_to_backup:
        source = os.path.join(data_dir, filename)
        if os.path.exists(source):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{filename}.{timestamp}.bak"
            dest = os.path.join(backup_dir, backup_name)

            import shutil
            shutil.copy2(source, dest)
            print(f"Backed up {filename} to {backup_name}")


def main():
    """Main migration function."""
    print("=" * 60)
    print("Speechly Data Migration")
    print("=" * 60)
    print()

    # Create app
    app = create_app()

    # Backup JSON files
    print("Step 1: Backing up JSON files...")
    backup_json_files(app)
    print()

    # Migrate session data
    print("Step 2: Migrating session data...")
    session_count = migrate_session_data(app)
    print()

    # Migrate speech history
    print("Step 3: Migrating speech history...")
    history_count = migrate_speech_history(app)
    print()

    print("=" * 60)
    print("Migration completed successfully!")
    print(f"  - {session_count} recordings migrated")
    print(f"  - {history_count} history entries migrated")
    print("=" * 60)


if __name__ == '__main__':
    main()
