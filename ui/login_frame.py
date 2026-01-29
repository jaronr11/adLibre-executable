import webbrowser
import customtkinter as ctk
from config import COLORS, FONT, ADLIBRE_WEBSITE

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login):
        super().__init__(master, fg_color="transparent")
        self.on_login = on_login

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(anchor="w", pady=(10, 24))

        ctk.CTkLabel(
            header, text="ad",
            font=ctk.CTkFont(family=FONT, size=52, weight="bold"),
            text_color=COLORS["deep_void"],
            fg_color=COLORS["shield_green"],
            corner_radius=6, padx=10, pady=2
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="Libre",
            font=ctk.CTkFont(family=FONT, size=52, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text="One subscription. All your devices. No ads.",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 24))

        self.username = ctk.CTkEntry(self, placeholder_text="Email", height=44, corner_radius=6)
        self.username.pack(fill="x", pady=(0, 12))

        self.password = ctk.CTkEntry(self, placeholder_text="Password", show="•", height=44, corner_radius=6)
        self.password.pack(fill="x", pady=(0, 18))

        self.error_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color=COLORS["exposed_red"])
        self.error_label.pack(anchor="w", pady=(0, 10))

        signup_row = ctk.CTkFrame(self, fg_color="transparent")
        signup_row.pack(pady=(18, 0))

        ctk.CTkLabel(signup_row, text="Don't have an account?",
                     font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]).pack(side="left")

        signup_link = ctk.CTkLabel(signup_row, text=" Sign up now!",
                                   font=ctk.CTkFont(size=12, underline=True),
                                   text_color=COLORS["shield_green"], cursor="hand2")
        signup_link.pack(side="left")
        signup_link.bind("<Button-1>", lambda _e: webbrowser.open(ADLIBRE_WEBSITE))

        self.login_button = ctk.CTkButton(
            self, text="[ LOGIN ]",
            font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
            fg_color=COLORS["text_primary"],
            text_color=COLORS["deep_void"],
            hover_color=COLORS["text_muted"],
            height=60, corner_radius=0,
            border_width=3, border_color=COLORS["text_primary"],
            command=self.submit
        )
        self.login_button.pack(fill="x", pady=(10, 0))

        master.bind("<Return>", lambda _e: self.submit())

    def submit(self):
        self.set_error("")
        self.on_login(self.username.get().strip(), self.password.get())

    def set_error(self, msg: str):
        self.error_label.configure(text=msg)
