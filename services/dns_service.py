import platform
import subprocess
import sys
import ctypes

class DNSService:
    def __init__(self, dns_server: str):
        self.dns_server = dns_server

    def _is_admin_windows(self):
        """Check if the script is running with admin privileges on Windows"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def _run_as_admin_windows(self, command):
        """Re-launch the command with admin privileges on Windows"""
        if not self._is_admin_windows():
            # Use ShellExecute to prompt for elevation
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas",  # Request elevation
                "cmd.exe",
                f'/c {command}',
                None,
                0  # SW_HIDE
            )
            return True
        return False

    def connect(self):
        if platform.system() == "Darwin":
            subprocess.run(f'networksetup -setdnsservers Wi-Fi {self.dns_server}', shell=True, check=True)
        else:
            command = f'netsh interface ip set dns name="Wi-Fi" static {self.dns_server}'
            if not self._is_admin_windows():
                self._run_as_admin_windows(command)
            else:
                subprocess.run(command, shell=True, check=True)

    def disconnect(self):
        if platform.system() == "Darwin":
            subprocess.run('networksetup -setdnsservers Wi-Fi empty', shell=True, check=True)
        else:
            command = 'netsh interface ip set dns name="Wi-Fi" dhcp'
            if not self._is_admin_windows():
                self._run_as_admin_windows(command)
            else:
                subprocess.run(command, shell=True, check=True)