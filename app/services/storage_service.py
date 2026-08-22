"""Storage service for managing audio files with Supabase Storage."""
import os
import uuid
from supabase import create_client, Client


class StorageService:
    """Service for handling file storage with Supabase Storage."""

    BUCKET_NAME = 'recordings'

    def __init__(self, supabase_url=None, supabase_key=None):
        """
        Initialize storage service with Supabase credentials.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase anon key or service role key
        """
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_ANON_KEY')
        self._client = None

    @property
    def client(self) -> Client:
        """Get or create Supabase client."""
        if self._client is None:
            if not self.supabase_url or not self.supabase_key:
                raise ValueError("Supabase URL and key must be configured")
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    def upload_audio(self, file_data, filename, session_id, content_type='audio/webm'):
        """
        Upload an audio file to Supabase Storage.

        Args:
            file_data: File data (bytes)
            filename: Original filename
            session_id: Session ID for organizing files
            content_type: MIME type of the file

        Returns:
            dict: Upload result with public URL or error
        """
        try:
            # Generate unique path: session_id/uuid_filename
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = f"{session_id}/{unique_filename}"

            # Upload to Supabase Storage
            result = self.client.storage.from_(self.BUCKET_NAME).upload(
                file_path,
                file_data,
                file_options={"content-type": content_type}
            )

            # Get public URL
            public_url = self.client.storage.from_(self.BUCKET_NAME).get_public_url(file_path)

            return {
                "success": True,
                "file_path": file_path,
                "public_url": public_url,
                "filename": unique_filename
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Storage upload error: {error_msg}")
            return {"success": False, "error": error_msg}

    def download_audio(self, file_path):
        """
        Download an audio file from Supabase Storage.

        Args:
            file_path: Path to the file in storage

        Returns:
            bytes: File data or None if error
        """
        try:
            data = self.client.storage.from_(self.BUCKET_NAME).download(file_path)
            return data
        except Exception as e:
            print(f"Storage download error: {e}")
            return None

    def delete_audio(self, file_path):
        """
        Delete an audio file from Supabase Storage.

        Args:
            file_path: Path to the file in storage

        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            self.client.storage.from_(self.BUCKET_NAME).remove([file_path])
            return True
        except Exception as e:
            print(f"Storage delete error: {e}")
            return False

    def delete_session_files(self, session_id):
        """
        Delete all files for a session.

        Args:
            session_id: Session ID

        Returns:
            int: Number of files deleted
        """
        try:
            # List all files in session folder
            files = self.client.storage.from_(self.BUCKET_NAME).list(session_id)

            if not files:
                return 0

            # Delete all files
            file_paths = [f"{session_id}/{f['name']}" for f in files]
            self.client.storage.from_(self.BUCKET_NAME).remove(file_paths)

            return len(file_paths)
        except Exception as e:
            print(f"Storage session delete error: {e}")
            return 0

    def get_public_url(self, file_path):
        """
        Get public URL for a file.

        Args:
            file_path: Path to the file in storage

        Returns:
            str: Public URL
        """
        return self.client.storage.from_(self.BUCKET_NAME).get_public_url(file_path)


# Singleton instance
_storage_service = None


def get_storage_service():
    """Get or create the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


__all__ = ['StorageService', 'get_storage_service']
