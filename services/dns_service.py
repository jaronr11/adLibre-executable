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
        self._flush_dns_cache()

    def disconnect(self):
        if platform.system() == "Darwin":
            subprocess.run('networksetup -setdnsservers Wi-Fi empty', shell=True, check=True)
        else:
            subprocess.run('netsh interface ip set dns name="Wi-Fi" dhcp', shell=True, check=True)
        self._flush_dns_cache()

    def _flush_dns_cache(self):
        """Flush the OS DNS resolver cache.

        Switching the system DNS server alone is not enough: any domain
        the OS has already resolved stays cached until its TTL expires
        (often up to ~15 minutes for ad/tracker domains), so ad-blocking
        appears to take effect slowly after CONNECT. Flushing forces
        subsequent lookups to go through the newly-selected DNS server
        immediately.

        Best-effort: failures here are swallowed because the DNS server
        change has already succeeded and we don't want to fail the whole
        connect/disconnect flow over a cache flush.
        """
        try:
            if platform.system() == "Darwin":
                subprocess.run("dscacheutil -flushcache", shell=True, check=False)
                subprocess.run("killall -HUP mDNSResponder", shell=True, check=False)
            else:
                subprocess.run("ipconfig /flushdns", shell=True, check=False)
        except Exception:
            pass
