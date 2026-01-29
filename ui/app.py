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

        self.login_frame = LoginFrame(self, on_login=self.handle_login)
        self.main_frame = MainFrame(self, dns_service=self.dns)

        self.show_login()

    def show_login(self):
        self.main_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True, padx=28, pady=28)

    def show_main(self):
        self.login_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)

    def handle_login(self, username: str, password: str):
        if self.auth.login(username, password):
            self.show_main()
        else:
            self.login_frame.set_error("Invalid credentials")
