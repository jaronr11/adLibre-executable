import customtkinter as ctk
import webbrowser
from config import COLORS, FONT, DNS_SERVER, ADLIBRE_WEBSITE


class MainFrame(ctk.CTkFrame):
    def __init__(self, master, dns_service, auth_service, on_logout):
        super().__init__(master, fg_color=COLORS["deep_void"])
        self.master = master
        self.dns_service = dns_service
        self.auth = auth_service
        self.on_logout = on_logout
        self.create_ui()

    def create_ui(self):
        # ----------------- Status Bar -----------------
        self.status_bar = ctk.CTkFrame(self, height=44, fg_color=COLORS["exposed_red"], corner_radius=0)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="STATUS: DISCONNECTED",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.status_label.pack(side="left", padx=20)

        ctk.CTkLabel(
            self.status_bar,
            text="●",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_primary"]
        ).pack(side="right", padx=20)

        # ----------------- Body -----------------
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(expand=True)

        # Header with logo and logout button
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
            pady=2
        )
        ad_label.pack(side="left")

        libre_label = ctk.CTkLabel(
            header,
            text="Libre",
            font=ctk.CTkFont(family=FONT, size=52, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        libre_label.pack(side="left")

        # Logout button
        self.logout_button = ctk.CTkButton(
            header_row,
            text="Logout",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=COLORS["text_muted"],
            hover_color=COLORS["deep_void"],
            width=60,
            height=28,
            command=self._do_logout
        )
        self.logout_button.pack(side="right", padx=(0, 10))

        # Welcome message with username
        self.welcome_label = ctk.CTkLabel(
            body,
            text="Secure your connection",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.welcome_label.pack(anchor="w", pady=(0, 48))

        # ----------------- Connect Button -----------------
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
            command=self.toggle_connection
        )
        self.connect_button.pack(anchor="center", pady=(24, 12))

        # ----------------- Server Info -----------------
        self.server_label = ctk.CTkLabel(
            body,
            text="Server: AUTOMATIC",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
            anchor="center"
        )
        self.server_label.pack(anchor="center")

        self.update_connection_ui()

    def set_user(self, user):
        """Update UI with logged-in user info."""
        if user and user.get("username"):
            self.welcome_label.configure(text=f"Welcome, {user['username']}")
        else:
            self.welcome_label.configure(text="Secure your connection")

    def _do_logout(self):
        """Handle logout."""
        self.auth.logout()
        self.on_logout()

    def toggle_connection(self):
        if self.master.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        try:
            self.dns_service.connect()
            self.master.is_connected = True
            self.update_connection_ui()
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
                border_color=COLORS["shield_green"]
            )
            self.server_label.configure(
                text=f"Server: {DNS_SERVER}",
                text_color=COLORS["text_primary"]
            )
        else:
            self.status_bar.configure(fg_color=COLORS["exposed_red"])
            self.status_label.configure(text="STATUS: DISCONNECTED")
            self.connect_button.configure(
                text="[ CONNECT ]",
                fg_color=COLORS["text_primary"],
                text_color=COLORS["deep_void"],
                hover_color=COLORS["text_muted"],
                border_color=COLORS["text_primary"]
            )
            self.server_label.configure(
                text="Server: AUTOMATIC",
                text_color=COLORS["text_muted"]
            )

    def show_error(self, message: str):
        self.status_label.configure(text="ERROR (see console)")
        print("ERROR:", message)