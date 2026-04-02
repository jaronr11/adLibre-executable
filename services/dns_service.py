import base64
import ctypes
import json
import platform
import subprocess
import time
from pathlib import Path


class DNSService:
    WINDOWS_BROWSER_DOH_POLICIES = {
        "chrome_system": {
            "browser": "Chrome",
            "process": "chrome",
            "path": r"HKLM:\SOFTWARE\Policies\Google\Chrome",
        },
        "chrome_user": {
            "browser": "Chrome",
            "process": "chrome",
            "path": r"HKCU:\SOFTWARE\Policies\Google\Chrome",
        },
        "edge_system": {
            "browser": "Edge",
            "process": "msedge",
            "path": r"HKLM:\SOFTWARE\Policies\Microsoft\Edge",
        },
        "edge_user": {
            "browser": "Edge",
            "process": "msedge",
            "path": r"HKCU:\SOFTWARE\Policies\Microsoft\Edge",
        },
    }

    def __init__(self, dns_server: str):
        self.dns_server = dns_server
        self._last_windows_aliases = []
        self._windows_ipv6_state = {}
        self._browser_doh_state = {}
        self._state_file = Path.home() / ".adlibre" / "network_state.json"

    def _is_admin_windows(self):
        """Check if the script is running with admin privileges on Windows."""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _encode_powershell(self, script: str) -> str:
        return base64.b64encode(script.encode("utf-16le")).decode("ascii")

    def _run_powershell(self, script: str, check: bool = True):
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                self._encode_powershell(script),
            ],
            capture_output=True,
            text=True,
            check=check,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _run_as_admin_windows(self, script: str):
        """Run a PowerShell script with elevation and wait for it to finish."""
        encoded_script = self._encode_powershell(script)
        launcher = (
            "Start-Process -FilePath 'powershell.exe' "
            "-Verb RunAs -Wait -WindowStyle Hidden "
            f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand','{encoded_script}')"
        )
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                launcher,
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _normalize_json_output(self, raw_output: str):
        cleaned = (raw_output or "").strip()
        if not cleaned:
            return []

        payload = json.loads(cleaned)
        if isinstance(payload, list):
            return payload
        return [payload]

    def _save_windows_state(self, aliases, ipv6_state, browser_doh_state=None):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "aliases": list(aliases or []),
            "ipv6_state": {str(alias): bool(enabled) for alias, enabled in (ipv6_state or {}).items()},
            "browser_doh_state": {
                str(browser): {
                    "exists": bool((details or {}).get("exists")),
                    "value": (details or {}).get("value"),
                }
                for browser, details in (browser_doh_state or {}).items()
            },
        }
        self._state_file.write_text(json.dumps(payload))

    def _load_windows_state(self):
        try:
            payload = json.loads(self._state_file.read_text())
        except Exception:
            return [], {}, {}

        aliases = [str(alias).strip() for alias in payload.get("aliases") or [] if str(alias).strip()]
        ipv6_state_raw = payload.get("ipv6_state") or {}
        ipv6_state = {
            str(alias).strip(): bool(enabled)
            for alias, enabled in ipv6_state_raw.items()
            if str(alias).strip()
        }
        browser_state_raw = payload.get("browser_doh_state") or {}
        browser_state = {
            str(browser).strip(): {
                "exists": bool((details or {}).get("exists")),
                "value": (details or {}).get("value"),
            }
            for browser, details in browser_state_raw.items()
            if str(browser).strip()
        }
        return aliases, ipv6_state, browser_state

    def _clear_windows_state(self):
        self._windows_ipv6_state = {}
        self._browser_doh_state = {}
        try:
            if self._state_file.exists():
                self._state_file.unlink()
        except OSError:
            pass

    def _browser_policy_entries(self):
        return [
            {"key": key, **value}
            for key, value in self.WINDOWS_BROWSER_DOH_POLICIES.items()
        ]

    def _get_windows_active_interface_aliases(self):
        script = """
$aliases = @(
    Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -and $_.NextHop -and $_.NextHop -ne '0.0.0.0' } |
        Sort-Object -Property RouteMetric, InterfaceMetric |
        Select-Object -ExpandProperty InterfaceAlias -Unique
)
if (-not $aliases -or $aliases.Count -eq 0) {
    $aliases = @(
        Get-NetAdapter -ErrorAction SilentlyContinue |
            Where-Object { $_.Status -eq 'Up' -and $_.Name } |
            Select-Object -ExpandProperty Name -Unique
    )
}
$aliases | ConvertTo-Json -Compress
"""
        result = self._run_powershell(script)
        aliases = [str(alias).strip() for alias in self._normalize_json_output(result.stdout)]
        return [alias for alias in aliases if alias]

    def _get_windows_ipv6_bindings(self, aliases):
        alias_json = json.dumps(list(aliases))
        script = f"""
$aliases = ConvertFrom-Json -InputObject '{alias_json}'
$results = @()
foreach ($alias in $aliases) {{
    $binding = Get-NetAdapterBinding -InterfaceAlias $alias -ComponentID 'ms_tcpip6' -ErrorAction SilentlyContinue
    $results += [pscustomobject]@{{
        alias = $alias
        enabled = [bool]($binding -and $binding.Enabled)
    }}
}}
$results | ConvertTo-Json -Compress
"""
        result = self._run_powershell(script)
        rows = self._normalize_json_output(result.stdout)
        return {
            str(row.get("alias", "")).strip(): bool(row.get("enabled"))
            for row in rows
            if str(row.get("alias", "")).strip()
        }

    def _get_windows_browser_doh_state(self):
        policies_json = json.dumps(self._browser_policy_entries())
        script = f"""
$policies = ConvertFrom-Json -InputObject '{policies_json}'
$results = @()
$policies | ForEach-Object {{
    $key = [string]$_.key
    $browser = [string]$_.browser
    $path = [string]$_.path
    $value = $null
    $exists = $false
    if (Test-Path $path) {{
        $item = Get-ItemProperty -Path $path -Name 'DnsOverHttpsMode' -ErrorAction SilentlyContinue
        if ($null -ne $item -and $null -ne $item.DnsOverHttpsMode) {{
            $value = [string]$item.DnsOverHttpsMode
            $exists = $true
        }}
    }}
    $results += [pscustomobject]@{{
        key = $key
        browser = $browser
        path = $path
        exists = $exists
        value = $value
    }}
}}
$results | ConvertTo-Json -Compress
"""
        result = self._run_powershell(script)
        rows = self._normalize_json_output(result.stdout)
        return {
            str(row.get("key", "")).strip(): {
                "browser": row.get("browser"),
                "path": row.get("path"),
                "exists": bool(row.get("exists")),
                "value": row.get("value"),
            }
            for row in rows
            if str(row.get("key", "")).strip()
        }

    def _get_running_windows_browsers(self):
        process_names = sorted(
            {
                str(entry.get("process", "")).strip()
                for entry in self.WINDOWS_BROWSER_DOH_POLICIES.values()
                if str(entry.get("process", "")).strip()
            }
        )
        if not process_names:
            return []

        process_json = json.dumps(process_names)
        script = f"""
$processNames = ConvertFrom-Json -InputObject '{process_json}'
$results = @()
foreach ($name in $processNames) {{
    if (Get-Process -Name $name -ErrorAction SilentlyContinue) {{
        $results += $name
    }}
}}
$results | ConvertTo-Json -Compress
"""
        result = self._run_powershell(script)
        running = {
            str(name).strip().lower()
            for name in self._normalize_json_output(result.stdout)
            if str(name).strip()
        }
        labels = []
        seen = set()
        for entry in self.WINDOWS_BROWSER_DOH_POLICIES.values():
            process = str(entry.get("process", "")).strip().lower()
            label = str(entry.get("browser", "")).strip()
            if process in running and label and label not in seen:
                seen.add(label)
                labels.append(label)
        return labels

    def _browser_restart_notice(self, action: str):
        if platform.system() != "Windows":
            return None

        browsers = self._get_running_windows_browsers()
        if not browsers:
            return None

        joined = "/".join(browsers)
        if action == "connect":
            return f"Restart {joined} to apply browser DNS protection."
        return f"Restart {joined} to restore browser DNS settings."

    @staticmethod
    def _merge_aliases(*alias_groups):
        merged = []
        seen = set()
        for alias_group in alias_groups:
            for alias in alias_group or []:
                normalized = str(alias).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged

    def _build_windows_dns_script(self, aliases, mode: str, ipv6_state=None):
        alias_json = json.dumps(list(aliases))
        dns_server_json = json.dumps(self.dns_server)
        ipv6_state_json = json.dumps(
            [
                {"alias": str(alias), "enabled": bool(enabled)}
                for alias, enabled in (ipv6_state or {}).items()
            ]
        )
        browser_doh_json = json.dumps(self._browser_doh_state or {})
        browser_entries_json = json.dumps(self._browser_policy_entries())

        if mode == "connect":
            return f"""
$ErrorActionPreference = 'Stop'
$aliases = ConvertFrom-Json -InputObject '{alias_json}'
$dnsServer = {dns_server_json}
$browserEntries = ConvertFrom-Json -InputObject '{browser_entries_json}'
foreach ($alias in $aliases) {{
    $applied = $false
    for ($attempt = 0; $attempt -lt 3 -and -not $applied; $attempt++) {{
        try {{
            Set-DnsClientServerAddress -InterfaceAlias $alias -ServerAddresses @($dnsServer) -ErrorAction Stop
            $null = & netsh interface ipv6 set dnsservers name="$alias" source=static address=none validate=no
            if ($LASTEXITCODE -ne 0) {{
                throw "Failed to clear IPv6 DNS servers for interface '$alias'."
            }}
            Disable-NetAdapterBinding -InterfaceAlias $alias -ComponentID 'ms_tcpip6' -Confirm:$false -ErrorAction Stop | Out-Null
            $applied = $true
        }} catch {{
            if ($attempt -ge 2) {{
                throw
            }}
            Start-Sleep -Milliseconds 750
        }}
    }}
}}
$browserEntries | ForEach-Object {{
    $path = [string]$_.path
    New-Item -Path $path -Force | Out-Null
    New-ItemProperty -Path $path -Name 'DnsOverHttpsMode' -PropertyType String -Value 'off' -Force | Out-Null
}}
Clear-DnsClientCache
"""

        return f"""
$ErrorActionPreference = 'Stop'
$aliases = ConvertFrom-Json -InputObject '{alias_json}'
$ipv6State = ConvertFrom-Json -InputObject '{ipv6_state_json}'
$browserDohState = ConvertFrom-Json -InputObject '{browser_doh_json}'
$browserEntries = ConvertFrom-Json -InputObject '{browser_entries_json}'
$ipv6ByAlias = @{{}}
foreach ($entry in $ipv6State) {{
    $ipv6ByAlias[$entry.alias] = [bool]$entry.enabled
}}
foreach ($alias in $aliases) {{
    $reset = $false
    for ($attempt = 0; $attempt -lt 3 -and -not $reset; $attempt++) {{
        try {{
            Set-DnsClientServerAddress -InterfaceAlias $alias -ResetServerAddresses -ErrorAction Stop
            $null = & netsh interface ip set dnsservers name="$alias" source=dhcp
            if ($LASTEXITCODE -ne 0) {{
                throw "Failed to restore IPv4 DNS to DHCP for interface '$alias'."
            }}
            $null = & netsh interface ipv6 set dnsservers name="$alias" source=dhcp
            if ($LASTEXITCODE -ne 0) {{
                throw "Failed to restore IPv6 DNS to DHCP for interface '$alias'."
            }}
            if ($ipv6ByAlias.ContainsKey($alias) -and $ipv6ByAlias[$alias]) {{
                Enable-NetAdapterBinding -InterfaceAlias $alias -ComponentID 'ms_tcpip6' -Confirm:$false -ErrorAction Stop | Out-Null
            }} else {{
                Disable-NetAdapterBinding -InterfaceAlias $alias -ComponentID 'ms_tcpip6' -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
            }}
            $reset = $true
        }} catch {{
            if ($attempt -ge 2) {{
                throw
            }}
            Start-Sleep -Milliseconds 750
        }}
    }}
}}
$browserEntries | ForEach-Object {{
    $key = [string]$_.key
    $path = [string]$_.path
    $state = $browserDohState.$key
    if ($null -ne $state -and [bool]$state.exists) {{
        New-Item -Path $path -Force | Out-Null
        New-ItemProperty -Path $path -Name 'DnsOverHttpsMode' -PropertyType String -Value ([string]$state.value) -Force | Out-Null
    }} else {{
        Remove-ItemProperty -Path $path -Name 'DnsOverHttpsMode' -ErrorAction SilentlyContinue
    }}
}}
Clear-DnsClientCache
"""

    def _get_windows_dns_servers(self, aliases):
        alias_json = json.dumps(list(aliases))
        script = f"""
$aliases = ConvertFrom-Json -InputObject '{alias_json}'
$results = @()
foreach ($alias in $aliases) {{
    $servers = @(
        Get-DnsClientServerAddress -InterfaceAlias $alias -ErrorAction SilentlyContinue |
            ForEach-Object {{ @($_.ServerAddresses) }} |
            Where-Object {{ $_ }}
    )
    $results += [pscustomobject]@{{
        alias = $alias
        servers = $servers
    }}
}}
$results | ConvertTo-Json -Compress -Depth 4
"""
        result = self._run_powershell(script)
        rows = self._normalize_json_output(result.stdout)
        normalized = {}
        for row in rows:
            alias = str(row.get("alias", "")).strip()
            servers = row.get("servers") or []
            if isinstance(servers, str):
                servers = [servers]
            normalized[alias] = [str(server).strip() for server in servers if str(server).strip()]
        return normalized

    def _wait_for_windows_dns_state(self, aliases, connected: bool, timeout_seconds: int = 20, expected_ipv6_state=None):
        deadline = time.time() + timeout_seconds
        last_seen = {}
        last_ipv6_state = {}

        while time.time() < deadline:
            try:
                last_seen = self._get_windows_dns_servers(aliases)
                last_ipv6_state = self._get_windows_ipv6_bindings(aliases)
            except Exception:
                time.sleep(1)
                continue

            if connected:
                dns_ready = aliases and all(self.dns_server in last_seen.get(alias, []) for alias in aliases)
                ipv6_ready = all(not last_ipv6_state.get(alias, False) for alias in aliases)
                if dns_ready and ipv6_ready:
                    return
            else:
                dns_ready = all(self.dns_server not in last_seen.get(alias, []) for alias in aliases)
                if expected_ipv6_state:
                    ipv6_ready = all(
                        bool(last_ipv6_state.get(alias, False)) == bool(expected_ipv6_state.get(alias, False))
                        for alias in aliases
                        if alias in expected_ipv6_state
                    )
                else:
                    ipv6_ready = True
                if dns_ready and ipv6_ready:
                    return

            time.sleep(1)

        if connected:
            raise RuntimeError(
                f"DNS server did not switch cleanly to {self.dns_server}. "
                f"Current DNS: {last_seen}; IPv6 bindings: {last_ipv6_state}"
            )
        raise RuntimeError(
            f"DNS server did not reset away from {self.dns_server}. "
            f"Current DNS: {last_seen}; IPv6 bindings: {last_ipv6_state}"
        )

    def _update_windows_dns(self, mode: str):
        aliases = self._get_windows_active_interface_aliases()
        if mode == "disconnect":
            saved_aliases, saved_ipv6_state, saved_browser_state = self._load_windows_state()
            aliases = self._merge_aliases(self._last_windows_aliases, saved_aliases, aliases)
            ipv6_state = saved_ipv6_state or self._windows_ipv6_state
            self._browser_doh_state = saved_browser_state or self._browser_doh_state
        else:
            ipv6_state = self._get_windows_ipv6_bindings(aliases)
            self._browser_doh_state = self._get_windows_browser_doh_state()

        if not aliases:
            raise RuntimeError("No active network adapter was found.")

        script = self._build_windows_dns_script(aliases, mode, ipv6_state=ipv6_state)
        if self._is_admin_windows():
            completed = self._run_powershell(script)
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "Failed to update DNS settings.")
        else:
            completed = self._run_as_admin_windows(script)
            if completed.returncode != 0:
                output = (completed.stderr or completed.stdout or "").strip()
                if "canceled by the user" in output.lower() or "cancelled by the user" in output.lower():
                    raise PermissionError("Administrator approval is required to change DNS settings.")
                raise RuntimeError(output or "Failed to update DNS settings.")

        wait_timeout = 30 if mode == "disconnect" else 20
        self._wait_for_windows_dns_state(
            aliases,
            connected=(mode == "connect"),
            timeout_seconds=wait_timeout,
            expected_ipv6_state=ipv6_state if mode == "disconnect" else None,
        )

        if mode == "connect":
            self._last_windows_aliases = list(aliases)
            self._windows_ipv6_state = dict(ipv6_state)
            self._save_windows_state(aliases, ipv6_state, self._browser_doh_state)
        else:
            self._last_windows_aliases = []
            self._clear_windows_state()

    def recover_windows_state_if_needed(self):
        if platform.system() != "Windows":
            return None

        saved_aliases, saved_ipv6_state, saved_browser_state = self._load_windows_state()
        if not saved_aliases and not saved_ipv6_state and not saved_browser_state:
            return None

        self._last_windows_aliases = list(saved_aliases)
        self._windows_ipv6_state = dict(saved_ipv6_state)
        self._browser_doh_state = dict(saved_browser_state)

        try:
            self._update_windows_dns("disconnect")
            return "Recovered browser and network settings from the previous session."
        except Exception as exc:
            return f"Could not recover previous network state automatically: {exc}"

    def connect(self):
        if platform.system() == "Darwin":
            subprocess.run(
                f'networksetup -setdnsservers Wi-Fi {self.dns_server}',
                shell=True,
                check=True,
            )
            return None

        self._update_windows_dns("connect")
        return self._browser_restart_notice("connect")

    def disconnect(self):
        if platform.system() == "Darwin":
            subprocess.run(
                "networksetup -setdnsservers Wi-Fi empty",
                shell=True,
                check=True,
            )
            return None

        self._update_windows_dns("disconnect")
        return self._browser_restart_notice("disconnect")
