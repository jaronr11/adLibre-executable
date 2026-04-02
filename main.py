import sys
import platform

def ensure_admin():
    """On Windows, re-launch as admin if not already elevated."""
    if platform.system() != "Windows":
        return
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    # Re-launch the current process with elevation
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)

if __name__ == "__main__":
    ensure_admin()
    from ui.app import DNSChangerApp
    DNSChangerApp().mainloop()