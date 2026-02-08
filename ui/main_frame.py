import customtkinter as ctk
import webbrowser
from config import COLORS, FONT, DNS_SERVER, ADLIBRE_WEBSITE

class MainFrame(ctk.CTkFrame):
    def __init__(self, master, dns_service):
        super().__init__(master, fg_color=COLORS["deep_void"])
        self.master = master
        self.dns_service = dns_service
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

        # ----------------- Clickable Header -----------------
        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(anchor="center")

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

        # Make labels clickable too
        for widget in (ad_label, libre_label):
            widget.bind("<Button-1>", open_site)
            widget.configure(cursor="hand2")

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
