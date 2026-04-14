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

    def disable_ipv6(self):
        """Disable IPv6 on all network adapters.

        IPv6 bypasses the IPv4 DNS server we set, so domains that resolve
        over IPv6 skip ad-blocking entirely.  Disabling IPv6 forces all
        lookups through our ad-blocking DNS.

        Uses PowerShell Disable-NetAdapterBinding on Windows to disable
        IPv6 across all adapters (not just Wi-Fi).
        """
        try:
            if platform.system() == "Darwin":
                subprocess.run("networksetup -setv6off Wi-Fi", shell=True, check=False)
            else:
                subprocess.run(
                    'powershell -Command "Disable-NetAdapterBinding -Name * -ComponentID ms_tcpip6"',
                    shell=True, check=False,
                )
        except Exception:
            pass

    def enable_ipv6(self):
        """Re-enable IPv6 on all network adapters."""
        try:
            if platform.system() == "Darwin":
                subprocess.run("networksetup -setv6automatic Wi-Fi", shell=True, check=False)
            else:
                subprocess.run(
                    'powershell -Command "Enable-NetAdapterBinding -Name * -ComponentID ms_tcpip6"',
                    shell=True, check=False,
                )
        except Exception:
            pass

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
