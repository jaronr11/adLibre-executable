import os
import platform
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

FONT = "Helvetica Neue" if platform.system() == "Darwin" else "Segoe UI Black"

COLORS = {
    "deep_void": "#0a0a0a",
    "shield_green": "#22c55e",
    "shield_green_hover": "#16a34a",
    "exposed_red": "#ef4444",
    "text_primary": "#f8f9fa",
    "text_muted": "#525252",
}

DNS_SERVER = "96.126.124.117"
API_BASE = os.getenv("ADLIBRE_API_BASE", "https://adlibre.org")
ADLIBRE_WEBSITE = "https://adlibre.org/"
