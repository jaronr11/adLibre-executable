import platform
import subprocess

# Suppress the brief console window that flashes when subprocess spawns
# a child on Windows (we run as a windowed app, so any cmd/powershell/
# netsh call would otherwise pop a visible terminal).
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


class DNSService:
    def __init__(self, dns_server: str):
        self.dns_server = dns_server

    def _get_active_interface(self) -> str:
        """Return the name of the interface routing internet traffic.

        Falls back to "Wi-Fi" if detection fails so behavior matches the
        previous hard-coded default rather than erroring out.
        """
        try:
            if platform.system() == "Darwin":
                # BSD device of the default route, e.g. "en0".
                dev = subprocess.run(
                    "route -n get default | awk '/interface:/ {print $2}'",
                    shell=True, capture_output=True, text=True, check=False,
                    creationflags=_NO_WINDOW,
                ).stdout.strip()
                if dev:
                    # Map BSD device -> networksetup service name.
                    ports = subprocess.run(
                        "networksetup -listallhardwareports",
                        shell=True, capture_output=True, text=True, check=False,
                        creationflags=_NO_WINDOW,
                    ).stdout
                    name = None
                    for block in ports.split("\n\n"):
                        if f"Device: {dev}" in block:
                            for line in block.splitlines():
                                if line.startswith("Hardware Port:"):
                                    name = line.split(":", 1)[1].strip()
                                    break
                            break
                    if name:
                        return name
            else:
                ps = (
                    "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
                    "-ErrorAction SilentlyContinue | "
                    "Sort-Object RouteMetric | "
                    "Select-Object -First 1).InterfaceAlias"
                )
                name = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, check=False,
                    creationflags=_NO_WINDOW,
                ).stdout.strip()
                if name:
                    return name
        except Exception:
            pass
        return "Wi-Fi"

    def connect(self):
        iface = self._get_active_interface()
        if platform.system() == "Darwin":
            subprocess.run(f'networksetup -setdnsservers "{iface}" {self.dns_server}', shell=True, check=True, creationflags=_NO_WINDOW)
        else:
            subprocess.run(f'netsh interface ip set dns name="{iface}" static {self.dns_server}', shell=True, check=True, creationflags=_NO_WINDOW)
        self._flush_dns_cache()

    def disconnect(self):
        iface = self._get_active_interface()
        if platform.system() == "Darwin":
            subprocess.run(f'networksetup -setdnsservers "{iface}" empty', shell=True, check=True, creationflags=_NO_WINDOW)
        else:
            subprocess.run(f'netsh interface ip set dns name="{iface}" dhcp', shell=True, check=True, creationflags=_NO_WINDOW)
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
                iface = self._get_active_interface()
                subprocess.run(f'networksetup -setv6off "{iface}"', shell=True, check=False, creationflags=_NO_WINDOW)
            else:
                subprocess.run(
                    'powershell -Command "Disable-NetAdapterBinding -Name * -ComponentID ms_tcpip6"',
                    shell=True, check=False, creationflags=_NO_WINDOW,
                )
        except Exception:
            pass

    def enable_ipv6(self):
        """Re-enable IPv6 on all network adapters."""
        try:
            if platform.system() == "Darwin":
                iface = self._get_active_interface()
                subprocess.run(f'networksetup -setv6automatic "{iface}"', shell=True, check=False, creationflags=_NO_WINDOW)
            else:
                subprocess.run(
                    'powershell -Command "Enable-NetAdapterBinding -Name * -ComponentID ms_tcpip6"',
                    shell=True, check=False, creationflags=_NO_WINDOW,
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
                subprocess.run("dscacheutil -flushcache", shell=True, check=False, creationflags=_NO_WINDOW)
                subprocess.run("killall -HUP mDNSResponder", shell=True, check=False, creationflags=_NO_WINDOW)
            else:
                subprocess.run("ipconfig /flushdns", shell=True, check=False, creationflags=_NO_WINDOW)
        except Exception:
            pass
