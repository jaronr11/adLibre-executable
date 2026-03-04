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
        self.geometry("420x520")
        self.configure(fg_color=COLORS["deep_void"])
        self.resizable(False, False)

        self.auth = AuthService()
        self.dns = DNSService(DNS_SERVER)
        self.is_connected = False

        self.login_frame = LoginFrame(self, auth_service=self.auth, on_login_success=self.handle_login)
        self.main_frame = MainFrame(self, dns_service=self.dns, auth_service=self.auth, on_logout=self.handle_logout)

        # Check if already logged in (has saved tokens)
        if self.auth.is_logged_in():
            self.main_frame.set_user(self.auth.user)
            self.show_main()
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

    def handle_logout(self):
        """Called when user logs out."""
        # Stop periodic tasks when logging out
        self.auth.stop_periodic_tasks()
        self.login_frame._reset_button()
        self.show_login()