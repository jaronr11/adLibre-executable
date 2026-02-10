import webbrowser
import threading
import customtkinter as ctk
from config import COLORS, FONT, ADLIBRE_WEBSITE


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, auth_service, on_login_success):
        super().__init__(master, fg_color="transparent")
        self.auth = auth_service
        self.on_login_success = on_login_success

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

        # Status label (shown during login)
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"]
        )
        self.status_label.pack(anchor="w", pady=(0, 10))

        # Error label
        self.error_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["exposed_red"]
        )
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
            command=self.start_login
        )
        self.login_button.pack(fill="x", pady=(10, 0))

    def start_login(self):
        """Start the OAuth login flow in a background thread."""
        self.set_error("")
        self.login_button.configure(state="disabled", text="[ WAITING... ]")
        self.status_label.configure(text="Complete login in your browser...")

        # Run login in background thread to not block UI
        thread = threading.Thread(target=self._do_login, daemon=True)
        thread.start()

    def _do_login(self):
        """Perform login (runs in background thread)."""
        success = self.auth.login(
            on_success=self._on_success,
            on_error=self._on_error,
        )

        if not success:
            self._reset_button()

    def _on_success(self, user):
        """Called on successful login (from background thread)."""
        self.after(0, lambda: self._handle_success(user))

    def _on_error(self, error_msg):
        """Called on login error (from background thread)."""
        self.after(0, lambda: self._handle_error(error_msg))

    def _handle_success(self, user):
        """Handle successful login on main thread."""
        self.status_label.configure(text="")
        self.on_login_success(user)

    def _handle_error(self, error_msg):
        """Handle login error on main thread."""
        self.set_error(error_msg)
        self._reset_button()

    def _reset_button(self):
        """Reset login button to initial state."""
        self.after(0, lambda: self.login_button.configure(
            state="normal",
            text="[ LOGIN ]"
        ))
        self.after(0, lambda: self.status_label.configure(text=""))

    def set_error(self, msg: str):
        self.error_label.configure(text=msg)