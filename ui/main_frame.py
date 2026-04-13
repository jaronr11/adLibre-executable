import os
import platform
import shutil
import subprocess
import threading
import webbrowser

import customtkinter as ctk

from config import ADLIBRE_WEBSITE, COLORS, DNS_SERVER, FONT


class MainFrame(ctk.CTkFrame):
    HOME_NETWORK_REFRESH_MS = 30000

    def __init__(self, master, dns_service, auth_service, on_logout):
        super().__init__(master, fg_color=COLORS["deep_void"])
        self.master = master
        self.dns_service = dns_service
        self.auth = auth_service
        self.on_logout = on_logout
        self._auth_check_id = None
        self._home_network_poll_id = None
        self._home_network_request_in_flight = False
        self.create_ui()

    def create_ui(self):
        self.status_bar = ctk.CTkFrame(
            self,
            height=44,
            fg_color=COLORS["exposed_red"],
            corner_radius=0,
        )
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="STATUS: DISCONNECTED",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self.status_label.pack(side="left", padx=20)

        ctk.CTkLabel(
            self.status_bar,
            text="o",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_primary"],
        ).pack(side="right", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(expand=True, fill="both", padx=28, pady=28)

        header_row = ctk.CTkFrame(body, fg_color="transparent")
        header_row.pack(fill="x", anchor="w")

        header = ctk.CTkFrame(header_row, fg_color="transparent")
        header.pack(side="left")

        def open_site(_=None):
            webbrowser.open(ADLIBRE_WEBSITE)

        header.bind("<Button-1>", open_site)
        header.configure(cursor="hand2")

        ad_label = ctk.CTkLabel(
            header,
            text="ad",
            font=ctk.CTkFont(family=FONT, size=52, weight="bold"),
            text_color=COLORS["deep_void"],
            fg_color=COLORS["shield_green"],
            corner_radius=6,
            padx=10,
            pady=2,
        )
        ad_label.pack(side="left")

        libre_label = ctk.CTkLabel(
            header,
            text="Libre",
            font=ctk.CTkFont(family=FONT, size=52, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        libre_label.pack(side="left")

        self.logout_button = ctk.CTkButton(
            header_row,
            text="Logout",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=COLORS["text_muted"],
            hover_color=COLORS["deep_void"],
            width=60,
            height=28,
            command=self._do_logout,
        )
        self.logout_button.pack(side="right", padx=(0, 10))

        self.welcome_label = ctk.CTkLabel(
            body,
            text="Secure your connection",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.welcome_label.pack(anchor="w", pady=(0, 32))

        self.connect_button = ctk.CTkButton(
            body,
            text="[ CONNECT ]",
            font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
            fg_color=COLORS["text_primary"],
            text_color=COLORS["deep_void"],
            hover_color=COLORS["text_muted"],
            height=72,
            width=360,
            corner_radius=0,
            border_width=3,
            border_color=COLORS["text_primary"],
            command=self.toggle_connection,
        )
        self.connect_button.pack(anchor="center", pady=(24, 12))

        self.server_label = ctk.CTkLabel(
            body,
            text="Server: AUTOMATIC",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
            anchor="center",
        )
        self.server_label.pack(anchor="center")

        # Shown only while connected. The OS DNS cache is already flushed
        # by DNSService, but Chrome keeps its own internal host cache and
        # socket pool that an external process can't touch — so tell the
        # user how to clear them for instant full blocking.
        self.browser_hint_container = ctk.CTkFrame(body, fg_color="transparent")

        self.browser_hint_label = ctk.CTkLabel(
            self.browser_hint_container,
            text="Tip: Restart your browser for full ad-blocking.",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        )
        self.browser_hint_label.pack()

        self.flush_browser_button = ctk.CTkButton(
            self.browser_hint_container,
            text="Flush browser caches",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLORS["shield_green"],
            hover_color=COLORS["deep_void"],
            border_width=1,
            border_color=COLORS["shield_green"],
            corner_radius=6,
            height=26,
            width=160,
            command=self._flush_browser_dns,
        )
        self.flush_browser_button.pack(pady=(6, 0))

        self.home_network_card = ctk.CTkFrame(
            body,
            fg_color="#111111",
            border_width=1,
            border_color=COLORS["text_muted"],
            corner_radius=12,
        )
        self.home_network_card.pack(fill="x", pady=(28, 0))

        card_header = ctk.CTkFrame(self.home_network_card, fg_color="transparent")
        card_header.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            card_header,
            text="HOME NETWORK",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        self.home_network_badge = ctk.CTkLabel(
            card_header,
            text="CHECKING",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["text_muted"],
            corner_radius=999,
            padx=10,
            pady=4,
        )
        self.home_network_badge.pack(side="right")

        self.home_network_status_label = ctk.CTkLabel(
            self.home_network_card,
            text="Checking your registered home network...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
            justify="left",
        )
        self.home_network_status_label.pack(fill="x", padx=16)

        self.home_network_detail_label = ctk.CTkLabel(
            self.home_network_card,
            text="Current IP: --\nRegistered IP: --",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
            justify="left",
        )
        self.home_network_detail_label.pack(fill="x", padx=16, pady=(8, 8))

        self.home_network_feedback_label = ctk.CTkLabel(
            self.home_network_card,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["shield_green"],
            anchor="w",
            justify="left",
        )
        self.home_network_feedback_label.pack(fill="x", padx=16)

        self.home_network_button = ctk.CTkButton(
            self.home_network_card,
            text="SET HOME NETWORK",
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            fg_color=COLORS["shield_green"],
            text_color=COLORS["deep_void"],
            hover_color=COLORS["shield_green_hover"],
            height=42,
            corner_radius=8,
            command=self.set_home_network,
        )
        self.home_network_button.pack(fill="x", padx=16, pady=(12, 16))

        self.update_connection_ui()
        self._render_home_network(None)

    def set_user(self, user):
        if user and user.get("username"):
            self.welcome_label.configure(text=f"Welcome, {user['username']}")
        else:
            self.welcome_label.configure(text="Secure your connection")
        self.refresh_home_network_status_async()

    def _do_logout(self):
        self.auth.logout()
        self.on_logout()

    def toggle_connection(self):
        if self.master.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        try:
            success, error_msg = self.auth.authorize_device_access()
            if not success:
                self.show_error(f"Authorization failed: {error_msg}")
                return
            self.dns_service.connect()
            self.master.is_connected = True
            self.update_connection_ui()
            self._render_home_network(self.auth.home_network)
        except Exception as e:
            self.show_error(str(e))

    def disconnect(self):
        try:
            self.dns_service.disconnect()
            self.master.is_connected = False
            self.update_connection_ui()
        except Exception as e:
            self.show_error(str(e))

    def update_connection_ui(self):
        if self.master.is_connected:
            self.status_bar.configure(fg_color=COLORS["shield_green"])
            self.status_label.configure(text="STATUS: CONNECTED")
            self.connect_button.configure(
                text="[ DISCONNECT ]",
                fg_color=COLORS["shield_green"],
                text_color=COLORS["text_primary"],
                hover_color=COLORS["shield_green_hover"],
                border_color=COLORS["shield_green"],
            )
            self.server_label.configure(
                text=f"Server: {DNS_SERVER}",
                text_color=COLORS["text_primary"],
            )
            self.browser_hint_container.pack(
                anchor="center", pady=(10, 0), before=self.home_network_card
            )
        else:
            self.status_bar.configure(fg_color=COLORS["exposed_red"])
            self.status_label.configure(text="STATUS: DISCONNECTED")
            self.connect_button.configure(
                text="[ CONNECT ]",
                fg_color=COLORS["text_primary"],
                text_color=COLORS["deep_void"],
                hover_color=COLORS["text_muted"],
                border_color=COLORS["text_primary"],
            )
            self.server_label.configure(
                text="Server: AUTOMATIC",
                text_color=COLORS["text_muted"],
            )
            self.browser_hint_container.pack_forget()

    def _flush_browser_dns(self):
        """Open Chrome's cache inspection pages so the user can one-click
        Clear host cache AND Flush socket pools.

        Clearing only the host cache is not enough: Chrome keeps
        keep-alive TCP / HTTP2 / QUIC sockets open to already-resolved
        servers and reuses them for minutes without re-resolving DNS, so
        ads served over those existing connections leak through even
        after the host cache is empty. Flushing socket pools drops those
        reused connections.

        chrome:// URLs are a browser-internal scheme, not a web URI, so
        the OS URL handler usually can't resolve them (Windows shows a
        "Get an app to open this link" dialog). We have to launch a
        Chromium binary directly with the URLs as arguments.
        """
        urls = [
            "chrome://net-internals/#dns",
            "chrome://net-internals/#sockets",
        ]
        browser = self._find_chromium_browser()
        if browser:
            try:
                subprocess.Popen([browser, *urls], close_fds=True)
                return
            except Exception:
                pass
        # Last resort: hand off to the default browser. On Windows this
        # will likely show the "get an app" dialog for chrome:// URLs,
        # but on macOS it may still succeed if Chrome is the handler.
        for url in urls:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    @staticmethod
    def _find_chromium_browser():
        """Return a path to an installed Chromium-based browser, or
        None if none is found. Chrome is preferred; Edge and Brave are
        fallbacks since they also handle chrome:// URLs."""
        system = platform.system()
        if system == "Windows":
            candidates = [
                r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
                r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
                r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
            ]
            for raw in candidates:
                path = os.path.expandvars(raw)
                if path and os.path.exists(path):
                    return path
        elif system == "Darwin":
            candidates = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            ]
            for path in candidates:
                if os.path.exists(path):
                    return path
        else:
            for name in ("google-chrome", "chromium", "chromium-browser",
                         "microsoft-edge", "brave-browser"):
                path = shutil.which(name)
                if path:
                    return path
        return None

    def _set_home_network_busy(self, busy, button_text=None):
        self._home_network_request_in_flight = busy
        self.home_network_button.configure(
            state="disabled" if busy else "normal",
            text=button_text or self.home_network_button.cget("text"),
        )

    def _render_home_network(self, home_network, message="", error=""):
        data = home_network or self.auth.home_network or {}
        registered = bool(data.get("is_registered"))
        on_home_network = bool(data.get("is_on_home_network"))
        current_ip = data.get("current_ip", "--")
        registered_home = data.get("registered_home_network") or {}
        registered_ip = registered_home.get("registered_ip", "Not set")
        current_network = data.get("current_network_cidr", "--")
        registered_network = registered_home.get("network_cidr", "--")

        if on_home_network:
            badge_text = "AT HOME"
            badge_color = COLORS["shield_green"]
            status_text = "You are on your registered home network."
            status_color = COLORS["text_primary"]
        elif registered:
            badge_text = "AWAY"
            badge_color = COLORS["exposed_red"]
            status_text = "This network is not your registered home network."
            status_color = COLORS["text_primary"]
        else:
            badge_text = "NOT SET"
            badge_color = COLORS["text_muted"]
            status_text = "No home network is registered yet."
            status_color = COLORS["text_primary"]

        if error:
            badge_text = "UNAVAILABLE"
            badge_color = COLORS["exposed_red"]
            status_text = "We could not verify your home network status."
            status_color = COLORS["exposed_red"]

        self.home_network_badge.configure(text=badge_text, fg_color=badge_color)
        self.home_network_status_label.configure(text=status_text, text_color=status_color)
        self.home_network_detail_label.configure(
            text=(
                f"Current IP: {current_ip}\n"
                f"Current network: {current_network}\n"
                f"Registered IP: {registered_ip}\n"
                f"Registered network: {registered_network}"
            )
        )
        self.home_network_feedback_label.configure(
            text=error or message or "",
            text_color=COLORS["exposed_red"] if error else COLORS["shield_green"],
        )
        self.home_network_button.configure(
            text="UPDATE HOME NETWORK" if registered else "SET HOME NETWORK"
        )

    def refresh_home_network_status_async(self):
        if not self.auth.is_logged_in() or self._home_network_request_in_flight:
            return

        self._set_home_network_busy(True, self.home_network_button.cget("text"))

        def worker():
            success, home_network, error = self.auth.get_home_network_status()
            self.after(0, lambda: self._finish_home_network_refresh(success, home_network, error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_home_network_refresh(self, success, home_network, error):
        self._set_home_network_busy(False)
        if success:
            self._render_home_network(home_network)
        else:
            self._render_home_network(self.auth.home_network, error=error)

    def set_home_network(self, force=False):
        if not self.auth.is_logged_in() or self._home_network_request_in_flight:
            return
        self.home_network_feedback_label.configure(text="")

        def worker():
            success, home_network, message, error_code = self.auth.set_home_network(force=force)
            self.after(
                0,
                lambda: self._finish_set_home_network(success, home_network, message, error_code),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_set_home_network(self, success, home_network, message, error_code=""):
        self._set_home_network_busy(False)
        if success:
            self._render_home_network(
                home_network,
                message=message or "Home network updated successfully.",
            )
        elif error_code == "OUTSIDE_HOME_NETWORK":
            self._show_overwrite_confirmation()
        else:
            self._render_home_network(self.auth.home_network, error=message)

    def _show_overwrite_confirmation(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Overwrite Home Network?")
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["deep_void"])
        dialog.transient(self.master)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text="You are outside your registered home\nnetwork. Overwriting it will change which\nnetwork gets ad-blocking protection.",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_primary"],
            justify="center",
        ).pack(pady=(20, 16))
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)

        def on_cancel():
            dialog.destroy()
            self._render_home_network(self.auth.home_network, error="Home network update cancelled.")

        def on_confirm():
            dialog.destroy()
            self.set_home_network(force=True)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=120,
            fg_color=COLORS["text_muted"], hover_color="#666666",
            command=on_cancel,
        ).pack(side="left", expand=True, padx=4)
        ctk.CTkButton(
            btn_frame, text="Overwrite", width=120,
            fg_color=COLORS["exposed_red"], hover_color="#dc2626",
            text_color=COLORS["text_primary"],
            command=on_confirm,
        ).pack(side="right", expand=True, padx=4)

    def start_auth_check(self):
        self._check_auth_loop()

    def _check_auth_loop(self):
        if self.master.is_connected and not self.auth.is_authorized():
            success, error_msg = self.auth.authorize_device_access()
            if not success:
                self.disconnect()
                self.show_error(f"Authorization failed: {error_msg}")
            else:
                self._render_home_network(self.auth.home_network)
        self._auth_check_id = self.after(1000, self._check_auth_loop)

    def stop_auth_check(self):
        if self._auth_check_id:
            self.after_cancel(self._auth_check_id)
            self._auth_check_id = None

    def start_home_network_polling(self):
        if self._home_network_poll_id is not None:
            return

        self.refresh_home_network_status_async()
        self._schedule_home_network_poll()

    def _schedule_home_network_poll(self):
        self._home_network_poll_id = self.after(
            self.HOME_NETWORK_REFRESH_MS,
            self._home_network_poll_loop,
        )

    def _home_network_poll_loop(self):
        self._home_network_poll_id = None
        self.refresh_home_network_status_async()
        self._schedule_home_network_poll()

    def stop_home_network_polling(self):
        if self._home_network_poll_id is not None:
            self.after_cancel(self._home_network_poll_id)
            self._home_network_poll_id = None

    def show_error(self, message: str):
        self.status_label.configure(text=message)
