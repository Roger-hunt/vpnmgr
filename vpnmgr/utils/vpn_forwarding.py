"""
VPN client forwarding management.

Ensures VPN clients (the IKEv2 subnet) can reach the internet, and purges the
legacy captive-portal enforcement rules that earlier versions of this project
installed inside the VPN container.

Why there is no captive portal here
-----------------------------------
A captive portal cannot work over an IPsec/IKEv2 tunnel. The OS connectivity
probe (Android NetworkMonitor, iOS Captive Network Assistant) runs on the
physical network transport and explicitly ignores VPN transports, so the login
sheet never appears no matter what is blocked inside the tunnel.

More fundamentally, tunnel access is already fully gated by the client
certificate: a client cannot obtain a VPN IP without passing Libreswan's
certificate verification. Re-checking account bindings at the network layer
would only re-derive an identity that the tunnel already proved.

Host-side networking (routes, NAT exclusions, INPUT rules) is set up by
``start.py::setup_vpn_network()``.
"""
import subprocess
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CONTAINER_NAME = settings.vpn_container_name or "ipsec-vpn-server"
VPN_SUBNET = settings.vpn_subnet

CHAIN = "FORWARD"
LEGACY_CHAIN = "CAPTIVE_AUTH"


def _iptables(args: list) -> tuple:
    """Run an iptables command inside the VPN container."""
    cmd = ["docker", "exec", CONTAINER_NAME, "iptables"] + args
    try:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=5
        )
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        logger.error(f"[FORWARD] iptables error: {e}")
        return False, "", str(e)


def _remove_all(rule: list) -> None:
    """Delete every matching rule (iptables -D removes only one per call)."""
    while _iptables(["-D"] + rule)[0]:
        pass


def _find_drop_index() -> int:
    """Return the line number of the generic DROP rule in FORWARD, or 0."""
    ok, out, _ = _iptables(["-L", CHAIN, "-n", "--line-numbers"])
    if not ok:
        return 0
    for line in out.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "DROP" and parts[0].isdigit():
            if "INVALID" not in line and "ctstate" not in line:
                return int(parts[0])
    return 0


def ensure_open_forwarding() -> bool:
    """
    Let VPN clients reach the internet and remove any leftover captive rules.

    Idempotent, safe to call on every startup. This is what keeps existing
    deployments from staying locked out after the captive portal was removed.
    """
    if not VPN_SUBNET:
        logger.warning("[FORWARD] vpn_subnet not configured, skipping")
        return False

    # NOTE: do NOT include CHAIN in `rule`. `rule` is passed to _iptables, which
    # prepends `iptables` and is later given the chain name separately (e.g.
    # `-D FORWARD <rule>` / `-I FORWARD <idx> <rule>`). Putting CHAIN inside the
    # rule produced `iptables -I FORWARD 7 FORWARD -s ...` -> "Bad argument
    # 'FORWARD'", so the egress ACCEPT was never inserted and VPN clients (IKEv2,
    # which uses no ppp interface) had their traffic dropped by the chain's tail
    # DROP rule. This is what kept them from reaching the internet/LAN.
    rule = ["-s", VPN_SUBNET, "-o", "eth0"]

    # 1. Drop legacy captive jumps and any stale duplicate ACCEPT rules
    _remove_all(rule + ["-j", LEGACY_CHAIN])
    _remove_all(rule + ["-j", "ACCEPT"])

    # 2. Insert a single ACCEPT ahead of the generic DROP rule. This is
    # source-interface-agnostic: IKEv2 clients arrive decrypted with a
    # 192.168.43.0/24 source and egress eth0, with no ppp interface involved.
    drop_idx = _find_drop_index()
    if drop_idx:
        ok, _, err = _iptables(["-I", CHAIN, str(drop_idx)] + rule + ["-j", "ACCEPT"])
    else:
        ok, _, err = _iptables(["-A"] + rule + ["-j", "ACCEPT"])

    if not ok:
        logger.error(f"[FORWARD] failed to allow VPN egress: {err}")
        return False

    # 3. Remove the legacy captive chain entirely
    _iptables(["-F", LEGACY_CHAIN])
    _iptables(["-X", LEGACY_CHAIN])

    logger.info(f"[FORWARD] VPN subnet {VPN_SUBNET} allowed to reach the internet")
    return True
