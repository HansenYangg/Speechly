"""Authentication service using Supabase."""
import os
from functools import wraps
from flask import request, jsonify, g
from supabase import create_client, Client


class AuthService:
    """Service for handling authentication with Supabase."""

    def __init__(self, supabase_url=None, supabase_key=None):
        """
        Initialize auth service with Supabase credentials.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase anon key
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

    def sign_up(self, email, password):
        """
        Register a new user.

        Args:
            email: User email
            password: User password

        Returns:
            dict: Response with user data or error
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })

            if response.user:
                return {
                    "success": True,
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "email_confirmed": response.user.email_confirmed_at is not None
                    },
                    "session": {
                        "access_token": response.session.access_token if response.session else None,
                        "refresh_token": response.session.refresh_token if response.session else None
                    } if response.session else None,
                    "message": "Check your email for confirmation link" if not response.session else "Signed up successfully"
                }
            else:
                return {"success": False, "error": "Failed to create user"}

        except Exception as e:
            error_msg = str(e)
            if "User already registered" in error_msg:
                return {"success": False, "error": "An account with this email already exists"}
            return {"success": False, "error": error_msg}

    def sign_in(self, email, password):
        """
        Sign in a user.

        Args:
            email: User email
            password: User password

        Returns:
            dict: Response with session data or error
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user and response.session:
                return {
                    "success": True,
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at
                    }
                }
            else:
                return {"success": False, "error": "Invalid credentials"}

        except Exception as e:
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                return {"success": False, "error": "Invalid email or password"}
            if "Email not confirmed" in error_msg:
                return {"success": False, "error": "Please confirm your email before signing in"}
            return {"success": False, "error": error_msg}

    def sign_out(self, access_token):
        """
        Sign out a user.

        Args:
            access_token: User's access token

        Returns:
            dict: Response indicating success or error
        """
        try:
            self.client.auth.sign_out()
            return {"success": True, "message": "Signed out successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user(self, access_token):
        """
        Get user from access token.

        Args:
            access_token: JWT access token

        Returns:
            dict: User data or None
        """
        try:
            response = self.client.auth.get_user(access_token)
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "email_confirmed": response.user.email_confirmed_at is not None
                }
            return None
        except Exception:
            return None

    def refresh_session(self, refresh_token):
        """
        Refresh an expired session.

        Args:
            refresh_token: Refresh token

        Returns:
            dict: New session data or error
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)
            if response.session:
                return {
                    "success": True,
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at
                    }
                }
            return {"success": False, "error": "Failed to refresh session"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_token(self, access_token):
        """
        Verify if an access token is valid.

        Args:
            access_token: JWT access token

        Returns:
            bool: True if valid, False otherwise
        """
        user = self.get_user(access_token)
        return user is not None

    def get_oauth_url(self, provider, redirect_url):
        """
        Get OAuth sign-in URL for a provider.

        Args:
            provider: OAuth provider (e.g., 'google')
            redirect_url: URL to redirect after auth

        Returns:
            dict: URL to redirect user to, or error
        """
        try:
            response = self.client.auth.sign_in_with_oauth({
                "provider": provider,
                "options": {
                    "redirect_to": redirect_url
                }
            })
            return {"success": True, "url": response.url}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_auth_service = None


def get_auth_service():
    """Get or create the auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def require_auth(f):
    """
    Decorator to require authentication for a route.

    Usage:
        @app.route('/protected')
        @require_auth
        def protected_route():
            user = g.user  # Access authenticated user
            return jsonify({"user": user})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({"error": "No authorization header"}), 401

        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({"error": "Invalid authorization header format"}), 401

        access_token = parts[1]

        auth_service = get_auth_service()
        user = auth_service.get_user(access_token)

        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Store user in Flask's g object for access in route
        g.user = user
        g.access_token = access_token

        return f(*args, **kwargs)

    return decorated_function


__all__ = ['AuthService', 'get_auth_service', 'require_auth']
