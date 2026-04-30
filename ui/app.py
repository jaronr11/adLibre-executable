import atexit
import customtkinter as ctk
from config import COLORS, DNS_SERVER
from services.auth_service import AuthService
from services.dns_service import DNSService
from ui.login_frame import LoginFrame
from ui.main_frame import MainFrame


class DNSChangerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("adLibre")
        self.geometry("420x760")
        self.configure(fg_color=COLORS["deep_void"])
        self.resizable(False, False)

        self.auth = AuthService()
        self.dns = DNSService(DNS_SERVER)
        # Recover from a hard-killed previous session: if DNS or IPv6 were
        # left in our "connected" state, reset them before this session
        # starts so the user isn't stuck with stale ad-blocking config.
        try:
            self.dns.disconnect()
        except Exception:
            pass
        self.dns.disable_ipv6()
        self.is_connected = False
        self._cleaned_up = False

        # Restore the user's network state when the app exits, however
        # it exits: closing the window, sys.exit, or interpreter shutdown.
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        atexit.register(self._cleanup)

        self.login_frame = LoginFrame(self, auth_service=self.auth, on_login_success=self.handle_login)
        self.main_frame = MainFrame(self, dns_service=self.dns, auth_service=self.auth, on_logout=self.handle_logout)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Check if already logged in (has saved tokens)
        if self.auth.is_logged_in():
            self.main_frame.set_user(self.auth.user)
            self.show_main()
            self.auth.start_periodic_tasks(interval_seconds=300)
            self.main_frame.start_auth_check()
            self.main_frame.start_home_network_polling()
        else:
            self.show_login()

    def show_login(self):
        self.main_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True, padx=28, pady=28)

    def show_main(self):
        self.login_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)

    def handle_login(self, user):
        """Called when OAuth login succeeds."""
        self.main_frame.set_user(user)
        self.show_main()
        # Start periodic tasks to refresh token and authorize device every 5 minutes
        self.auth.start_periodic_tasks(interval_seconds=300)
        # Start 1-second auth timestamp check
        self.main_frame.start_auth_check()
        self.main_frame.start_home_network_polling()

    def handle_logout(self):
        """Called when user logs out."""
        # Stop periodic tasks when logging out
        self.auth.stop_periodic_tasks()
        self.main_frame.stop_auth_check()
        self.main_frame.stop_home_network_polling()
        self.login_frame._reset_button()
        self.show_login()

    def _cleanup(self):
        """Restore DNS and IPv6 before the window is destroyed."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self.is_connected:
            try:
                self.dns.disconnect()
            except Exception:
                pass
        try:
            self.dns.enable_ipv6()
        except Exception:
            pass

    def _on_close(self):
        self._cleanup()
        try:
            self.auth.stop_periodic_tasks()
            self.main_frame.stop_auth_check()
            self.main_frame.stop_home_network_polling()
        except Exception:
            pass
        self.destroy()
