import customtkinter as ctk
import subprocess
import platform

# ----------------- Theme Setup -----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Cross-platform fonts
if platform.system() == "Darwin":  # macOS
    FONT_BOLD = "Helvetica Neue"
    FONT_MONO = "Menlo"
else:  # Windows
    FONT_BOLD = "Arial Black"
    FONT_MONO = "Consolas"

# Color palette
COLORS = {
    "bg_dark": "#0a0a0a",
    "bg_hover": "#1a1a1a",
    "accent_green": "#22c55e",
    "accent_green_hover": "#16a34a",
    "accent_red": "#ef4444",
    "text_primary": "#ffffff",
    "text_muted": "#525252",
}

# Hardcoded DNS
DNS_SERVER = "96.126.124.117"

class DNSChangerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("DNS_SHIELD")
        self.geometry("420x480")
        self.configure(fg_color=COLORS["bg_dark"])
        self.resizable(False, False)
        
        # State
        self.is_connected = False
        
        self.create_ui()
    
    def create_ui(self):
        # ----------------- Status Bar -----------------
        self.status_bar = ctk.CTkFrame(self, height=44, fg_color=COLORS["accent_red"], corner_radius=0)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="STATUS: EXPOSED",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.status_label.pack(side="left", padx=20)
        
        self.status_indicator = ctk.CTkLabel(
            self.status_bar,
            text="●",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_primary"]
        )
        self.status_indicator.pack(side="right", padx=20)
        
        # ----------------- Main Container -----------------
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=28, pady=28)
        
        # ----------------- Header -----------------
        self.title_label = ctk.CTkLabel(
            self.main_container,
            text="DNS_",
            font=ctk.CTkFont(family=FONT_BOLD, size=52, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.title_label.pack(anchor="w")
        
        self.subtitle_label = ctk.CTkLabel(
            self.main_container,
            text="SHIELD",
            font=ctk.CTkFont(family=FONT_BOLD, size=52, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.subtitle_label.pack(anchor="w", pady=(0, 8))
        
        self.tagline_label = ctk.CTkLabel(
            self.main_container,
            text="Secure your connection",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.tagline_label.pack(anchor="w", pady=(0, 48))
        
        # ----------------- Connect Button -----------------
        self.connect_button = ctk.CTkButton(
            self.main_container,
            text="[ CONNECT ]",
            font=ctk.CTkFont(family=FONT_MONO, size=14, weight="bold"),
            fg_color=COLORS["text_primary"],
            text_color=COLORS["bg_dark"],
            hover_color=COLORS["text_muted"],
            height=72,
            corner_radius=0,
            border_width=3,
            border_color=COLORS["text_primary"],
            command=self.toggle_connection
        )
        self.connect_button.pack(fill="x", pady=(0, 24))
        
        # ----------------- Server Info -----------------
        self.server_label = ctk.CTkLabel(
            self.main_container,
            text=f"Server: {DNS_SERVER}",
            font=ctk.CTkFont(family=FONT_MONO, size=12),
            text_color=COLORS["text_muted"]
        )
        self.server_label.pack(anchor="w")
    
    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        try:
            # Detect network interface based on platform
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
            # Green everything
            self.status_bar.configure(fg_color=COLORS["accent_green"])
            self.status_label.configure(text="STATUS: PROTECTED")
            self.connect_button.configure(
                text="[ DISCONNECT ]",
                fg_color=COLORS["accent_green"],
                text_color=COLORS["text_primary"],
                hover_color=COLORS["accent_green_hover"],
                border_color=COLORS["accent_green"]
            )
        else:
            # Back to default
            self.status_bar.configure(fg_color=COLORS["accent_red"])
            self.status_label.configure(text="STATUS: EXPOSED")
            self.connect_button.configure(
                text="[ CONNECT ]",
                fg_color=COLORS["text_primary"],
                text_color=COLORS["bg_dark"],
                hover_color=COLORS["text_muted"],
                border_color=COLORS["text_primary"]
            )
    
    def show_error(self, message):
        self.status_label.configure(text=f"ERROR: {message[:30]}")

# ----------------- Run App -----------------
if __name__ == "__main__":
    app = DNSChangerApp()
    app.mainloop()