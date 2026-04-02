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
API_BASES = [
    base.strip()
    for base in os.getenv(
        "ADLIBRE_API_BASES",
        "http://45.79.9.188,https://adlibre.org",
    ).split(",")
    if base.strip()
]
API_BASE = API_BASES[0]
ADLIBRE_WEBSITE = "https://adlibre.org/"
