"""
OAuth PKCE authentication service for adLibre desktop app.
Opens browser for login, handles callback via custom URL scheme.
"""
import secrets
import hashlib
import base64
import webbrowser
import threading
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from pathlib import Path


class AuthService:
    CLIENT_ID = "adlibre-desktop"
    REDIRECT_URI = "https://adlibre.org/callback"
    API_BASE = "http://45.79.9.188"    
    
    TOKEN_FILE = Path.home() / ".adlibre" / "tokens.json"
    
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.user = None
        self._load_tokens()
    
    def _generate_pkce(self):
        """Generate PKCE code_verifier and code_challenge."""
        code_verifier = secrets.token_urlsafe(32)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
        return code_verifier, code_challenge
    
    def _save_tokens(self):
        """Persist tokens to disk."""
        self.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "user": self.user,
        }
        self.TOKEN_FILE.write_text(json.dumps(data))
    
    def _load_tokens(self):
        """Load tokens from disk if they exist."""
        if self.TOKEN_FILE.exists():
            try:
                data = json.loads(self.TOKEN_FILE.read_text())
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.user = data.get("user")
            except (json.JSONDecodeError, IOError):
                pass
    
    def _clear_tokens(self):
        """Clear stored tokens."""
        self.access_token = None
        self.refresh_token = None
        self.user = None
        if self.TOKEN_FILE.exists():
            self.TOKEN_FILE.unlink()
    
    def is_logged_in(self):
        """Check if user has valid tokens."""
        return self.access_token is not None
    
    def login(self, on_success=None, on_error=None):
        """
        Start OAuth login flow.
        Opens browser for user to authenticate, then polls for completion.
        """
        code_verifier, code_challenge = self._generate_pkce()
        state = secrets.token_urlsafe(16)

        # Start the auth flow
        try:
            resp = requests.post(
                f"{self.API_BASE}/api/app-auth/start",
                json={
                    "client_id": self.CLIENT_ID,
                    "redirect_uri": self.REDIRECT_URI,
                    "state": state,
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            if on_error:
                on_error(f"Failed to start login: {e}")
            return False

        request_id = data["request_id"]
        login_url = data["login_url"]

        # Open the browser for the user to log in
        webbrowser.open(login_url, new=1, autoraise=True)

        # Poll /api/app-auth/check until authorized or timed out
        auth_code = None
        deadline = time.time() + 60  # 60 second timeout

        while time.time() < deadline:
            time.sleep(2)
            try:
                poll = requests.get(
                    f"{self.API_BASE}/api/app-auth/check",
                    params={"request_id": request_id},
                    timeout=10,
                )
                poll.raise_for_status()
                poll_data = poll.json()
            except Exception as e:
                if on_error:
                    on_error(f"Polling error: {e}")
                return False

            if poll_data.get("status") == "authorized":
                auth_code = poll_data["code"]
                break
            elif poll_data.get("status") == "pending":
                continue
            else:
                if on_error:
                    on_error(f"Unexpected poll status: {poll_data}")
                return False

        if not auth_code:
            if on_error:
                on_error("Login timed out. Please try again.")
            return False

        # Exchange code for tokens
        try:
            resp = requests.post(
                f"{self.API_BASE}/api/app-auth/token",
                json={
                    "client_id": self.CLIENT_ID,
                    "code": auth_code,
                    "code_verifier": code_verifier,
                    "redirect_uri": self.REDIRECT_URI,
                    "device_name": self._get_device_name(),
                },
                timeout=10,
            )
            resp.raise_for_status()
            token_data = resp.json()
        except Exception as e:
            if on_error:
                on_error(f"Token exchange failed: {e}")
            return False

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]
        self.user = token_data.get("user")
        self._save_tokens()

        if on_success:
            on_success(self.user)
        return True

    
    def _get_device_name(self):
        """Get a friendly device name."""
        import platform
        return f"{platform.node()} ({platform.system()})"
    
    def refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            return False
        
        try:
            resp = requests.post(
                f"{self.API_BASE}/api/app-auth/refresh",
                json={
                    "client_id": self.CLIENT_ID,
                    "refresh_token": self.refresh_token,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data["access_token"]
            self._save_tokens()
            return True
        except Exception:
            return False
    
    def logout(self):
        """Logout and revoke tokens."""
        if self.refresh_token:
            try:
                requests.post(
                    f"{self.API_BASE}/api/app-auth/revoke",
                    json={"refresh_token": self.refresh_token},
                    timeout=10,
                )
            except Exception:
                pass  # Best effort
        
        self._clear_tokens()
    
    def get_auth_header(self):
        """Get Authorization header for API requests."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}
