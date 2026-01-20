import customtkinter as ctk
import subprocess
import platform

# ----------------- Theme Setup -----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Cross-platform fonts
if platform.system() == "Darwin":  # macOS
    FONT_HEADING = "Helvetica Neue"
    FONT_BODY = "Helvetica Neue"
else:  # Windows
    FONT_HEADING = "Segoe UI"
    FONT_BODY = "Segoe UI"

# Color palette
COLORS = {
    "bg_dark": "#111111",
    "bg_card": "#1a1a1a",
    "accent_green": "#22c55e",
    "accent_green_hover": "#16a34a",
    "accent_gray": "#525252",
    "text_primary": "#ffffff",
    "text_secondary": "#a3a3a3",
    "text_muted": "#636363",
}

# Hardcoded DNS
DNS_SERVER = "96.126.124.117"

class AdLibreApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AdLibre")
        self.geometry("400x480")
        self.configure(fg_color=COLORS["bg_dark"])
        self.resizable(False, False)
        
        # State
        self.is_connected = False
        
        self.create_ui()
    
    def create_ui(self):
        # ----------------- Main Container -----------------
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=32, pady=32)
        
        # ----------------- Header with icon -----------------
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 24))
        
        # App icon
        self.icon_label = ctk.CTkLabel(
            self.header_frame,
            text="🛡️",
            font=ctk.CTkFont(size=32),
        )
        self.icon_label.pack(side="left")
        
        # App name
        self.app_name = ctk.CTkLabel(
            self.header_frame,
            text="AdLibre",
            font=ctk.CTkFont(family=FONT_HEADING, size=22, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.app_name.pack(side="left", padx=(12, 0))
        
        # ----------------- Status Card -----------------
        self.status_card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["bg_card"],
            corner_radius=20
        )
        self.status_card.pack(fill="x", pady=(0, 24))
        
        self.status_inner = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.status_inner.pack(fill="x", padx=24, pady=28)
        
        # Big shield icon
        self.shield_icon = ctk.CTkLabel(
            self.status_inner,
            text="🛡️",
            font=ctk.CTkFont(size=56),
        )
        self.shield_icon.pack(pady=(0, 16))
        
        # Status title
        self.status_title = ctk.CTkLabel(
            self.status_inner,
            text="Ad Blocking Off",
            font=ctk.CTkFont(family=FONT_HEADING, size=20, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.status_title.pack(pady=(0, 4))
        
        # Status subtitle
        self.status_subtitle = ctk.CTkLabel(
            self.status_inner,
            text="Connect to start blocking ads",
            font=ctk.CTkFont(family=FONT_BODY, size=13),
            text_color=COLORS["text_muted"]
        )
        self.status_subtitle.pack(pady=(0, 20))
        
        # Status pill
        self.status_pill = ctk.CTkFrame(
            self.status_inner,
            fg_color=COLORS["accent_gray"],
            corner_radius=20,
            height=32
        )
        self.status_pill.pack()
        
        self.status_pill_label = ctk.CTkLabel(
            self.status_pill,
            text="  ○  Disconnected  ",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.status_pill_label.pack(padx=16, pady=6)
        
        # ----------------- Connect Button -----------------
        self.connect_button = ctk.CTkButton(
            self.main_container,
            text="Connect",
            font=ctk.CTkFont(family=FONT_BODY, size=16, weight="bold"),
            fg_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            hover_color=COLORS["accent_green_hover"],
            height=56,
            corner_radius=14,
            command=self.toggle_connection
        )
        self.connect_button.pack(fill="x", pady=(0, 16))
        
        # ----------------- Info text -----------------
        self.info_label = ctk.CTkLabel(
            self.main_container,
            text="Block ads across all your apps and browsers\nwith one tap.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=COLORS["text_muted"],
            justify="center"
        )
        self.info_label.pack(pady=(8, 0))
    
    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(
                    f'networksetup -setdnsservers Wi-Fi {DNS_SERVER}',
                    shell=True,
                    check=True
                )
            else:  # Windows
                subprocess.run(
                    f'netsh interface ip set dns name="Wi-Fi" static {DNS_SERVER}',
                    shell=True,
                    check=True
                )
            
            self.is_connected = True
            self.update_connection_ui()
            
        except Exception as e:
            self.show_error(str(e))
    
    def disconnect(self):
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(
                    'networksetup -setdnsservers Wi-Fi empty',
                    shell=True,
                    check=True
                )
            else:  # Windows
                subprocess.run(
                    'netsh interface ip set dns name="Wi-Fi" dhcp',
                    shell=True,
                    check=True
                )
            
            self.is_connected = False
            self.update_connection_ui()
            
        except Exception as e:
            self.show_error(str(e))
    
    def update_connection_ui(self):
        if self.is_connected:
            self.status_title.configure(text="Ad Blocking On")
            self.status_subtitle.configure(text="Ads are being blocked")
            self.status_pill.configure(fg_color=COLORS["accent_green"])
            self.status_pill_label.configure(text="  ●  Connected  ")
            self.connect_button.configure(
                text="Disconnect",
                fg_color=COLORS["bg_card"],
                hover_color="#262626"
            )
        else:
            self.status_title.configure(text="Ad Blocking Off")
            self.status_subtitle.configure(text="Connect to start blocking ads")
            self.status_pill.configure(fg_color=COLORS["accent_gray"])
            self.status_pill_label.configure(text="  ○  Disconnected  ")
            self.connect_button.configure(
                text="Connect",
                fg_color=COLORS["accent_green"],
                hover_color=COLORS["accent_green_hover"]
            )
    
    def show_error(self, message):
        self.status_title.configure(text="Something went wrong")
        self.status_subtitle.configure(text="Please try again")

# ----------------- Run App -----------------
if __name__ == "__main__":
    app = AdLibreApp()
    app.mainloop()