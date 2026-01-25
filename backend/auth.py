"""Authentication middleware for Flask backend."""

import os
from functools import wraps
from flask import request, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


def verify_google_token(token: str) -> dict | None:
    """
    Verify a Google ID token and return the user info.

    Args:
        token: The Google ID token to verify

    Returns:
        User info dict if valid, None otherwise
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # Verify the issuer
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            return None

        return {
            "sub": idinfo["sub"],  # Google user ID
            "email": idinfo.get("email"),
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None


def require_auth(f):
    """
    Decorator to require authentication for a route.

    Expects the Authorization header to contain:
    - Bearer <google_id_token>

    Sets request.user with the verified user info.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Invalid Authorization header format"}), 401

        token = parts[1]

        # Verify the Google ID token
        user_info = verify_google_token(token)

        if not user_info:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Attach user info to request
        request.user = user_info

        return f(*args, **kwargs)

    return decorated_function


def optional_auth(f):
    """
    Decorator that attempts to authenticate but doesn't require it.

    Sets request.user if authentication succeeds, None otherwise.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        request.user = None

        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                request.user = verify_google_token(token)

        return f(*args, **kwargs)

    return decorated_function
