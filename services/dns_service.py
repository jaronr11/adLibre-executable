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
        """Run command with admin privileges on Windows via UAC prompt.
        
        Returns True if the user accepted the UAC prompt, False if they denied it.
        """
        import time
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "cmd.exe",
            f'/c {command}',
            None,
            0  # SW_HIDE
        )
        # ShellExecuteW returns <= 32 on failure (including UAC denial = error code 5)
        if result <= 32:
            return False
        # Give the elevated process a moment to run before returning
        time.sleep(1)
        return True

    def connect(self):
        if platform.system() == "Darwin":
            subprocess.run(f'networksetup -setdnsservers Wi-Fi {self.dns_server}', shell=True, check=True)
        else:
            command = f'netsh interface ip set dns name="Wi-Fi" static {self.dns_server}'
            if not self._is_admin_windows():
                success = self._run_as_admin_windows(command)
                if not success:
                    raise PermissionError("Administrator privileges are required to change DNS settings.")
            else:
                subprocess.run(command, shell=True, check=True)

    def disconnect(self):
        if platform.system() == "Darwin":
            subprocess.run('networksetup -setdnsservers Wi-Fi empty', shell=True, check=True)
        else:
            command = 'netsh interface ip set dns name="Wi-Fi" dhcp'
            if not self._is_admin_windows():
                success = self._run_as_admin_windows(command)
                if not success:
                    raise PermissionError("Administrator privileges are required to change DNS settings.")
            else:
                subprocess.run(command, shell=True, check=True)