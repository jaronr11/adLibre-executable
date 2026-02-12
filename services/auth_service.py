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
    REDIRECT_URI = "adlibre://callback"
    API_BASE = "http://45.79.9.188"    

    # For local callback handling (fallback if custom URL scheme not registered)
    LOCAL_CALLBACK_PORT = 19847
    LOCAL_REDIRECT_URI = f"http://localhost:{LOCAL_CALLBACK_PORT}/callback"
    
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
        Opens browser for user to authenticate.
        """
        code_verifier, code_challenge = self._generate_pkce()
        state = secrets.token_urlsafe(16)
        
        # Start the auth flow
        try:
            resp = requests.post(
                f"{self.API_BASE}/api/app-auth/start",
                json={
                    "client_id": self.CLIENT_ID,
                    "redirect_uri": self.LOCAL_REDIRECT_URI,  # Use local for now
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
        
        login_url = data["login_url"]
        
        # Start local server to receive callback
        auth_code = None
        received_state = None
        server_error = None
        
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal auth_code, received_state, server_error
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                
                if "error" in params:
                    server_error = params["error"][0]
                    self._send_response("Login failed. You can close this window.")
                    return
                
                auth_code = params.get("code", [None])[0]
                received_state = params.get("state", [None])[0]
                self._send_response("Login successful! You can close this window and return to the app.")
            
            def _send_response(self, message):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                html = f"""
                <html>
                <head><title>adLibre</title></head>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2>{message}</h2>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
            
            def log_message(self, format, *args):
                pass  # Suppress logging
        
        server = HTTPServer(("localhost", self.LOCAL_CALLBACK_PORT), CallbackHandler)
        server.timeout = 120  # 2 minute timeout
        
        # Request a new browser window for desktop app sign-in.
        webbrowser.open(login_url, new=1, autoraise=True)
        
        # Wait for callback (blocking, but could be threaded)
        server.handle_request()
        server.server_close()
        
        if server_error:
            if on_error:
                on_error(f"Login error: {server_error}")
            return False
        
        if not auth_code or received_state != state:
            if on_error:
                on_error("Invalid login response")
            return False
        
        # Exchange code for tokens
        try:
            resp = requests.post(
                f"{self.API_BASE}/api/app-auth/token",
                json={
                    "client_id": self.CLIENT_ID,
                    "code": auth_code,
                    "code_verifier": code_verifier,
                    "redirect_uri": self.LOCAL_REDIRECT_URI,
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
