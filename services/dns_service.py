import json
import platform
import re
import subprocess
from pathlib import Path

# Suppress the brief console window that flashes when subprocess spawns
# a child on Windows (we run as a windowed app, so any cmd/powershell/
# netsh call would otherwise pop a visible terminal).
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


class DNSService:
    # Persists what we changed (which interface, original DNS servers, original
    # IPv6 state) so a crashed/force-killed previous session can be cleaned up
    # on next launch — and so we can restore the user's actual prior DNS
    # instead of always blanking it back to DHCP.
    STATE_FILE = Path.home() / ".adlibre" / "dns_state.json"

    def __init__(self, dns_server: str):
        self.dns_server = dns_server

    # ---------- state file ----------

    def _load_state(self) -> dict:
        if not self.STATE_FILE.exists():
            return {}
        try:
            return json.loads(self.STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict):
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            if state:
                self.STATE_FILE.write_text(json.dumps(state))
            elif self.STATE_FILE.exists():
                self.STATE_FILE.unlink()
        except OSError:
            pass

    # ---------- interface detection ----------

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

    def _list_all_interfaces(self) -> list:
        """Enumerate every network interface on the system."""
        try:
            if platform.system() == "Darwin":
                out = subprocess.run(
                    "networksetup -listallnetworkservices",
                    shell=True, capture_output=True, text=True, check=False,
                ).stdout
                names = []
                for line in out.splitlines()[1:]:  # skip the leading "An asterisk..." note
                    name = line.lstrip("*").strip()
                    if name:
                        names.append(name)
                return names
            else:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-NetAdapter | Select-Object -ExpandProperty Name"],
                    capture_output=True, text=True, check=False, creationflags=_NO_WINDOW,
                ).stdout
                return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception:
            return []

    # ---------- DNS read ----------

    def _read_current_dns(self, iface: str) -> dict:
        """Return {'mode': 'static'|'dhcp', 'servers': [...]} for iface.

        Best-effort: returns {'mode': 'dhcp', 'servers': []} on parse failure.
        """
        try:
            if platform.system() == "Darwin":
                out = subprocess.run(
                    f'networksetup -getdnsservers "{iface}"',
                    shell=True, capture_output=True, text=True, check=False,
                ).stdout.strip()
                if not out or "any dns servers" in out.lower():
                    return {"mode": "dhcp", "servers": []}
                servers = [line.strip() for line in out.splitlines() if line.strip()]
                return {"mode": "static", "servers": servers}
            else:
                out = subprocess.run(
                    f'netsh interface ipv4 show dnsservers name="{iface}"',
                    shell=True, capture_output=True, text=True, check=False,
                    creationflags=_NO_WINDOW,
                ).stdout
                if "statically" not in out.lower():
                    return {"mode": "dhcp", "servers": []}
                servers = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", out)
                return {"mode": "static", "servers": servers} if servers else {"mode": "dhcp", "servers": []}
        except Exception:
            return {"mode": "dhcp", "servers": []}

    def _read_ipv6_enabled(self) -> bool:
        """Best-effort: was IPv6 enabled before we touched it? Defaults True on failure."""
        try:
            if platform.system() == "Darwin":
                iface = self._get_active_interface()
                out = subprocess.run(
                    f'networksetup -getinfo "{iface}"',
                    shell=True, capture_output=True, text=True, check=False,
                ).stdout
                for line in out.splitlines():
                    if line.startswith("IPv6:"):
                        return "off" not in line.lower()
                return True
            else:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-NetAdapterBinding -ComponentID ms_tcpip6 "
                     "| Where-Object Enabled -eq $true | Measure-Object).Count"],
                    capture_output=True, text=True, check=False, creationflags=_NO_WINDOW,
                ).stdout.strip()
                try:
                    return int(out) > 0
                except ValueError:
                    return True
        except Exception:
            return True

    # ---------- DNS modification primitives ----------

    def _set_dns_static(self, iface: str, servers: list):
        """Set the given interface to use the given static DNS servers."""
        if platform.system() == "Darwin":
            subprocess.run(
                f'networksetup -setdnsservers "{iface}" {" ".join(servers)}',
                shell=True, check=True, creationflags=_NO_WINDOW,
            )
        else:
            subprocess.run(
                f'netsh interface ip set dns name="{iface}" static {servers[0]}',
                shell=True, check=True, creationflags=_NO_WINDOW,
            )
            for srv in servers[1:]:
                subprocess.run(
                    f'netsh interface ip add dns name="{iface}" {srv}',
                    shell=True, check=False, creationflags=_NO_WINDOW,
                )

    def _set_dns_dhcp(self, iface: str):
        """Reset the given interface to automatic DNS (DHCP)."""
        if platform.system() == "Darwin":
            subprocess.run(
                f'networksetup -setdnsservers "{iface}" empty',
                shell=True, check=True, creationflags=_NO_WINDOW,
            )
        else:
            subprocess.run(
                f'netsh interface ip set dns name="{iface}" dhcp',
                shell=True, check=True, creationflags=_NO_WINDOW,
            )

    # ---------- connect / disconnect ----------

    def connect(self):
        iface = self._get_active_interface()
        # Capture original DNS before modifying — but only if we don't already
        # have a captured original (which would be lost otherwise on reconnect).
        state = self._load_state()
        if "original_dns" not in state:
            current = self._read_current_dns(iface)
            already_ours = (
                current["mode"] == "static"
                and current["servers"] == [self.dns_server]
            )
            if not already_ours:
                state["original_dns"] = current
                state["interface"] = iface
                self._save_state(state)
        self._set_dns_static(iface, [self.dns_server])
        self._flush_dns_cache()

    def disconnect(self):
        """Restore DNS on every adapter we may have touched.

        Restores the captured original DNS on the recorded interface, then
        sweeps every other adapter for stale "= our DNS server" entries left
        behind by a previous session on a different interface and resets them
        to DHCP. Always clears the captured DNS state at the end.
        """
        state = self._load_state()
        original = state.get("original_dns")
        recorded_iface = state.get("interface")
        active_iface = self._get_active_interface()
        primary_iface = recorded_iface or active_iface

        if original and original.get("mode") == "static" and original.get("servers"):
            self._set_dns_static(primary_iface, original["servers"])
        else:
            self._set_dns_dhcp(primary_iface)

        # Sweep every other adapter currently pointing at our DNS — covers the
        # "user moved between Wi-Fi/Ethernet/VPN" case where the modified
        # interface no longer matches the active one.
        for other in self._list_all_interfaces():
            if other == primary_iface:
                continue
            current = self._read_current_dns(other)
            if current["mode"] == "static" and self.dns_server in current["servers"]:
                try:
                    self._set_dns_dhcp(other)
                except Exception:
                    pass

        if "original_dns" in state:
            state.pop("original_dns", None)
            state.pop("interface", None)
            self._save_state(state)
        self._flush_dns_cache()

    # ---------- IPv6 ----------

    def disable_ipv6(self):
        """Disable IPv6 on all network adapters.

        IPv6 bypasses the IPv4 DNS server we set, so domains that resolve
        over IPv6 skip ad-blocking entirely. Disabling IPv6 forces all
        lookups through our ad-blocking DNS.

        Captures the user's pre-launch IPv6 state on first call so
        :meth:`restore_ipv6` can put it back exactly as it was.
        """
        state = self._load_state()
        if "original_ipv6_enabled" not in state:
            state["original_ipv6_enabled"] = self._read_ipv6_enabled()
            self._save_state(state)
        try:
            if platform.system() == "Darwin":
                iface = self._get_active_interface()
                subprocess.run(
                    f'networksetup -setv6off "{iface}"',
                    shell=True, check=False, creationflags=_NO_WINDOW,
                )
            else:
                subprocess.run(
                    'powershell -Command "Disable-NetAdapterBinding -Name * -ComponentID ms_tcpip6"',
                    shell=True, check=False, creationflags=_NO_WINDOW,
                )
        except Exception:
            pass

    def enable_ipv6(self):
        """Forcibly enable IPv6 on all adapters (used by the exempt-device button)."""
        try:
            if platform.system() == "Darwin":
                iface = self._get_active_interface()
                subprocess.run(
                    f'networksetup -setv6automatic "{iface}"',
                    shell=True, check=False, creationflags=_NO_WINDOW,
                )
            else:
                subprocess.run(
                    'powershell -Command "Enable-NetAdapterBinding -Name * -ComponentID ms_tcpip6"',
                    shell=True, check=False, creationflags=_NO_WINDOW,
                )
        except Exception:
            pass

    def restore_ipv6(self):
        """Restore IPv6 to the user's pre-launch state.

        If they had it on, re-enable it. If they already had it disabled
        before launching, leave it alone. Clears the captured IPv6 state.
        """
        state = self._load_state()
        was_enabled = state.get("original_ipv6_enabled", True)
        if was_enabled:
            self.enable_ipv6()
        if "original_ipv6_enabled" in state:
            state.pop("original_ipv6_enabled", None)
            self._save_state(state)

    def exempt(self):
        """Set DNS to 1.1.1.1, bypassing adLibre ad-blocking."""
        iface = self._get_active_interface()
        self._set_dns_static(iface, ["1.1.1.1"])
        self._flush_dns_cache()

    def undo_exempt(self):
        """Re-enable ad-blocking by pointing DNS back at the adLibre server."""
        iface = self._get_active_interface()
        self._set_dns_static(iface, [self.dns_server])
        self._flush_dns_cache()

    # ---------- crash recovery ----------

    def recover_from_crash(self) -> dict:
        """Detect and clean up state left behind by a crashed previous session.

        Scans all adapters for stale "DNS = our server" entries and reverts
        them. If our state file recorded an original DNS for the modified
        interface, restores to that; otherwise resets to DHCP. Restores IPv6
        to the captured pre-launch state if we recorded one.

        Returns:
            {
                "recovered": bool,           # did we change anything?
                "interfaces_reset": [...],   # interface names that had stale DNS
                "errors": [str, ...],        # exception messages, if any
            }
        """
        result = {"recovered": False, "interfaces_reset": [], "errors": []}
        state = self._load_state()

        # ---- DNS recovery ----
        recorded_iface = state.get("interface")
        original = state.get("original_dns")
        adapters_with_our_dns = []
        for iface in self._list_all_interfaces():
            try:
                current = self._read_current_dns(iface)
                if current["mode"] == "static" and self.dns_server in current["servers"]:
                    adapters_with_our_dns.append(iface)
            except Exception as e:
                result["errors"].append(f"reading DNS on {iface!r}: {e}")

        for iface in adapters_with_our_dns:
            try:
                if iface == recorded_iface and original \
                        and original.get("mode") == "static" \
                        and original.get("servers"):
                    self._set_dns_static(iface, original["servers"])
                else:
                    self._set_dns_dhcp(iface)
                result["interfaces_reset"].append(iface)
                result["recovered"] = True
            except Exception as e:
                result["errors"].append(f"resetting DNS on {iface!r}: {e}")

        if adapters_with_our_dns:
            try:
                self._flush_dns_cache()
            except Exception:
                pass

        # ---- IPv6 recovery ----
        # If state says we captured the pre-launch IPv6 status and the user
        # had it on, re-enable it. (If they had it off, leave it off.)
        if "original_ipv6_enabled" in state:
            if state["original_ipv6_enabled"]:
                try:
                    self.enable_ipv6()
                    result["recovered"] = True
                except Exception as e:
                    result["errors"].append(f"restoring IPv6: {e}")

        # Clear captured state — we either restored it or it's stale.
        if state:
            self._save_state({})

        return result

    # ---------- DNS cache ----------

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
