import atexit
import logging
import logging.handlers
import signal
import sys
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from config import COLORS, DNS_SERVER
from services.auth_service import AuthService
from services.dns_service import DNSService
from ui.login_frame import LoginFrame
from ui.main_frame import MainFrame


def _setup_logging():
    """Send unhandled events to ~/.adlibre/adlibre.log.

    Windowed PyInstaller builds have no stdout/stderr, so without a file we'd
    have no visibility into recovery failures or shutdown-path errors.
    """
    log_path = Path.home() / ".adlibre" / "adlibre.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers if __init__ runs twice (e.g. dev reload).
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    return logging.getLogger("adlibre")


log = _setup_logging()


class DNSChangerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("adLibre")
        self.geometry("420x760")
        self.configure(fg_color=COLORS["deep_void"])
        self.resizable(False, False)

        self.auth = AuthService()
        self.dns = DNSService(DNS_SERVER)
        self.is_connected = False
        self._cleaned_up = False

        # If a previous session was force-killed (e.g. user shut down their
        # computer while connected), undo whatever it left behind: any
        # adapter still pointing at our DNS gets reset, and IPv6 is restored
        # to the user's pre-launch state. Loud failure if we can't fix it.
        self._recover_from_previous_session()
        self.dns.disable_ipv6()

        # Restore the user's network state when the app exits, however
        # it exits: closing the window, sys.exit, or interpreter shutdown.
        # Also catch SIGTERM/SIGINT so graceful kills (Task Manager "End task",
        # Ctrl-C in dev, `kill <pid>`) clean up before the process dies.
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        atexit.register(self._cleanup)
        self._install_signal_handlers()

        self.login_frame = LoginFrame(self, auth_service=self.auth, on_login_success=self.handle_login)
        self.main_frame = MainFrame(self, dns_service=self.dns, auth_service=self.auth, on_logout=self.handle_logout)

        # Check if already logged in (has saved tokens)
        if self.auth.is_logged_in():
            self.main_frame.set_user(self.auth.user)
            self.show_main()
            self.auth.start_periodic_tasks(interval_seconds=300)
            self.main_frame.start_auth_check()
            self.main_frame.start_home_network_polling()
        else:
            self.show_login()

    # ---------- crash recovery ----------

    def _recover_from_previous_session(self):
        """Roll back any DNS / IPv6 state left behind by a crashed prior run.

        Surfaces failures: writes to the log file and pops a dialog when the
        previous session's state can't be undone, so the user isn't left with
        broken internet and no idea why.
        """
        try:
            result = self.dns.recover_from_crash()
        except Exception as e:
            log.exception("recover_from_crash raised")
            messagebox.showwarning(
                "adLibre — couldn't restore network",
                "We tried to undo the previous session's network changes but "
                "hit an error.\n\n"
                f"Details: {e}\n\n"
                "If your internet isn't working, open Network settings and "
                "set DNS to automatic, then re-enable IPv6.",
            )
            return

        if result.get("recovered"):
            log.info(
                "Recovered from prior session — reset DNS on %s",
                result.get("interfaces_reset") or "<none>",
            )
        if result.get("errors"):
            log.warning("Recovery completed with errors: %s", result["errors"])
            messagebox.showwarning(
                "adLibre — partial recovery",
                "We restored your network mostly, but a few interfaces "
                "couldn't be reset:\n\n"
                + "\n".join(result["errors"][:5])
                + "\n\nIf your internet isn't working, set DNS to automatic in "
                "Network settings.",
            )

    # ---------- shutdown handling ----------

    def _install_signal_handlers(self):
        """Run cleanup on SIGTERM / SIGINT in addition to the X button.

        Covers `taskkill` (without /F), Ctrl-C from the console, and the
        SIGTERM that some OS shutdown sequences deliver before SIGKILL.
        Does NOT cover hard kills (Task Manager "End task" with /F, BSOD,
        power loss, or Windows session end without grace) — those are handled
        by recover_from_crash() on the next launch.
        """
        def handler(signum, _frame):
            log.info("received signal %s — running cleanup", signum)
            try:
                self._cleanup()
            finally:
                # Re-raise the default action so the OS sees the signal too.
                sys.exit(0)

        for sig_name in ("SIGTERM", "SIGINT", "SIGBREAK"):  # SIGBREAK is Windows-only
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                # signal.signal can fail if not on the main thread — fine to skip.
                pass

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
        # Start 1-second auth timestamp check
        self.main_frame.start_auth_check()
        self.main_frame.start_home_network_polling()

    def handle_logout(self):
        """Called when user logs out."""
        # Stop periodic tasks when logging out
        self.auth.stop_periodic_tasks()
        self.main_frame.stop_auth_check()
        self.main_frame.stop_home_network_polling()
        self.login_frame._reset_button()
        self.show_login()

    def _cleanup(self):
        """Restore DNS and IPv6 before the window is destroyed."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self.is_connected:
            try:
                self.dns.disconnect()
            except Exception:
                log.exception("disconnect during cleanup failed")
        try:
            self.dns.restore_ipv6()
        except Exception:
            log.exception("restore_ipv6 during cleanup failed")

    def _on_close(self):
        self._cleanup()
        try:
            self.auth.stop_periodic_tasks()
            self.main_frame.stop_auth_check()
            self.main_frame.stop_home_network_polling()
        except Exception:
            pass
        self.destroy()
