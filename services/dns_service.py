import platform
import subprocess

class DNSService:
    def __init__(self, dns_server: str):
        self.dns_server = dns_server

    def connect(self):
        if platform.system() == "Darwin":
            subprocess.run(f'networksetup -setdnsservers Wi-Fi {self.dns_server}', shell=True, check=True)
        else:
            subprocess.run(f'netsh interface ip set dns name="Wi-Fi" static {self.dns_server}', shell=True, check=True)

    def disconnect(self):
        if platform.system() == "Darwin":
            subprocess.run('networksetup -setdnsservers Wi-Fi empty', shell=True, check=True)
        else:
            subprocess.run('netsh interface ip set dns name="Wi-Fi" dhcp', shell=True, check=True)
