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

from config import API_BASE as DEFAULT_API_BASE, API_BASES as DEFAULT_API_BASES


class AuthService:
    CLIENT_ID = "adlibre-desktop"
    REDIRECT_URI = "https://adlibre.org/callback"
    API_BASE = DEFAULT_API_BASE
    API_BASES = tuple(DEFAULT_API_BASES) if DEFAULT_API_BASES else (DEFAULT_API_BASE,)
    
    TOKEN_FILE = Path.home() / ".adlibre" / "tokens.json"
    
    def __init__(self):
        self.api_bases = self._normalize_api_bases(self.API_BASES)
        self.API_BASE = self.api_bases[0]
        self.access_token = None
        self.refresh_token = None
        self.user = None
        self._load_tokens()
        # Periodic task control
        self._periodic_thread = None
        self._stop_event = threading.Event()
        self.last_authorized = None  # timestamp of last successful authorization
        self.home_network = None
        self.AUTH_TIMEOUT = 330 # seconds before authorization is considered stale (5min + 30s grace)

    @staticmethod
    def _normalize_api_bases(bases):
        seen = set()
        normalized = []

        for base in bases or []:
            candidate = str(base or "").strip().rstrip("/")
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)

        fallback = str(DEFAULT_API_BASE or "").strip().rstrip("/")
        if not normalized and fallback:
            normalized.append(fallback)

        return normalized

    def _request_first_available(self, method, path, *, bases=None, fallback_statuses=(404,), **kwargs):
        candidates = self._normalize_api_bases(bases or self.api_bases)
        last_response = None
        last_error = None

        for base in candidates:
            try:
                response = requests.request(
                    method,
                    f"{base}{path}",
                    **kwargs,
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc
                continue

            if response.status_code in fallback_statuses:
                last_response = (response, base)
                continue

            return response, base

        if last_response is not None:
            return last_response

        if last_error is not None:
            raise last_error

        raise RuntimeError("No API endpoints configured.")

    def _request_all_bases(self, method, path, **kwargs):
        candidates = self._normalize_api_bases(self.api_bases)
        results = []

        for base in candidates:
            try:
                response = requests.request(
                    method,
                    f"{base}{path}",
                    **kwargs,
                )
                results.append((base, response, None))
            except requests.exceptions.RequestException as exc:
                results.append((base, None, exc))

        return results

    @staticmethod
    def _label_api_base(base):
        return base.replace("http://", "").replace("https://", "")

    def _request_json_from_any_base(self, method, path, **kwargs):
        results = self._request_all_bases(method, path, **kwargs)
        errors = []

        for base, resp, request_error in results:
            if request_error is not None:
                errors.append(
                    f"{self._label_api_base(base)}: "
                    f"{request_error.__class__.__name__}: {request_error}"
                )
                continue

            if resp.status_code >= 400:
                error_msg, _data = self._extract_error_message(resp)
                errors.append(f"{self._label_api_base(base)}: {error_msg}")
                continue

            try:
                data = resp.json()
            except Exception:
                errors.append(f"{self._label_api_base(base)}: Invalid server response")
                continue

            return True, data, None

        if errors:
            return False, None, "; ".join(errors)

        return False, None, "No API response"
    
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
        self.home_network = None
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
            resp, auth_base = self._request_first_available(
                "POST",
                "/api/app-auth/start",
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
        deadline = time.time() + 120  # 2 minute timeout

        while time.time() < deadline:
            time.sleep(2)
            try:
                poll, _ = self._request_first_available(
                    "GET",
                    "/api/app-auth/check",
                    bases=[auth_base],
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
            resp, _ = self._request_first_available(
                "POST",
                "/api/app-auth/token",
                bases=[auth_base],
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
            resp, _ = self._request_first_available(
                "POST",
                "/api/app-auth/refresh",
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
                self._request_first_available(
                    "POST",
                    "/api/app-auth/revoke",
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

    def _extract_error_message(self, response):
        try:
            data = response.json()
        except Exception:
            if response.status_code == 404:
                return "This feature is not available on the current server yet.", None
            return f"Request failed (HTTP {response.status_code})", None

        message = (
            data.get("error")
            or data.get("message")
            or f"Request failed (HTTP {response.status_code})"
        )
        return message, data

    def _store_home_network(self, data):
        if isinstance(data, dict):
            self.home_network = data.get("home_network")
        return self.home_network
    
    def authorize_device_access(self):
        """
        Send POST request to authorize device access and register device IP.
        Called before connecting to ensure user has device access.
        Returns (success, error_message) tuple.
        
        The endpoint:
        - Extracts the client IP from the request
        - Sends it to the DNS server for authorization
        - Returns success only if both the request succeeds AND DNS server authorizes the IP
        """
        if not self.access_token:
            return (False, "Not authenticated")
        
        try:
            results = self._request_all_bases(
                "POST",
                "/api/app-auth/device-access",
                headers=self.get_auth_header(),
                json={},
                timeout=10,
            )

            success_bases = []
            errors = []
            active_devices = None

            for base, resp, request_error in results:
                if request_error is not None:
                    errors.append(
                        f"{self._label_api_base(base)}: "
                        f"{request_error.__class__.__name__}: {request_error}"
                    )
                    continue

                if resp.status_code >= 400:
                    error_msg, _data = self._extract_error_message(resp)
                    errors.append(f"{self._label_api_base(base)}: {error_msg}")
                    continue

                try:
                    data = resp.json()
                except Exception:
                    errors.append(f"{self._label_api_base(base)}: Invalid server response")
                    continue

                self._store_home_network(data)
                if data.get("status") == "ok":
                    success_bases.append(self._label_api_base(base))
                    active_devices = data.get("active_devices", active_devices)
                    continue

                errors.append(
                    f"{self._label_api_base(base)}: "
                    f"{data.get('error') or data.get('message') or 'DNS server denied access'}"
                )

            if success_bases:
                self.last_authorized = time.time()
                print(
                    "Device authorized via "
                    f"{', '.join(success_bases)}. "
                    f"Active devices: {active_devices if active_devices is not None else 'unknown'}"
                )
                return (True, None)

            if errors:
                return (False, "; ".join(errors))

            return (False, "Authorization failed: no API response")
        except requests.exceptions.Timeout:
            return (False, "Request timeout - check your connection")
        except requests.exceptions.ConnectionError:
            return (False, "Connection error - check your internet")
        except Exception as e:
            return (False, f"Authorization failed: {str(e)}")

    def get_home_network_status(self):
        """Fetch the current home network status for this account."""
        if not self.access_token:
            return (False, None, "Not authenticated")

        try:
            success, data, error = self._request_json_from_any_base(
                "GET",
                "/api/app-auth/home-network",
                headers=self.get_auth_header(),
                timeout=10,
            )
            if not success:
                return (False, None, error)
            home_network = self._store_home_network(data)
            return (True, home_network, None)
        except requests.exceptions.Timeout:
            return (False, None, "Request timeout - check your connection")
        except requests.exceptions.ConnectionError:
            return (False, None, "Connection error - check your internet")
        except Exception as e:
            return (False, None, f"Home network lookup failed: {str(e)}")

    def set_home_network(self):
        """Register the current public IP as the user's home network."""
        if not self.access_token:
            return (False, None, "Not authenticated")

        try:
            success, data, error = self._request_json_from_any_base(
                "POST",
                "/api/app-auth/home-network",
                headers=self.get_auth_header(),
                json={},
                timeout=10,
            )
            if not success:
                return (False, None, error)
            home_network = self._store_home_network(data)
            return (True, home_network, data.get("message"))
        except requests.exceptions.Timeout:
            return (False, None, "Request timeout - check your connection")
        except requests.exceptions.ConnectionError:
            return (False, None, "Connection error - check your internet")
        except Exception as e:
            return (False, None, f"Failed to set home network: {str(e)}")
        
    
    def is_authorized(self):
        """Check if the last authorization timestamp is still within the valid window."""
        if self.last_authorized is None:
            return False
        return (time.time() - self.last_authorized) < self.AUTH_TIMEOUT

    def _periodic_worker(self, interval_seconds, task):
        """Worker loop that runs `task` immediately, then every `interval_seconds` seconds.

        The loop exits when `self._stop_event` is set.
        """
        # Run first time immediately
        try:
            task()
        except Exception:
            pass

        # Repeatedly wait and run until stopped
        while not self._stop_event.wait(interval_seconds):
            try:
                task()
            except Exception:
                pass

    def start_periodic_tasks(self, interval_seconds=300, task=None):
        """Start a background daemon thread that runs `task` every `interval_seconds`.

        - If `task` is None, defaults to refreshing the access token and calling
          `authorize_device_access()`.
        - `interval_seconds` defaults to 300 (5 minutes).
        """
        if self._periodic_thread and self._periodic_thread.is_alive():
            return  # already running

        if task is None:
            def task():
                try:
                    self.refresh_access_token()
                except Exception:
                    pass
                try:
                    self.authorize_device_access()
                except Exception:
                    pass
                try:
                    self.get_home_network_status()
                except Exception:
                    pass

        # Clear any previous stop event and start new thread
        self._stop_event.clear()
        self._periodic_thread = threading.Thread(
            target=self._periodic_worker, args=(interval_seconds, task), daemon=True
        )
        self._periodic_thread.start()

    def stop_periodic_tasks(self, join_timeout=5):
        """Signal the periodic worker to stop and join the thread (optional timeout)."""
        self._stop_event.set()
        if self._periodic_thread:
            try:
                self._periodic_thread.join(timeout=join_timeout)
            except Exception:
                pass
