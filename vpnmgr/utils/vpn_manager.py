"""
VPN Manager - Docker container interaction
"""
import base64
import docker
import subprocess
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from ..config import get_settings

settings = get_settings()


def parse_cert_expiry(text: str) -> Optional[str]:
    """
    Parse a certificate 'Not After' line into an ISO timestamp.

    Handles both formats:
      openssl : notAfter=Jan  1 00:00:00 2028 GMT
      certutil: Not After : Jan  1 00:00:00 2028 GMT
    """
    if not text:
        return None
    match = re.search(
        r"not ?after\s*[=:]\s*([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})",
        text, re.IGNORECASE
    )
    if not match:
        return None
    normalized = " ".join(match.group(1).split())
    try:
        dt = datetime.strptime(normalized, "%b %d %H:%M:%S %Y")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


class VPNManager:
    """Manage VPN Docker container"""
    
    def __init__(self, container_name: str = None):
        self.container_name = container_name or settings.vpn_container_name
        self.client = docker.from_env()
        self._container = None
    
    @property
    def container(self):
        """Get Docker container"""
        if self._container is None:
            try:
                self._container = self.client.containers.get(self.container_name)
            except docker.errors.NotFound:
                return None
        return self._container
    
    def is_container_running(self) -> bool:
        """Check if VPN container is running"""
        try:
            container = self.container
            if container is None:
                return False
            return container.status == "running"
        except Exception:
            return False
    
    def exec_command(self, command: List[str]) -> Tuple[int, str, str]:
        """
        Execute command in container
        Returns: (exit_code, stdout, stderr)
        """
        try:
            container = self.container
            if container is None:
                return 1, "", f"Container '{self.container_name}' not found"
            
            result = container.exec_run(command, demux=True)
            exit_code = result.exit_code
            
            stdout = result.output[0].decode('utf-8') if result.output[0] else ""
            stderr = result.output[1].decode('utf-8') if result.output[1] else ""
            
            return exit_code, stdout, stderr
        except Exception as e:
            return 1, "", str(e)
    
    # ========== User Management ==========
    
    def add_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Add a new VPN user"""
        # For hwdsl2/ipsec-vpn-server, VPN users are stored in /etc/ipsec.d/passwd
        # Format: username:encrypted_password:xauth-psk
        # We need to encrypt the password using openssl
        
        # Check if user already exists
        exit_code, stdout, _ = self.exec_command([
            "bash", "-c",
            f"grep -q '^{username}:' /etc/ipsec.d/passwd && echo 'exists' || echo 'not exists'"
        ])
        
        if exit_code == 0 and stdout.strip() == "exists":
            return False, f"User '{username}' already exists"
        
        # Encrypt password using openssl (MD5 hash for ipsec)
        exit_code, encrypted_pass, stderr = self.exec_command([
            "bash", "-c",
            f"openssl passwd -1 '{password}'"
        ])
        
        if exit_code != 0 or not encrypted_pass.strip():
            return False, f"Failed to encrypt password: {stderr}"
        
        encrypted_pass = encrypted_pass.strip()
        
        # Add user to /etc/ipsec.d/passwd
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            f"echo '{username}:{encrypted_pass}:xauth-psk' >> /etc/ipsec.d/passwd"
        ])
        
        if exit_code == 0:
            return True, f"User '{username}' added successfully"
        else:
            return False, stderr or "Failed to add user"
    
    def delete_user(self, username: str) -> Tuple[bool, str]:
        """Delete a VPN user"""
        # Remove user from /etc/ipsec.d/passwd and /etc/ppp/chap-secrets if exists
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            f"sed -i '/^{username}:/d' /etc/ipsec.d/passwd; [ -f /etc/ppp/chap-secrets ] && sed -i '/^{username}[ \\t]/d' /etc/ppp/chap-secrets || true"
        ])
        
        if exit_code == 0:
            return True, f"User '{username}' deleted successfully"
        else:
            return False, stderr or "Failed to delete user"
    
    def update_password(self, username: str, new_password: str) -> Tuple[bool, str]:
        """Update user password"""
        # Check if user exists
        exit_code, stdout, _ = self.exec_command([
            "bash", "-c",
            f"grep -q '^{username}:' /etc/ipsec.d/passwd && echo 'exists' || echo 'not exists'"
        ])
        
        if exit_code != 0 or stdout.strip() != "exists":
            return False, f"User '{username}' does not exist"
        
        # Encrypt new password
        exit_code, encrypted_pass, stderr = self.exec_command([
            "bash", "-c",
            f"openssl passwd -1 '{new_password}'"
        ])
        
        if exit_code != 0 or not encrypted_pass.strip():
            return False, f"Failed to encrypt password: {stderr}"
        
        encrypted_pass = encrypted_pass.strip()
        
        # Update password in /etc/ipsec.d/passwd
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            f"sed -i 's/^{username}:[^:]*:/'{username}':'{encrypted_pass}':/' /etc/ipsec.d/passwd"
        ])
        
        if exit_code == 0:
            return True, f"Password updated for user '{username}'"
        else:
            return False, stderr or "Failed to update password"
    
    def list_users(self) -> List[Dict]:
        """List all VPN users"""
        users = []
        
        # Method 1: Get users from /etc/passwd with UIDs >= 1000 (regular users)
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            "awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd"
        ])
        
        if exit_code == 0:
            for username in stdout.strip().split('\n'):
                username = username.strip()
                if username and username not in ['nobody']:
                    # Check if user is locked
                    exit_code2, stdout2, _ = self.exec_command([
                        "passwd", "-S", username
                    ])
                    is_active = "L" not in stdout2 if exit_code2 == 0 else True
                    
                    users.append({
                        "username": username,
                        "is_active": is_active
                    })
        
        # Method 2: Get users from /etc/ipsec.d/passwd (hwdsl2/ipsec-vpn-server format)
        # Format: username:password_hash:xauth-psk
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            "cat /etc/ipsec.d/passwd 2>/dev/null || true"
        ])
        
        if exit_code == 0 and stdout.strip():
            existing_usernames = {u["username"] for u in users}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                if line and ':' in line:
                    parts = line.split(':')
                    username = parts[0]
                    if username and username not in existing_usernames:
                        users.append({
                            "username": username,
                            "is_active": True
                        })
        
        return users
    
    # ========== Status & Monitoring ==========
    
    def get_status(self) -> Dict:
        """Get VPN server status"""
        status = {
            "container_running": self.is_container_running(),
            "active_connections": [],
            "server_info": {},
            "ipsec_status": "unknown"
        }
        
        if not status["container_running"]:
            return status
        
        # Get IPsec status
        exit_code, stdout, _ = self.exec_command(["ipsec", "status"])
        if exit_code == 0:
            status["ipsec_status"] = stdout
            # Also try to parse connections from ipsec status
            status["active_connections"] = self._parse_ipsec_status(stdout)
        
        # Get traffic status (active connections) - this provides more details
        exit_code, stdout, _ = self.exec_command([
            "ipsec", "whack", "--trafficstatus"
        ])
        if exit_code == 0 and stdout.strip():
            traffic_conns = self._parse_traffic_status(stdout)
            # Merge with existing connections if any
            if traffic_conns:
                status["active_connections"] = traffic_conns
        
        return status
    
    def _parse_ipsec_status(self, output: str) -> List[Dict]:
        """Parse ipsec status output for active connections"""
        connections = []
        if not output:
            return connections
        
        # Look for lines with "ESTABLISHED" or connected clients
        # Pattern: "tunnel-name"[n] IP, ... 
        # Example: "l2tp-psk"[2]: ESTABLISHED... 192.168.1.100...
        
        for line in output.split('\n'):
            line = line.strip()
            # Match established connections with IP
            match = re.search(r'"([^"]+)"\[(\d+)\]:\s+ESTABLISHED.*?([\d.]+:\d+|[\d.]+)', line)
            if match:
                client_ip = match.group(3).split(':')[0]
                # Check if this connection is already recorded
                existing = [c for c in connections if c.get("client_ip") == client_ip]
                if not existing:
                    connections.append({
                        "tunnel": match.group(1),
                        "id": match.group(2),
                        "client_ip": client_ip,
                        "username": "unknown",
                    })
        
        return connections
    
    def _parse_traffic_status(self, output: str) -> List[Dict]:
        """Parse ipsec whack --trafficstatus output"""
        connections = []
        if not output or not output.strip():
            return connections
        
        # Pattern for IKEv2 traffic status:
        # #196: "ikev2-cp"[92] 203.0.113.10, type=ESP, ... id='CN=client1, O=IKEv2 VPN', lease=192.168.43.11/32
        pattern = r'#\d+:\s*"([^"]+)"\[(\d+)\]\s+([\d.]+),.*?id=[\'"](?:CN=)?([^,\'"]+)'
        # Pattern for lease IP - support both "lease=x.x.x.x" and "lease=x.x.x.x/32"
        lease_pattern = r'lease=([\d.]+)(?:/\d+)?'
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            match = re.search(pattern, line)
            if match:
                # Extract lease IP if present
                lease_match = re.search(lease_pattern, line)
                assigned_ip = lease_match.group(1) if lease_match else '-'
                
                connections.append({
                    "tunnel": match.group(1),
                    "id": match.group(2),
                    "client_ip": match.group(3),
                    "username": match.group(4),
                    "assigned_ip": assigned_ip,
                })
        
        print(f"[VPN_PARSER] Parsed {len(connections)} connections from trafficstatus")
        for c in connections:
            print(f"[VPN_PARSER]   id={c['id']} username={c['username']} client_ip={c['client_ip']} assigned_ip={c['assigned_ip']}")
        return connections
    
    def get_logs(self, lines: int = 100) -> str:
        """Get VPN connection logs (API-based, no sensitive info)"""
        try:
            # Get current connections as formatted logs
            status = self.get_status()
            
            log_lines = []
            log_lines.append("=" * 60)
            log_lines.append(f"VPN Connection Status - {self._get_timestamp()}")
            log_lines.append("=" * 60)
            log_lines.append("")
            
            # Container status
            if status['container_running']:
                log_lines.append("[INFO] VPN Container: Running")
            else:
                log_lines.append("[WARN] VPN Container: Stopped")
            log_lines.append("")
            
            # Active connections
            if status['active_connections']:
                log_lines.append(f"[INFO] Active Connections: {len(status['active_connections'])}")
                log_lines.append("-" * 60)
                for conn in status['active_connections']:
                    log_lines.append(f"[CONN] Tunnel: {conn['tunnel']}")
                    log_lines.append(f"       Client: {conn['username']}")
                    log_lines.append(f"       IP: {conn['client_ip']}")
                    log_lines.append(f"       Session ID: {conn['id']}")
                    log_lines.append("")
            else:
                log_lines.append("[INFO] Active Connections: 0")
                log_lines.append("")
            
            # Get recent ipsec status summary
            exit_code, stdout, _ = self.exec_command(["ipsec", "status"])
            if exit_code == 0:
                log_lines.append("-" * 60)
                log_lines.append("[INFO] Tunnel Status Summary:")
                # Count established connections
                established_count = stdout.count('ESTABLISHED')
                if established_count > 0:
                    log_lines.append(f"       Established SAs: {established_count}")
                # Extract routing info
                for line in stdout.split('\n'):
                    if 'routed' in line.lower() or 'established' in line.lower():
                        log_lines.append(f"       {line.strip()}")
            
            log_lines.append("")
            log_lines.append("=" * 60)
            log_lines.append("End of Status Report")
            log_lines.append("=" * 60)
            
            return '\n'.join(log_lines)
        except Exception as e:
            return f"Error getting logs: {str(e)}"
    
    def sync_connection_logs(self, db_session) -> None:
        """Sync current connections to database (to be called periodically)"""
        try:
            from datetime import datetime, timezone, timedelta
            from ..models.connection_log import ConnectionLog
            
            status = self.get_status()
            current_conns = status.get('active_connections', [])
            
            # Get current active session IDs
            current_session_ids = {conn['id'] for conn in current_conns}
            
            # Get all currently connected sessions from database
            db_connected_sessions = db_session.query(ConnectionLog).filter(
                ConnectionLog.status == 'connected'
            ).all()
            
            # Mark disconnected sessions
            now = datetime.now(timezone(timedelta(hours=8)))
            for db_conn in db_connected_sessions:
                if db_conn.session_id not in current_session_ids:
                    # This session is no longer active, mark as disconnected
                    db_conn.status = 'disconnected'
                    db_conn.disconnected_at = now
            
            # Add new connections
            for conn in current_conns:
                # Check if this session already exists and is connected
                existing = db_session.query(ConnectionLog).filter(
                    ConnectionLog.session_id == conn['id'],
                    ConnectionLog.status == 'connected'
                ).first()
                
                if not existing:
                    # Create new connection log
                    new_log = ConnectionLog(
                        session_id=conn['id'],
                        client_name=conn['username'],
                        tunnel_type=conn['tunnel'],
                        client_ip=conn['client_ip'],
                        assigned_ip=conn.get('assigned_ip', '-'),
                        status='connected',
                        connected_at=now,
                        raw_log=f"Tunnel: {conn['tunnel']}, Client: {conn['username']}, IP: {conn['client_ip']}"
                    )
                    db_session.add(new_log)
            
            db_session.commit()
        except Exception as e:
            print(f"Error syncing connection logs: {e}")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp (GMT+8)"""
        from datetime import datetime, timezone, timedelta
        gmt8 = timezone(timedelta(hours=8))
        return datetime.now(gmt8).strftime('%Y-%m-%d %H:%M:%S')
    
    def disconnect_connection(self, session_id: str) -> Tuple[bool, str]:
        """
        Disconnect a specific VPN connection by session ID
        Uses ipsec whack --crash to terminate the connection
        """
        try:
            # Try to find the connection and terminate it
            # ipsec whack --crash <id> will terminate the connection with that ID
            exit_code, stdout, stderr = self.exec_command([
                "ipsec", "whack", "--crash", session_id
            ])
            
            if exit_code == 0:
                return True, f"Connection {session_id} terminated successfully"
            else:
                # Try alternative method - delete the connection
                exit_code2, stdout2, stderr2 = self.exec_command([
                    "ipsec", "whack", "--delete", "--name", f"ikev2-cp[{session_id}]"
                ])
                if exit_code2 == 0:
                    return True, f"Connection {session_id} deleted"
                return False, f"Failed to disconnect: {stderr or stderr2}"
        except Exception as e:
            return False, f"Error disconnecting: {str(e)}"
    
    # ========== IKEv2 Certificate Management ==========
    
    def list_ikev2_certs(self) -> List[Dict]:
        """List IKEv2 certificates using ikev2.sh --listclients"""
        certs = []
        
        # Use ikev2.sh --listclients to get certificate list
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            "/opt/src/ikev2.sh --listclients 2>/dev/null || true"
        ])
        
        if exit_code == 0 and stdout.strip():
            # Parse output like:
            # Client Name       Certificate Status
            # ------------      -------------------
            # client1           valid
            # client2           valid
            lines = stdout.strip().split('\n')
            in_table = False
            
            for line in lines:
                line = line.strip()
                # Skip empty lines
                if not line:
                    continue
                # Start of table (header line)
                if 'Client Name' in line and 'Certificate Status' in line:
                    in_table = True
                    continue
                # Skip separator line
                if '---' in line and in_table:
                    continue
                # End of table (Total line)
                if line.startswith('Total:') and in_table:
                    break
                # Parse client line - must have "valid" or "revoked" status
                if in_table:
                    parts = line.split()
                    if len(parts) >= 2:
                        client_name = parts[0]
                        cert_status = parts[-1]  # Last part is status
                        # Only include if status is valid or revoked
                        if cert_status in ('valid', 'revoked'):
                            certs.append({
                                "name": client_name,
                                "status": cert_status,
                                "p12_path": f"/etc/ipsec.d/{client_name}.p12",
                                "mobileconfig_path": f"/etc/ipsec.d/{client_name}.mobileconfig",
                                "sswan_path": f"/etc/ipsec.d/{client_name}.sswan",
                            })
        
        # Fallback: if ikev2.sh didn't work, try listing .p12 files
        if not certs:
            exit_code, stdout, _ = self.exec_command([
                "bash", "-c",
                "ls /etc/ipsec.d/*.p12 2>/dev/null || true"
            ])
            
            if exit_code == 0 and stdout.strip():
                for line in stdout.strip().split('\n'):
                    if line.endswith('.p12'):
                        cert_name = line.split('/')[-1].replace('.p12', '')
                        certs.append({
                            "name": cert_name,
                            "status": "valid",
                            "p12_path": line.strip(),
                            "mobileconfig_path": f"/etc/ipsec.d/{cert_name}.mobileconfig",
                            "sswan_path": f"/etc/ipsec.d/{cert_name}.sswan",
                        })
        
        # Attach certificate validity so the UI can show the remaining days
        expiries = self._collect_cert_expiry([c["name"] for c in certs])
        for cert in certs:
            cert["expires_at"] = expiries.get(cert["name"])

        return certs

    def get_cert_expiry(self, client_name: str) -> Optional[str]:
        """Return the ISO expiry timestamp for a single certificate."""
        return self._collect_cert_expiry([client_name]).get(client_name)

    def _collect_cert_expiry(self, names: List[str]) -> Dict[str, Optional[str]]:
        """Return {cert_name: iso_expiry} for the given certificates (single exec)."""
        safe = [n for n in names if n and re.fullmatch(r"[A-Za-z0-9._@-]+", n)]
        if not safe:
            return {}
        quoted = " ".join(f"'{n}'" for n in safe)
        script = (
            f"for n in {quoted}; do "
            'echo "===CERT:$n==="; '
            'certutil -L -d sql:/etc/ipsec.d -n "$n" 2>/dev/null | grep -i "not after" '
            '|| certutil -L -d /etc/ipsec.d -n "$n" 2>/dev/null | grep -i "not after" '
            '|| echo "EXPIRY_UNKNOWN"; '
            "done"
        )
        code, out, _ = self.exec_command(["bash", "-c", script])
        if code != 0 or not out:
            return {}

        result: Dict[str, Optional[str]] = {}
        current = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("===CERT:") and line.endswith("==="):
                current = line[len("===CERT:"):-3]
                result.setdefault(current, None)
            elif current and line and line != "EXPIRY_UNKNOWN":
                parsed = parse_cert_expiry(line)
                if parsed:
                    result[current] = parsed
        return result

    # The import password is stored globally by ikev2.sh in this file, so any
    # per-certificate decision has to be applied by (temporarily) rewriting it.
    CONFIG_FILE = "/etc/ipsec.d/.vpnconfig"
    PASSWORD_RE = re.compile(r"^[A-Za-z0-9._@#%^*+=\-]{6,128}$")

    def validate_config_password(self, password: str) -> Tuple[bool, str]:
        """Reject passwords that would break shell quoting inside the container."""
        if not password:
            return True, ""
        if not self.PASSWORD_RE.match(password):
            return False, "密码只能包含字母、数字以及 . _ @ # % ^ * + = - ，长度 6-128 位"
        return True, ""

    def get_config_password(self) -> str:
        """Read the persisted client-config import password from the container."""
        code, out, _ = self.exec_command([
            "bash", "-c",
            f"grep -s '^IKEV2_CONFIG_PASSWORD=.' {self.CONFIG_FILE} 2>/dev/null | tail -n 1 || true"
        ])
        if code != 0 or not out.strip():
            return ""
        return out.strip().split("=", 1)[-1].strip().strip("'")

    def _write_config_password(self, password: str) -> bool:
        """Set (or clear, when empty) IKEV2_CONFIG_PASSWORD in the config file."""
        code, out, _ = self.exec_command([
            "bash", "-c", f"cat {self.CONFIG_FILE} 2>/dev/null || true"
        ])
        content = out if code == 0 else ""
        kept = [ln for ln in content.splitlines() if not ln.startswith("IKEV2_CONFIG_PASSWORD=")]
        if password:
            kept.append(f"IKEV2_CONFIG_PASSWORD='{password}'")
        new_content = "\n".join(kept) + ("\n" if kept else "")
        b64 = base64.b64encode(new_content.encode()).decode()
        code, _, err = self.exec_command([
            "bash", "-c",
            f"printf '%s' '{b64}' | base64 -d > {self.CONFIG_FILE} && chmod 600 {self.CONFIG_FILE}"
        ])
        if code != 0:
            print(f"[CERT] Failed to update {self.CONFIG_FILE}: {err}")
        return code == 0

    @staticmethod
    def _parse_import_password(stdout: str) -> Optional[str]:
        """Extract the password that ikev2.sh prints after protecting a config."""
        lines = (stdout or "").splitlines()
        for i, line in enumerate(lines):
            if "Password for client config files" in line and i + 1 < len(lines):
                candidate = lines[i + 1].strip()
                if candidate:
                    return candidate
        return None

    def generate_ikev2_cert(
        self,
        client_name: str,
        protect_config: Optional[bool] = None,
        config_password: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Generate an IKEv2 certificate for a client.

        protect_config / config_password default to the global settings.
        Returns: (success, message, p12_content_base64, import_password)
        """
        if protect_config is None:
            protect_config = settings.protect_client_config
        if config_password is None:
            config_password = settings.client_config_password or ""

        ok, err = self.validate_config_password(config_password)
        if not ok:
            return False, err, None, None

        # ikev2.sh keeps ONE import password for all clients. To issue an
        # unprotected certificate we must hide any persisted password while the
        # command runs, then put it back for the certificates that rely on it.
        original_password = self.get_config_password()
        restore_after = None
        env_prefix = ""

        if protect_config:
            if config_password:
                self._write_config_password(config_password)
            env_prefix = "VPN_PROTECT_CONFIG=yes "
        elif original_password:
            self._write_config_password("")
            restore_after = original_password

        try:
            exit_code, stdout, stderr = self.exec_command([
                "bash", "-c",
                f"{env_prefix}echo '' | /opt/src/ikev2.sh --addclient '{client_name}'"
            ])
        finally:
            if restore_after is not None:
                self._write_config_password(restore_after)

        if exit_code != 0:
            return False, stderr or "Failed to generate certificate", None, None

        import_password = None
        if protect_config:
            import_password = self._parse_import_password(stdout) or self.get_config_password() or None

        # Export the .p12 file
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            f"cat /etc/ipsec.d/{client_name}.p12 | base64"
        ])

        if exit_code == 0:
            return True, "Certificate generated successfully", stdout.strip(), import_password
        return True, "Certificate generated but failed to read file", None, import_password
    
    def revoke_ikev2_cert(self, client_name: str) -> Tuple[bool, str]:
        """Revoke IKEv2 certificate"""
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            f"echo 'y' | /opt/src/ikev2.sh --revokeclient '{client_name}'"
        ])
        
        # Clean up exported cert files in container
        self.exec_command([
            "bash", "-c",
            f"rm -f /etc/ipsec.d/{client_name}.p12 /etc/ipsec.d/{client_name}.mobileconfig /etc/ipsec.d/{client_name}.sswan"
        ])
        
        if exit_code == 0:
            return True, f"Certificate for '{client_name}' revoked"
        else:
            return False, stderr or "Failed to revoke certificate"
    
    def export_ikev2_cert(
        self,
        client_name: str,
        format_type: str = "p12",
        protect: Optional[bool] = None,
        config_password: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Export IKEv2 certificate in specified format
        format_type: 'p12', 'mobileconfig', or 'sswan'

        ikev2.sh applies the import password at export time, so the per-certificate
        protection flag has to be applied here as well.
        Returns: (success, message, file_content_base64, filename)
        """
        if protect is None:
            protect = settings.protect_client_config

        original_password = self.get_config_password()
        restore_after = None
        env_prefix = ""

        if protect:
            password = config_password or original_password or ""
            if password and password != original_password:
                self._write_config_password(password)
                restore_after = original_password
            env_prefix = "VPN_PROTECT_CONFIG=yes "
        elif original_password:
            self._write_config_password("")
            restore_after = original_password

        try:
            exit_code, stdout, stderr = self.exec_command([
                "bash", "-c",
                f"{env_prefix}echo '' | /opt/src/ikev2.sh --exportclient '{client_name}'"
            ])
        finally:
            if restore_after is not None:
                self._write_config_password(restore_after)

        if exit_code != 0:
            return False, stderr or f"Failed to export certificate for '{client_name}'", None, None
        
        # Map format to file extension
        format_map = {
            "p12": ("p12", f"{client_name}.p12"),
            "mobileconfig": ("mobileconfig", f"{client_name}.mobileconfig"),
            "sswan": ("sswan", f"{client_name}.sswan"),
        }
        
        if format_type not in format_map:
            return False, f"Invalid format: {format_type}. Supported: p12, mobileconfig, sswan", None, None
        
        ext, filename = format_map[format_type]
        file_path = f"/etc/ipsec.d/{filename}"
        
        # Read and encode the file
        exit_code, stdout, stderr = self.exec_command([
            "bash", "-c",
            f"cat '{file_path}' | base64"
        ])
        
        if exit_code == 0:
            return True, f"Certificate exported successfully", stdout.strip(), filename
        else:
            return False, f"Failed to read {ext} file: {stderr}", None, None


# Global VPN manager instance
vpn_manager = VPNManager()
