"""
Captive Portal Firewall Enforcement Manager
Controls iptables inside ipsec-vpn-server container to enforce access control.
"""
import subprocess
import logging
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CONTAINER_NAME = settings.vpn_container_name or "ipsec-vpn-server"
CHAIN_NAME = "CAPTIVE_AUTH"
VPN_SUBNET = "192.168.43.0/24"
HOST_IP = "192.168.1.165"


def run_container_iptables(args: list) -> tuple:
    """Run iptables command inside the VPN container"""
    cmd = ["docker", "exec", CONTAINER_NAME, "iptables"] + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        logger.error(f"[FIREWALL] Error running iptables: {e}")
        return False, "", str(e)


def is_firewall_enforced() -> bool:
    """Check if CAPTIVE_AUTH is currently hooked in FORWARD chain"""
    ok, out, _ = run_container_iptables(["-L", "FORWARD", "-n", "-v"])
    return ok and CHAIN_NAME in out


def init_captive_firewall():
    """Initialize the CAPTIVE_AUTH chain and hook it into FORWARD"""
    # 0. Ensure VPN clients -> Host IP preserves real client IP (must be position 1 before MASQUERADE)
    run_container_iptables(["-t", "nat", "-D", "POSTROUTING", "-s", VPN_SUBNET, "-d", f"{HOST_IP}/32", "-j", "RETURN"])
    run_container_iptables(["-t", "nat", "-I", "POSTROUTING", "1", "-s", VPN_SUBNET, "-d", f"{HOST_IP}/32", "-j", "RETURN"])

    # 1. Create chain if not exists
    run_container_iptables(["-N", CHAIN_NAME])
    
    # 2. Flush chain
    run_container_iptables(["-F", CHAIN_NAME])
    
    # 3. Base allowed rules in chain for unauthenticated clients:
    # Allow DNS (UDP/TCP 53) to any resolver (e.g. AdGuard or upstream)
    run_container_iptables(["-A", CHAIN_NAME, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
    run_container_iptables(["-A", CHAIN_NAME, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])
    
    # Allow HTTP / Portal traffic to host (192.168.1.165:80 NPM, :8080 vpnmgr direct)
    run_container_iptables(["-A", CHAIN_NAME, "-p", "tcp", "-d", HOST_IP, "--dport", "80", "-j", "ACCEPT"])
    run_container_iptables(["-A", CHAIN_NAME, "-p", "tcp", "-d", HOST_IP, "--dport", "8080", "-j", "ACCEPT"])
    
    # Allow ICMP ping to portal host for diagnostic
    run_container_iptables(["-A", CHAIN_NAME, "-p", "icmp", "-d", HOST_IP, "-j", "ACCEPT"])
    
    # REJECT TCP connections (HTTPS etc.) with tcp-reset so browsers fail fast
    # instead of hanging on timeout for 30+ seconds with DROP
    run_container_iptables(["-A", CHAIN_NAME, "-p", "tcp", "-j", "REJECT", "--reject-with", "tcp-reset"])
    # DROP everything else (UDP non-DNS, etc.) as final catch-all
    run_container_iptables(["-A", CHAIN_NAME, "-j", "DROP"])
    
    # 4. Remove all existing blanket ACCEPT and existing CAPTIVE_AUTH jumps from FORWARD
    while True:
        ok, _, _ = run_container_iptables(["-D", "FORWARD", "-s", VPN_SUBNET, "-o", "eth0", "-j", "ACCEPT"])
        if not ok:
            break
    while True:
        ok, _, _ = run_container_iptables(["-D", "FORWARD", "-s", VPN_SUBNET, "-o", "eth0", "-j", CHAIN_NAME])
        if not ok:
            break

    # 5. Insert jump to CAPTIVE_AUTH before the final DROP rule in FORWARD
    ok, out, _ = run_container_iptables(["-L", "FORWARD", "-n", "--line-numbers"])
    drop_idx = None
    if ok:
        for line in out.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "DROP" and parts[0].isdigit():
                if "INVALID" not in line and "ctstate" not in line:
                    drop_idx = int(parts[0])
                    break
    
    if drop_idx:
        run_container_iptables(["-I", "FORWARD", str(drop_idx), "-s", VPN_SUBNET, "-o", "eth0", "-j", CHAIN_NAME])
    else:
        run_container_iptables(["-A", "FORWARD", "-s", VPN_SUBNET, "-o", "eth0", "-j", CHAIN_NAME])
        
    logger.info("[FIREWALL] Captive enforcement initialized in VPN container")


def disable_captive_firewall():
    """Restore default open forwarding without captive enforcement"""
    while True:
        ok, _, _ = run_container_iptables(["-D", "FORWARD", "-s", VPN_SUBNET, "-o", "eth0", "-j", CHAIN_NAME])
        if not ok:
            break
    while True:
        ok, _, _ = run_container_iptables(["-D", "FORWARD", "-s", VPN_SUBNET, "-o", "eth0", "-j", "ACCEPT"])
        if not ok:
            break
            
    ok, out, _ = run_container_iptables(["-L", "FORWARD", "-n", "--line-numbers"])
    drop_idx = None
    if ok:
        for line in out.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "DROP" and parts[0].isdigit():
                if "INVALID" not in line and "ctstate" not in line:
                    drop_idx = int(parts[0])
                    break
    if drop_idx:
        run_container_iptables(["-I", "FORWARD", str(drop_idx), "-s", VPN_SUBNET, "-o", "eth0", "-j", "ACCEPT"])
    else:
        run_container_iptables(["-A", "FORWARD", "-s", VPN_SUBNET, "-o", "eth0", "-j", "ACCEPT"])
        
    run_container_iptables(["-F", CHAIN_NAME])
    logger.info("[FIREWALL] Captive enforcement disabled (open forwarding restored)")


def authorize_ip(client_ip: str) -> bool:
    """Add client IP to top of CAPTIVE_AUTH chain to grant full internet access"""
    if not client_ip or client_ip == "unknown":
        return False
    # Avoid duplicate rules
    while True:
        ok, _, _ = run_container_iptables(["-D", CHAIN_NAME, "-s", client_ip, "-j", "ACCEPT"])
        if not ok:
            break
    success, _, err = run_container_iptables(["-I", CHAIN_NAME, "1", "-s", client_ip, "-j", "ACCEPT"])
    if success:
        logger.info(f"[FIREWALL] Authorized client IP {client_ip} in firewall")
    else:
        logger.error(f"[FIREWALL] Failed to authorize {client_ip}: {err}")
    return success


def deauthorize_ip(client_ip: str) -> bool:
    """Remove client IP from CAPTIVE_AUTH chain"""
    if not client_ip or client_ip == "unknown":
        return False
    while True:
        ok, _, _ = run_container_iptables(["-D", CHAIN_NAME, "-s", client_ip, "-j", "ACCEPT"])
        if not ok:
            break
    logger.info(f"[FIREWALL] Deauthorized client IP {client_ip} in firewall")
    return True


def reset_firewall():
    """Clear all authorized IPs and re-initialize base firewall rules"""
    init_captive_firewall()
