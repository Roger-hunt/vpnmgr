"""
VPN Manager - FastAPI Application
"""
import os
import time
import ipaddress
import secrets
import hashlib
import base64
from urllib.parse import urlencode
import httpx
try:
    from jose import jwt
except ImportError:
    jwt = None
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .schemas import *
from .models.database import init_db, get_db, AsyncSessionLocal
from .models.vpn_user import VPNUser
from .models.connection_log import ConnectionLog as ConnectionLogModel
from .models.ikev2_cert import IKEv2Certificate
from .models.connection_log import ConnectionLog
from .models.user_cert_binding import UserCertBinding, CertUsageLog
from .models.system_user import SystemUser, UserActivityLog
from .utils.vpn_manager import vpn_manager
from .utils.auth import require_auth, create_access_token, verify_password, get_current_user

settings = get_settings()

# Track active connections for history
_active_sessions = {}

async def sync_connection_history():
    """Background task to sync connection history with audit logging"""
    await asyncio.sleep(3)  # Wait for app to start
    print("[SYNC] Connection history sync started")
    
    # Load existing active connections from database on startup
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ConnectionLog).where(ConnectionLog.status == 'connected')
            )
            db_active_conns = result.scalars().all()
            for conn in db_active_conns:
                _active_sessions[conn.session_id] = {
                    'id': conn.session_id,
                    'username': conn.client_name,
                    'tunnel': conn.tunnel_type,
                    'client_ip': conn.client_ip,
                    'assigned_ip': conn.assigned_ip or '-'
                }
            if db_active_conns:
                print(f"[SYNC] Loaded {len(db_active_conns)} active connections from database")
    except Exception as e:
        print(f"[SYNC ERROR] Failed to load existing connections: {e}")
    
    while True:
        try:
            # Get current connections
            status = vpn_manager.get_status()
            current_conns = {conn['id']: conn for conn in status.get('active_connections', [])}
            
            if current_conns:
                print(f"[SYNC] Found {len(current_conns)} active connections")
            
            async with AsyncSessionLocal() as db:
                # === Connection Limit Enforcement ===
                # Note: Single connection per cert is now enforced when new connections are detected
                # This section handles any edge cases (e.g., manual connections, race conditions)
                cert_connections = {}
                for session_id, conn in current_conns.items():
                    cert_name = conn.get('username', 'Unknown')
                    if cert_name not in cert_connections:
                        cert_connections[cert_name] = []
                    cert_connections[cert_name].append((session_id, conn))
                
                # Log warning if any cert still has multiple connections
                for cert_name, conns in cert_connections.items():
                    if len(conns) > 1:
                        print(f"[SYNC WARNING] Certificate '{cert_name}' still has {len(conns)} connections, cleaning up...")
                        # Sort by session_id (numeric) in descending order, keep newest
                        conns_sorted = sorted(conns, key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=True)
                        
                        # Disconnect older connections
                        for session_id, conn in conns_sorted[1:]:
                            print(f"[SYNC] Disconnecting older connection: {session_id} - {cert_name}")
                            success, message = vpn_manager.disconnect_connection(session_id)
                            if success:
                                print(f"[SYNC] Successfully disconnected: {session_id}")
                            else:
                                print(f"[SYNC ERROR] Failed to disconnect {session_id}: {message}")
                
                # Refresh connections after cleanup
                if any(len(conns) > 1 for conns in cert_connections.values()):
                    status = vpn_manager.get_status()
                    current_conns = {conn['id']: conn for conn in status.get('active_connections', [])}
                
                # Check for new connections and update existing ones
                for session_id, conn in current_conns.items():
                    assigned_ip = conn.get('assigned_ip', '-')
                    cert_name = conn.get('username', 'Unknown')
                    client_ip = conn.get('client_ip', '-')
                    
                    if session_id not in _active_sessions:
                        print(f"[SYNC] New connection: {session_id} - {cert_name} - IP: {assigned_ip}")
                        
                        # === Single Connection Enforcement ===
                        # When a new client connects with the same cert, kick existing connections
                        existing_same_cert_sessions = [
                            (sid, sconn) for sid, sconn in _active_sessions.items()
                            if sconn.get('username') == cert_name
                        ]
                        
                        for old_session_id, old_conn in existing_same_cert_sessions:
                            print(f"[SYNC] Kicking previous connection for '{cert_name}': {old_session_id}")
                            success, message = vpn_manager.disconnect_connection(old_session_id)
                            if success:
                                print(f"[SYNC] Successfully kicked old session: {old_session_id}")
                                # Update database status
                                try:
                                    result = await db.execute(
                                        select(ConnectionLog)
                                        .where(ConnectionLog.session_id == str(old_session_id))
                                        .where(ConnectionLog.status == 'connected')
                                    )
                                    old_log = result.scalar_one_or_none()
                                    if old_log:
                                        old_log.status = 'disconnected'
                                        old_log.disconnected_at = datetime.now(timezone(timedelta(hours=8)))
                                        await db.commit()
                                        print(f"[SYNC] Marked old session {old_session_id} as disconnected in DB")
                                except Exception as e:
                                    print(f"[SYNC ERROR] Failed to update old session status: {e}")
                                    await db.rollback()
                                # Remove from active sessions
                                if old_session_id in _active_sessions:
                                    del _active_sessions[old_session_id]
                            else:
                                print(f"[SYNC ERROR] Failed to kick old session {old_session_id}: {message}")
                        try:
                            # Look up system user for this certificate
                            result = await db.execute(
                                select(SystemUser)
                                .where(SystemUser.vpn_cert_name == cert_name)
                                .where(SystemUser.is_active == True)
                            )
                            system_user = result.scalar_one_or_none()
                            bound_username = system_user.username if system_user else None
                            system_user_id = system_user.id if system_user else None
                            
                            if system_user:
                                print(f"[SYNC] Certificate '{cert_name}' is bound to system user '{bound_username}'")
                            else:
                                print(f"[SYNC WARNING] Certificate '{cert_name}' has no system user binding!")
                            
                            # New connection - add to connection log
                            log = ConnectionLog(
                                session_id=str(session_id),
                                client_name=cert_name,
                                username=bound_username or cert_name,
                                tunnel_type=conn.get('tunnel', 'IKEv2'),
                                client_ip=client_ip,
                                assigned_ip=assigned_ip,
                                status='connected',
                                connected_at=datetime.now(timezone(timedelta(hours=8)))
                            )
                            db.add(log)
                            
                            # Also add to UserActivityLog
                            activity_log = UserActivityLog(
                                system_user_id=system_user_id,
                                system_username=bound_username,
                                connection_type='ikev2',
                                vpn_identity=cert_name,
                                client_ip=client_ip,
                                assigned_vpn_ip=assigned_ip,
                                session_id=str(session_id),
                                activity='connected',
                                device_info=f"Tunnel: {conn.get('tunnel', 'IKEv2')}"
                            )
                            db.add(activity_log)
                            
                            await db.commit()
                            _active_sessions[session_id] = conn
                            print(f"[SYNC] Saved connection: {session_id} with IP {assigned_ip}")
                        except Exception as e:
                            print(f"[SYNC ERROR] Failed to save connection: {e}")
                            import traceback
                            traceback.print_exc()
                            await db.rollback()
                    else:
                        # Update assigned_ip if it changed (e.g., from '-' to actual IP)
                        existing_conn = _active_sessions[session_id]
                        old_ip = existing_conn.get('assigned_ip', '-')
                        if old_ip == '-' and assigned_ip != '-':
                            print(f"[SYNC] Updating assigned_ip for {session_id}: {old_ip} -> {assigned_ip}")
                            try:
                                result = await db.execute(
                                    select(ConnectionLog)
                                    .where(ConnectionLog.session_id == str(session_id))
                                    .where(ConnectionLog.status == 'connected')
                                )
                                log = result.scalar_one_or_none()
                                if log:
                                    log.assigned_ip = assigned_ip
                                    await db.commit()
                                    _active_sessions[session_id] = conn
                                    
                                    # Also update UserActivityLog
                                    result = await db.execute(
                                        select(UserActivityLog)
                                        .where(UserActivityLog.session_id == str(session_id))
                                        .where(UserActivityLog.activity == 'connected')
                                    )
                                    activity_log = result.scalar_one_or_none()
                                    if activity_log:
                                        activity_log.assigned_vpn_ip = assigned_ip
                                        await db.commit()
                            except Exception as e:
                                print(f"[SYNC ERROR] Failed to update assigned_ip: {e}")
                                await db.rollback()
                
                # Check for disconnected sessions
                disconnected_sessions = []
                for session_id in list(_active_sessions.keys()):
                    if session_id not in current_conns:
                        print(f"[SYNC] Connection closed: {session_id}")
                        try:
                            # Connection lost - update database
                            result = await db.execute(
                                select(ConnectionLog)
                                .where(ConnectionLog.session_id == str(session_id))
                                .where(ConnectionLog.status == 'connected')
                            )
                            log = result.scalar_one_or_none()
                            if log:
                                log.status = 'disconnected'
                                log.disconnected_at = datetime.now(timezone(timedelta(hours=8)))
                                await db.commit()
                            disconnected_sessions.append(session_id)
                        except Exception as e:
                            print(f"[SYNC ERROR] Failed to update disconnected: {e}")
                            await db.rollback()
                
                # Remove disconnected sessions from tracking
                for session_id in disconnected_sessions:
                    del _active_sessions[session_id]
                
        except Exception as e:
            print(f"[ERROR] Connection sync failed: {e}")
        
        await asyncio.sleep(10)  # Check every 10 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await init_db()
    print("✅ Database initialized")
    print(f"🚀 VPN Manager starting...")
    print(f"   Container: {settings.vpn_container_name}")
    
    # Clean up stale connections from previous runs
    await cleanup_stale_connections()
    
    # Start background tasks
    asyncio.create_task(sync_connection_history())
    asyncio.create_task(scheduled_log_cleanup())
    print("🔄 Background tasks started")
    
    yield
    
    # Shutdown
    print("👋 VPN Manager shutting down...")


async def scheduled_log_cleanup():
    """Run log cleanup every 24 hours"""
    while True:
        await asyncio.sleep(24 * 3600)  # Wait 24 hours
        await cleanup_old_logs()


async def cleanup_stale_connections():
    """Mark all connections that were 'connected' during last shutdown as 'disconnected'"""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, update
            
            # Find all connections that are still marked as 'connected'
            result = await db.execute(
                select(ConnectionLog).where(ConnectionLog.status == 'connected')
            )
            stale_connections = result.scalars().all()
            
            if stale_connections:
                now = datetime.now(timezone(timedelta(hours=8)))
                for conn in stale_connections:
                    conn.status = 'disconnected'
                    conn.disconnected_at = now
                    print(f"[CLEANUP] Marked stale connection as disconnected: {conn.session_id} - {conn.client_name}")
                
                await db.commit()
                print(f"[CLEANUP] Cleaned up {len(stale_connections)} stale connections")
            else:
                print("[CLEANUP] No stale connections found")
    except Exception as e:
        print(f"[CLEANUP ERROR] Failed to cleanup stale connections: {e}")


async def cleanup_old_logs():
    """Clean up logs older than 30 days for audit compliance"""
    try:
        from datetime import timedelta
        
        async with AsyncSessionLocal() as db:
            cutoff_date = datetime.now(timezone(timedelta(hours=8))) - timedelta(days=30)
            
            # Clean up ConnectionLog
            from sqlalchemy import delete
            result = await db.execute(
                delete(ConnectionLog).where(ConnectionLog.connected_at < cutoff_date)
            )
            connection_logs_deleted = result.rowcount
            
            # Clean up UserActivityLog
            result = await db.execute(
                delete(UserActivityLog).where(UserActivityLog.created_at < cutoff_date)
            )
            activity_logs_deleted = result.rowcount
            
            # Clean up CertUsageLog
            result = await db.execute(
                delete(CertUsageLog).where(CertUsageLog.connected_at < cutoff_date)
            )
            cert_logs_deleted = result.rowcount
            
            await db.commit()
            
            total_deleted = connection_logs_deleted + activity_logs_deleted + cert_logs_deleted
            if total_deleted > 0:
                print(f"[CLEANUP] Deleted {connection_logs_deleted} connection logs, "
                      f"{activity_logs_deleted} activity logs, "
                      f"{cert_logs_deleted} cert logs (older than 30 days)")
            else:
                print("[CLEANUP] No old logs to delete")
                
    except Exception as e:
        print(f"[CLEANUP ERROR] Failed to cleanup old logs: {e}")


app = FastAPI(
    title="VPN Manager",
    description="Web-based management for docker-ipsec-vpn-server",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=3600 * 24 * 7 if settings.debug else 3600 * 24  # 7 days in debug, 1 day in prod
)

# Static files and templates - use absolute paths based on this file's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ========== Helper Functions ==========

def check_admin_auth(username: str, password: str) -> bool:
    """Check admin credentials"""
    return username == settings.admin_username and password == settings.admin_password


# Captive Portal Session Storage (Client IP -> Expire Timestamp)
_captive_authenticated_ips: dict = {}
CAPTIVE_SESSION_TTL = 86400  # 24 hours


def get_real_client_ip(request: Request) -> str:
    """Extract real client IP from headers (behind reverse proxy) or connection."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def is_ip_captive_authenticated(ip: str) -> bool:
    """Check if the client IP has completed captive portal authentication."""
    if not ip or ip == "unknown":
        return False
    exp = _captive_authenticated_ips.get(ip)
    if exp is not None:
        if exp > time.time():
            return True
        else:
            del _captive_authenticated_ips[ip]
    return False


def set_ip_captive_authenticated(ip: str, duration: int = CAPTIVE_SESSION_TTL) -> None:
    """Mark a client IP as authenticated for captive portal access."""
    if ip and ip != "unknown":
        _captive_authenticated_ips[ip] = time.time() + duration


def is_valid_vpn_ip(ip: str) -> bool:
    """Check if IP is a valid VPN client IP (192.168.43.0/24)"""
    if not ip or ip == 'unknown':
        return False
    try:
        addr = ipaddress.ip_address(ip)
        vpn_network = ipaddress.ip_network('192.168.43.0/24')
        return addr in vpn_network and ip not in ('192.168.43.0', '192.168.43.255')
    except ValueError:
        return False


async def render_welcome_page(request: Request) -> HTMLResponse:
    """Render welcome landing page with captive portal status and connection details."""
    real_ip = get_real_client_ip(request)
    is_captive_auth = is_ip_captive_authenticated(real_ip)
    
    try:
        vpn_status = vpn_manager.get_status()
        vpn_running = vpn_status.get("container_running", False)
        active_conns = vpn_status.get("active_connections", [])
        active_conns_count = len(active_conns)
        
        is_connected = False
        cert_name = None
        assigned_ip = None
        client_ip = None
        bound_username = None
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(func.count(SystemUser.id)))
            total_users = result.scalar() or 0
            
            if is_valid_vpn_ip(real_ip):
                for conn in active_conns:
                    conn_assigned = conn.get('assigned_ip', '-')
                    conn_client = conn.get('client_ip', '-')
                    if conn_assigned == real_ip or conn_client == real_ip:
                        is_connected = True
                        cert_name = conn.get('username', 'Unknown')
                        assigned_ip = conn_assigned
                        client_ip = conn_client
                        
                        try:
                            user_res = await db.execute(
                                select(SystemUser)
                                .where(SystemUser.vpn_cert_name == cert_name)
                                .where(SystemUser.is_active == True)
                            )
                            system_user = user_res.scalar_one_or_none()
                            if system_user:
                                bound_username = system_user.username
                        except Exception as e:
                            print(f"[WELCOME ERROR] Failed to lookup binding: {e}")
                        break
        
        return templates.TemplateResponse("welcome.html", {
            "request": request,
            "user": None,
            "vpn_running": vpn_running,
            "active_connections": active_conns_count,
            "total_users": total_users,
            "is_connected": is_connected,
            "cert_name": cert_name,
            "bound_username": bound_username,
            "assigned_ip": assigned_ip,
            "client_ip": client_ip,
            "real_ip": real_ip,
            "is_captive_auth": is_captive_auth
        })
    except Exception as e:
        print(f"[WELCOME ERROR] {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("welcome.html", {
            "request": request,
            "user": None,
            "vpn_running": False,
            "active_connections": 0,
            "total_users": 0,
            "is_connected": False,
            "cert_name": None,
            "bound_username": None,
            "assigned_ip": None,
            "client_ip": None,
            "real_ip": real_ip,
            "is_captive_auth": is_captive_auth
        })


def get_captive_redirect_url(request: Request) -> str:
    """Build redirect URL for captive portal, preserving host header if present."""
    host = request.headers.get("Host", "").strip()
    if host:
        return f"http://{host}/welcome"
    return "/welcome"


# Known OS captive probe domains (matching probe requests hitting root '/')
APPLE_PROBE_HOSTS = {
    "captive.apple.com", "www.apple.com", "appleiphonecell.com",
    "ibook.info", "itools.info", "airport.us", "thinkdifferent.us"
}

# Android & domestic Chinese vendor probe hosts (Vivo, Xiaomi, Huawei, Oppo, etc.)
ANDROID_PROBE_HOSTS = {
    # AOSP / Google
    "connectivitycheck.gstatic.com", "www.google.com", "play.googleapis.com",
    "connectivitycheck.android.com", "clients3.google.com", "google.cn", "g.cn",
    # Vivo
    "wifi.vivo.com.cn", "devel.vivo.com.cn",
    # Xiaomi / Redmi
    "connect.rom.miui.com",
    # Huawei / Honor
    "connectivitycheck.platform.hicloud.com", "connectivity.hihonor.com",
    # Oppo / Realme / OnePlus
    "captive.oppomobile.com", "connectivity.coloros.com",
    # Meizu / Others
    "connectivitycheck.flyme.cn", "captiveportal.baidu.com", "wifi.qq.com"
}

WINDOWS_PROBE_HOSTS = {
    "www.msftconnecttest.com", "msftconnecttest.com", "www.msftncsi.com", "msftncsi.com",
    "ipv6.msftconnecttest.com"
}

LINUX_PROBE_HOSTS = {
    "detectportal.firefox.com", "nmcheck.gnome.org"
}


def is_android_probe_host(host: str) -> bool:
    if not host:
        return False
    if host in ANDROID_PROBE_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in (
        ".vivo.com.cn", ".miui.com", ".hicloud.com", ".hihonor.com",
        ".oppomobile.com", ".coloros.com", ".flyme.cn", ".gstatic.com", ".android.com"
    ))


def is_apple_probe_host(host: str) -> bool:
    if not host:
        return False
    if host in APPLE_PROBE_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in (
        ".apple.com", "airport.us", "thinkdifferent.us", "ibook.info", "itools.info"
    ))


def is_windows_probe_host(host: str) -> bool:
    if not host:
        return False
    if host in WINDOWS_PROBE_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in (".msftconnecttest.com", ".msftncsi.com"))


def is_linux_probe_host(host: str) -> bool:
    return host in LINUX_PROBE_HOSTS


# ========== Page Routes ==========

@app.api_route("/", methods=["GET", "HEAD", "POST"], response_class=HTMLResponse)
async def index(request: Request, user: str = Depends(get_current_user)):
    """Landing page - shows dashboard for logged-in users, captive detection or welcome for others"""
    if user:
        return templates.TemplateResponse("index.html", {"request": request, "user": user})
    
    host_header = request.headers.get("Host", "").lower().split(":")[0]
    client_ip = get_real_client_ip(request)
    
    # Check if this is an OS captive portal probe requesting root '/'
    if is_apple_probe_host(host_header):
        if is_ip_captive_authenticated(client_ip):
            return HTMLResponse(
                content="<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>",
                status_code=200
            )
        return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)
    elif is_android_probe_host(host_header):
        if is_ip_captive_authenticated(client_ip):
            return Response(status_code=204)
        return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)
    elif is_windows_probe_host(host_header):
        if is_ip_captive_authenticated(client_ip):
            return PlainTextResponse("Microsoft Connect Test", status_code=200)
        return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)
    elif is_linux_probe_host(host_header):
        if is_ip_captive_authenticated(client_ip):
            return PlainTextResponse("success\n", status_code=200)
        return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)
    
    return await render_welcome_page(request)


@app.api_route("/welcome", methods=["GET", "HEAD", "POST"], response_class=HTMLResponse)
async def welcome_page(request: Request):
    """Explicit welcome and captive portal landing page"""
    return await render_welcome_page(request)


# ========== Captive Portal Probe Routes ==========

@app.api_route("/generate_204", methods=["GET", "HEAD", "POST"])
@app.api_route("/gen_204", methods=["GET", "HEAD", "POST"])
@app.api_route("/mobile/status.php", methods=["GET", "HEAD", "POST"])
async def android_captive_probe(request: Request):
    """Android / ChromeOS / Xiaomi / Huawei / Vivo captive portal probe endpoint"""
    client_ip = get_real_client_ip(request)
    if is_ip_captive_authenticated(client_ip):
        return Response(status_code=204)
    return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)


@app.api_route("/hotspot-detect.html", methods=["GET", "HEAD", "POST"])
@app.api_route("/library/test/success.html", methods=["GET", "HEAD", "POST"])
@app.api_route("/success.html", methods=["GET", "HEAD", "POST"])
@app.api_route("/captive.apple.com/hotspot-detect.html", methods=["GET", "HEAD", "POST"])
async def apple_captive_probe(request: Request):
    """Apple iOS / macOS / iPadOS / watchOS Captive Network Assistant (CNA) probe endpoint"""
    client_ip = get_real_client_ip(request)
    if is_ip_captive_authenticated(client_ip):
        return HTMLResponse(
            content="<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>",
            status_code=200
        )
    return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)


@app.api_route("/connecttest.txt", methods=["GET", "HEAD", "POST"])
@app.api_route("/ncsi.txt", methods=["GET", "HEAD", "POST"])
@app.api_route("/redirect", methods=["GET", "HEAD", "POST"])
@app.api_route("/fwlink", methods=["GET", "HEAD", "POST"])
@app.api_route("/fwlink/", methods=["GET", "HEAD", "POST"])
async def windows_captive_probe(request: Request):
    """Windows NCSI (Network Connectivity Status Indicator) probe endpoint"""
    client_ip = get_real_client_ip(request)
    if is_ip_captive_authenticated(client_ip):
        path = request.url.path
        if "ncsi" in path:
            return PlainTextResponse("Microsoft NCSI", status_code=200)
        return PlainTextResponse("Microsoft Connect Test", status_code=200)
    return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)


@app.api_route("/success.txt", methods=["GET", "HEAD", "POST"])
@app.api_route("/canonical.html", methods=["GET", "HEAD", "POST"])
@app.api_route("/check_network_status.txt", methods=["GET", "HEAD", "POST"])
async def linux_firefox_captive_probe(request: Request):
    """Linux NetworkManager and Firefox captive portal probe endpoint"""
    client_ip = get_real_client_ip(request)
    if is_ip_captive_authenticated(client_ip):
        path = request.url.path
        if "check_network_status" in path:
            return PlainTextResponse("NetworkManager is online\n", status_code=200)
        return PlainTextResponse("success\n", status_code=200)
    return RedirectResponse(url=get_captive_redirect_url(request), status_code=302)


# ========== Captive Portal API Routes ==========

@app.post("/api/captive/complete")
async def api_captive_complete(request: Request):
    """Authorize the client IP to access the Internet via captive portal"""
    client_ip = get_real_client_ip(request)
    set_ip_captive_authenticated(client_ip)
    print(f"[CAPTIVE] Client IP '{client_ip}' successfully authorized for internet access")
    return {
        "success": True,
        "authenticated": True,
        "ip": client_ip,
        "message": "Captive authentication successful"
    }


@app.get("/api/captive/status")
async def api_captive_status(request: Request):
    """Check captive portal authorization status for the requesting client IP"""
    client_ip = get_real_client_ip(request)
    authenticated = is_ip_captive_authenticated(client_ip)
    return {
        "authenticated": authenticated,
        "ip": client_ip
    }


# ========== OIDC / SSO Authentication Routes ==========

def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge (RFC 7636, S256)"""
    verifier_bytes = secrets.token_bytes(64)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).decode('ascii').rstrip('=')
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return code_verifier, code_challenge


@app.get("/api/auth/sso/config")
async def api_sso_config():
    """Return SSO / OIDC availability and provider information"""
    return {
        "enabled": settings.is_oidc_active,
        "provider_name": settings.oidc_provider_name or "SSO 单点登录"
    }


@app.get("/api/auth/sso/login")
async def api_sso_login(request: Request):
    """Initiate OIDC Authorization Code Flow with PKCE"""
    if not settings.is_oidc_active:
        return RedirectResponse(url="/login?error=sso_disabled", status_code=302)
    
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()
    
    request.session["oidc_state"] = state
    request.session["oidc_code_verifier"] = code_verifier
    
    if settings.oidc_redirect_uri:
        redirect_uri = settings.oidc_redirect_uri
    else:
        redirect_uri = str(request.url_for("api_sso_callback"))
        if request.headers.get("X-Forwarded-Proto") == "https":
            redirect_uri = redirect_uri.replace("http://", "https://", 1)
    
    issuer = settings.oidc_issuer_url.rstrip("/")
    auth_endpoint = f"{issuer}/oauth2/auth"
    
    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    
    target_url = f"{auth_endpoint}?{urlencode(params)}"
    return RedirectResponse(url=target_url, status_code=302)


@app.get("/api/auth/sso/callback")
async def api_sso_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    error_description: str = None
):
    """Handle OIDC Callback, exchange code for tokens, and provision/authenticate user"""
    if error:
        err_msg = error_description or error
        print(f"[OIDC ERROR] Provider returned error: {err_msg}")
        return RedirectResponse(url=f"/login?error={err_msg}", status_code=302)
    
    expected_state = request.session.get("oidc_state")
    code_verifier = request.session.get("oidc_code_verifier")
    
    if not state or not expected_state or state != expected_state:
        print("[OIDC ERROR] Invalid state parameter (CSRF detected or session expired)")
        return RedirectResponse(url="/login?error=invalid_state", status_code=302)
    
    if not code:
        return RedirectResponse(url="/login?error=missing_code", status_code=302)
    
    if settings.oidc_redirect_uri:
        redirect_uri = settings.oidc_redirect_uri
    else:
        redirect_uri = str(request.url_for("api_sso_callback"))
        if request.headers.get("X-Forwarded-Proto") == "https":
            redirect_uri = redirect_uri.replace("http://", "https://", 1)
    
    issuer = settings.oidc_issuer_url.rstrip("/")
    token_endpoint = f"{issuer}/oauth2/token"
    
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
        "code_verifier": code_verifier
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            token_resp = await client.post(token_endpoint, data=token_data)
            if token_resp.status_code != 200:
                print(f"[OIDC ERROR] Token endpoint returned {token_resp.status_code}: {token_resp.text}")
                return RedirectResponse(url="/login?error=token_exchange_failed", status_code=302)
            
            token_json = token_resp.json()
            id_token = token_json.get("id_token")
            access_token = token_json.get("access_token")
            
            claims = {}
            if id_token and jwt is not None:
                try:
                    claims = jwt.get_unverified_claims(id_token)
                except Exception as e:
                    print(f"[OIDC WARNING] Failed to decode unverified claims: {e}")
            
            if not claims and access_token:
                userinfo_endpoint = f"{issuer}/oauth2/userinfo"
                userinfo_resp = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if userinfo_resp.status_code == 200:
                    claims = userinfo_resp.json()
            
            sub = str(claims.get("sub", ""))
            username = claims.get("preferred_username") or claims.get("username") or claims.get("name") or sub
            display_name = claims.get("name") or claims.get("nickname") or username
            email = claims.get("email")
            
            if not sub and not username:
                print("[OIDC ERROR] Could not extract user identity from claims")
                return RedirectResponse(url="/login?error=invalid_user_claims", status_code=302)
            
            async with AsyncSessionLocal() as db:
                system_user = None
                if sub:
                    result = await db.execute(select(SystemUser).where(SystemUser.oidc_sub == sub))
                    system_user = result.scalar_one_or_none()
                
                if not system_user and username:
                    result = await db.execute(select(SystemUser).where(SystemUser.username == username))
                    system_user = result.scalar_one_or_none()
                    if system_user:
                        system_user.oidc_sub = sub
                        system_user.auth_provider = "oidc"
                        if email and not system_user.email:
                            system_user.email = email
                        await db.commit()
                
                if not system_user:
                    if settings.oidc_auto_create_user:
                        system_user = SystemUser(
                            username=username,
                            password_hash="OIDC_MANAGED",
                            display_name=display_name,
                            email=email,
                            is_admin=True,
                            is_active=True,
                            auth_provider="oidc",
                            oidc_sub=sub,
                            created_by="OIDC SSO",
                            description="Automatically created via OIDC SSO"
                        )
                        db.add(system_user)
                        await db.commit()
                        await db.refresh(system_user)
                        print(f"[OIDC] Auto-provisioned user '{username}' (sub: {sub})")
                    else:
                        print(f"[OIDC] User '{username}' does not exist locally and auto-provisioning is disabled")
                        return RedirectResponse(url="/login?error=user_not_authorized", status_code=302)
                
                system_user.last_login_at = datetime.now(timezone(timedelta(hours=8)))
                await db.commit()
                authenticated_username = system_user.username
            
            jwt_token = create_access_token({"sub": authenticated_username})
            request.session["user"] = authenticated_username
            
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(
                key="access_token",
                value=f"Bearer {jwt_token}",
                httponly=True,
                max_age=3600 * 24 * 7 if settings.debug else 3600 * 24,
                samesite="lax"
            )
            print(f"[OIDC SUCCESS] User '{authenticated_username}' logged in successfully via SSO")
            return response
            
    except Exception as e:
        print(f"[OIDC ERROR] Exception during SSO callback: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url="/login?error=sso_failed", status_code=302)



@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/public-debug", response_class=HTMLResponse)
async def public_debug_page(request: Request):
    """Public debug page for welcome page"""
    return templates.TemplateResponse("public_debug.html", {"request": request})


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: str = Depends(require_auth)):
    """Users management page"""
    return templates.TemplateResponse("users.html", {"request": request, "user": user})


@app.get("/certs")
async def certs_redirect():
    """Redirect to users page (cert management integrated into user management)"""
    return RedirectResponse(url="/users", status_code=301)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, user: str = Depends(require_auth)):
    """Logs page"""
    return templates.TemplateResponse("logs.html", {"request": request, "user": user})


@app.get("/debug", response_class=HTMLResponse)
async def debug_page(request: Request, user: str = Depends(require_auth)):
    """Debug info page"""
    return templates.TemplateResponse("debug.html", {"request": request, "user": user})


# ========== API Routes - Auth ==========

@app.post("/api/auth/login")
async def api_login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login API - authenticate against database system_users, with fallback to settings"""
    authenticated = False
    
    # 1. 优先查询数据库 system_users 表并校验密码
    try:
        result = await db.execute(
            select(SystemUser).where(
                SystemUser.username == data.username,
                SystemUser.is_active == True
            )
        )
        user = result.scalar_one_or_none()
        if user and verify_password(data.password, user.password_hash):
            authenticated = True
            user.last_login_at = datetime.now(timezone(timedelta(hours=8)))
            await db.commit()
    except Exception as e:
        print(f"[AUTH] Database auth check error: {e}")
    
    # 2. 回退检查环境变量中的 admin 账号密码
    if not authenticated and check_admin_auth(data.username, data.password):
        authenticated = True

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Set session
    request.session["user"] = data.username
    
    # Create token
    token = create_access_token({"sub": data.username})
    
    return LoginResponse(
        success=True,
        message="Login successful",
        token=token
    )


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    """Logout API"""
    request.session.clear()
    return {"success": True, "message": "Logged out"}


@app.get("/api/auth/check")
async def api_check_auth(user: str = Depends(get_current_user)):
    """Check authentication status"""
    return {"authenticated": user is not None, "user": user}


@app.get("/api/public-debug")
async def api_public_debug():
    """Public debug endpoint for welcome page - checks VPN, Internet, LAN status"""
    import subprocess
    import socket
    
    # Check VPN status
    vpn_running = False
    try:
        status = vpn_manager.get_status()
        vpn_running = status.get("container_running", False)
    except Exception as e:
        print(f"[DEBUG] VPN check error: {e}")
    
    # Check Internet connectivity (ping 114.114.114.114 - 国内可靠DNS)
    internet_connected = False
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "114.114.114.114"],
            capture_output=True,
            timeout=10
        )
        internet_connected = result.returncode == 0
    except Exception as e:
        print(f"[DEBUG] Ping check error: {e}")
    
    # If ping fails, try HTTP request to reliable Chinese site
    if not internet_connected:
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://223.5.5.5",  # 阿里云 DNS HTTP 接口
                method="HEAD",
                headers={"User-Agent": "VPN-Manager/1.0"},
                timeout=5
            )
            with urllib.request.urlopen(req) as response:
                internet_connected = True
        except:
            # Try another fallback - curl to baidu
            try:
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "5", "-o", "/dev/null", "-w", "%{http_code}", "http://www.baidu.com"],
                    capture_output=True,
                    text=True,
                    timeout=8
                )
                internet_connected = result.stdout.strip() == "200"
            except Exception as e2:
                print(f"[DEBUG] HTTP check error: {e2}")
    
    # Check LAN server (if configured via LAN_CHECK_HOST and LAN_CHECK_PORT)
    lan_accessible = False
    lan_host = settings.lan_check_host
    lan_port = settings.lan_check_port
    if lan_host and lan_port > 0:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((lan_host, lan_port))
            sock.close()
            lan_accessible = (result == 0)
        except Exception as e:
            print(f"[DEBUG] LAN check error: {e}")
    
    return {
        "vpn_running": vpn_running,
        "internet_connected": internet_connected,
        "lan_accessible": lan_accessible,
        "lan_ip": lan_host or ""
    }


# ========== API Routes - VPN Users ==========

@app.get("/api/users", response_model=List[VPNUserResponse])
async def api_list_users(
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """List all VPN users"""
    # Get users from database
    result = await db.execute(select(VPNUser).order_by(VPNUser.created_at.desc()))
    db_users = result.scalars().all()
    
    # Also get users from container
    container_users = vpn_manager.list_users()
    container_usernames = {u["username"] for u in container_users}
    
    # Sync: add container users to DB if not exists
    for cu in container_users:
        if not any(u.username == cu["username"] for u in db_users):
            new_user = VPNUser(
                username=cu["username"],
                password="*managed_by_container*",
                is_active=cu.get("is_active", True)
            )
            db.add(new_user)
    
    await db.commit()
    
    # Refresh and return
    result = await db.execute(select(VPNUser).order_by(VPNUser.created_at.desc()))
    users = result.scalars().all()
    
    return [u.to_dict() for u in users]


@app.post("/api/users", response_model=VPNUserResponse)
async def api_create_user(
    data: VPNUserCreate,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Create a new VPN user"""
    # Check if user exists in DB
    result = await db.execute(select(VPNUser).where(VPNUser.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    # Add to container
    success, message = vpn_manager.add_user(data.username, data.password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    # Add to database
    db_user = VPNUser(
        username=data.username,
        password="*managed*",
        description=data.description
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user.to_dict()


@app.put("/api/users/{username}")
async def api_update_user(
    username: str,
    data: VPNUserUpdate,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Update VPN user"""
    result = await db.execute(select(VPNUser).where(VPNUser.username == username))
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password if provided
    if data.password:
        success, message = vpn_manager.update_password(username, data.password)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
    
    # Update other fields
    if data.is_active is not None:
        db_user.is_active = data.is_active
    if data.description is not None:
        db_user.description = data.description
    
    await db.commit()
    await db.refresh(db_user)
    
    return db_user.to_dict()


@app.delete("/api/users/{username}")
async def api_delete_user(
    username: str,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Delete VPN user"""
    # Don't allow deleting admin
    if username == settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin user"
        )
    
    # Delete from container
    success, message = vpn_manager.delete_user(username)
    # Note: we continue even if container delete fails, as user might not exist there
    
    # Delete from database
    result = await db.execute(select(VPNUser).where(VPNUser.username == username))
    db_user = result.scalar_one_or_none()
    
    if db_user:
        await db.delete(db_user)
        
    # Unbind from system_users
    su_result = await db.execute(select(SystemUser).where(SystemUser.vpn_username == username))
    for su in su_result.scalars().all():
        su.vpn_username = None
        
    await db.commit()
    
    return {"success": True, "message": f"User '{username}' deleted"}


# ========== API Routes - Certificates ==========

@app.get("/api/certs")
async def api_list_certs(
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """List all IKEv2 certificates from container and merge with database info"""
    # Get certs from container
    container_certs = vpn_manager.list_ikev2_certs()
    print(f"[DEBUG] Container certs: {len(container_certs)}")
    
    # Get database records for descriptions
    result = await db.execute(select(IKEv2Certificate))
    db_certs = {c.client_name: c for c in result.scalars().all()}
    print(f"[DEBUG] DB certs: {len(db_certs)}")
    
    # Merge container certs with db info
    certs = []
    for idx, cert in enumerate(container_certs, 1):
        client_name = cert["name"]
        db_cert = db_certs.get(client_name)
        
        certs.append({
            "id": db_cert.id if db_cert else idx,
            "client_name": client_name,
            "status": cert.get("status", "valid"),
            "created_at": db_cert.created_at.isoformat() if db_cert and db_cert.created_at else None,
            "expires_at": db_cert.expires_at.isoformat() if db_cert and db_cert.expires_at else None,
            "is_active": cert.get("status") == "valid",
            "description": db_cert.description if db_cert else None,
            "p12_path": cert.get("p12_path"),
            "mobileconfig_path": cert.get("mobileconfig_path"),
            "sswan_path": cert.get("sswan_path"),
        })
    
    print(f"[DEBUG] Returning certs: {len(certs)}")
    return certs


@app.post("/api/certs")
async def api_create_cert(
    data: CertCreate,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Generate new IKEv2 certificate"""
    # Check if cert exists
    result = await db.execute(
        select(IKEv2Certificate).where(IKEv2Certificate.client_name == data.client_name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate with this name already exists"
        )
    
    # Generate cert
    success, message, p12_data = vpn_manager.generate_ikev2_cert(data.client_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    # Save to database
    db_cert = IKEv2Certificate(
        client_name=data.client_name,
        p12_path=f"/etc/ipsec.d/{data.client_name}.p12",
        description=data.description
    )
    db.add(db_cert)
    await db.commit()
    await db.refresh(db_cert)
    
    return {
        "success": True,
        "message": message,
        "cert": db_cert.to_dict(),
        "p12_data": p12_data
    }


@app.delete("/api/certs/{client_name}")
async def api_delete_cert(
    client_name: str,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Revoke IKEv2 certificate"""
    success, message = vpn_manager.revoke_ikev2_cert(client_name)
    
    # Delete from database
    result = await db.execute(
        select(IKEv2Certificate).where(IKEv2Certificate.client_name == client_name)
    )
    db_cert = result.scalar_one_or_none()
    
    if db_cert:
        await db.delete(db_cert)
        
    # Unbind from system_users
    su_result = await db.execute(
        select(SystemUser).where(SystemUser.vpn_cert_name == client_name)
    )
    for su in su_result.scalars().all():
        su.vpn_cert_name = None
        
    # Delete from user_cert_bindings
    await db.execute(
        delete(UserCertBinding).where(UserCertBinding.cert_name == client_name)
    )
    
    await db.commit()
    
    return {"success": success, "message": message}


@app.get("/api/certs/{client_name}/download")
async def api_download_cert(
    client_name: str,
    format: str = "p12",
    user: str = Depends(require_auth)
):
    """Download IKEv2 certificate in specified format"""
    success, message, file_data, filename = vpn_manager.export_ikev2_cert(client_name, format)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    # Map format to MIME type
    mime_types = {
        "p12": "application/x-pkcs12",
        "mobileconfig": "application/x-apple-aspen-config",
        "sswan": "application/octet-stream"
    }
    
    return {
        "success": True,
        "filename": filename,
        "content_type": mime_types.get(format, "application/octet-stream"),
        "data": file_data
    }


# ========== API Routes - Status & Logs ==========

@app.get("/api/status")
async def api_status(user: str = Depends(require_auth)):
    """Get VPN status - requires authentication"""
    return vpn_manager.get_status()


@app.get("/api/public/info")
async def api_public_info():
    """Get public info for landing page - no authentication required"""
    try:
        # Get VPN status (public info only)
        vpn_status = vpn_manager.get_status()
        
        # Get total users count
        async with AsyncSessionLocal() as db:
            from sqlalchemy import func
            result = await db.execute(select(func.count(SystemUser.id)))
            total_users = result.scalar() or 0
        
        return {
            "success": True,
            "data": {
                "vpn_running": vpn_status.get("container_running", False),
                "active_connections": len(vpn_status.get("active_connections", [])),
                "total_users": total_users,
                "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "data": {
                "vpn_running": False,
                "active_connections": 0,
                "total_users": 0
            }
        }


@app.get("/api/public/my-ip")
async def api_public_my_ip(request: Request):
    """No-auth endpoint to diagnose what IP the server sees from the client.
    VPN clients can call this to check if their VPN IP is visible."""
    direct_ip = request.client.host if request.client else 'unknown'
    forwarded_for = request.headers.get('X-Forwarded-For')
    real_ip = forwarded_for.split(',')[0].strip() if forwarded_for else (
        request.headers.get('X-Real-IP') or direct_ip
    )
    return {
        "direct_ip": direct_ip,
        "real_ip": real_ip,
        "is_vpn_ip": is_valid_vpn_ip(real_ip),
        "headers": {
            "X-Forwarded-For": request.headers.get('X-Forwarded-For'),
            "X-Real-IP": request.headers.get('X-Real-IP'),
            "User-Agent": request.headers.get('User-Agent'),
        }
    }


@app.get("/api/stats")
async def api_stats(
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Get system statistics"""
    vpn_status = vpn_manager.get_status()
    
    # Convert cert names to bound usernames in active connections
    for conn in vpn_status.get('active_connections', []):
        cert_name = conn.get('username', '')
        if cert_name:
            result = await db.execute(
                select(SystemUser)
                .where(SystemUser.vpn_cert_name == cert_name)
                .where(SystemUser.is_active == True)
            )
            system_user = result.scalar_one_or_none()
            if system_user:
                conn['username'] = system_user.username
    
    # Count system users (与 /api/system-users 保持一致)
    result = await db.execute(select(func.count(SystemUser.id)))
    total_users = result.scalar()
    
    # Count certs
    result = await db.execute(select(func.count(IKEv2Certificate.id)))
    total_certs = result.scalar()
    
    return {
        "vpn_status": vpn_status,
        "total_users": total_users,
        "total_certs": total_certs
    }


@app.get("/api/logs")
async def api_logs(
    lines: int = 100,
    user: str = Depends(require_auth)
):
    """Get container logs"""
    return {"logs": vpn_manager.get_logs(lines)}


@app.post("/api/connections/kick-all")
async def api_kick_all_connections(
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Kick all active VPN connections"""
    from datetime import datetime, timezone, timedelta
    
    vpn_status = vpn_manager.get_status()
    active_conns = vpn_status.get('active_connections', [])
    
    kicked = []
    failed = []
    
    for conn in active_conns:
        session_id = conn.get('id')
        cert_name = conn.get('username', 'Unknown')
        
        success, message = vpn_manager.disconnect_connection(session_id)
        if success:
            kicked.append({
                "session_id": session_id,
                "cert_name": cert_name,
                "client_ip": conn.get('client_ip'),
                "assigned_ip": conn.get('assigned_ip')
            })
            print(f"[KICK-ALL] Kicked session {session_id} - {cert_name}")
            
            # Update database
            try:
                result = await db.execute(
                    select(ConnectionLog)
                    .where(ConnectionLog.session_id == str(session_id))
                    .where(ConnectionLog.status == 'connected')
                )
                log = result.scalar_one_or_none()
                if log:
                    log.status = 'disconnected'
                    log.disconnected_at = datetime.now(timezone(timedelta(hours=8)))
                    await db.commit()
            except Exception as e:
                print(f"[KICK-ALL ERROR] Failed to update DB for {session_id}: {e}")
                await db.rollback()
            
            # Remove from active sessions tracking
            if session_id in _active_sessions:
                del _active_sessions[session_id]
        else:
            failed.append({
                "session_id": session_id,
                "cert_name": cert_name,
                "error": message
            })
            print(f"[KICK-ALL ERROR] Failed to kick {session_id}: {message}")
    
    return {
        "success": True,
        "kicked_count": len(kicked),
        "failed_count": len(failed),
        "kicked": kicked,
        "failed": failed
    }



@app.get("/api/debug/network-info")
async def api_network_info(
    request: Request,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Get network debug info and all active VPN connections with security validation"""
    # Get direct TCP connection IP (what web server sees at TCP level)
    direct_ip = request.client.host if request.client else 'unknown'
    
    # Get real IP from request (considering proxy headers)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        real_ip = forwarded_for.split(',')[0].strip()
    else:
        real_ip = request.headers.get('X-Real-IP') or direct_ip
    
    # Security: Validate IP is from VPN subnet
    is_trusted_vpn_ip = is_valid_vpn_ip(real_ip)
    
    # Also get raw trafficstatus for debugging
    raw_trafficstatus = ""
    try:
        exit_code, raw_out, _ = vpn_manager.exec_command(["ipsec", "whack", "--trafficstatus"])
        raw_trafficstatus = raw_out if exit_code == 0 else f"(exit_code={exit_code})"
    except Exception as e:
        raw_trafficstatus = f"(error: {e})"
    
    try:
        # Get all active connections from VPN manager
        vpn_status = vpn_manager.get_status()
        active_conns = vpn_status.get('active_connections', [])
        
        # Security: Verify the IP is actually in active VPN connections
        ip_verified_in_connections = False
        matched_connection = None
        
        if is_trusted_vpn_ip:
            for conn in active_conns:
                # Match by assigned_ip (VPN internal IP) OR client_ip (public IP)
                if conn.get('assigned_ip') == real_ip or conn.get('client_ip') == real_ip:
                    ip_verified_in_connections = True
                    matched_connection = conn
                    break
        
        # Security logging
        if is_trusted_vpn_ip and not ip_verified_in_connections:
            print(f"[SECURITY WARNING] IP {real_ip} claims to be VPN client but not in active connections!")
            print(f"[SECURITY WARNING] active_conns={active_conns}")
        
        print(f"[DEBUG] real_ip={real_ip}, direct_ip={direct_ip}, connections={len(active_conns)}, verified={ip_verified_in_connections}")
        
    except Exception as e:
        print(f"[DEBUG] Error getting network info: {e}")
        import traceback
        traceback.print_exc()
        active_conns = []
        ip_verified_in_connections = False
        matched_connection = None
    
    return {
        "success": True,
        "data": {
            "real_ip": real_ip,
            "direct_ip": direct_ip,
            "is_vpn_ip": is_trusted_vpn_ip,
            "ip_verified": ip_verified_in_connections,
            "matched_connection": matched_connection,
            "active_connections": active_conns,
            "raw_trafficstatus": raw_trafficstatus,
            "user_agent": request.headers.get('User-Agent', ''),
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()
        }
    }


@app.get("/api/debug/raw-vpn-status")
async def api_raw_vpn_status(
    user: str = Depends(require_auth)
):
    """Get raw ipsec status output for debugging IP matching issues"""
    result = {}
    
    # Raw trafficstatus
    exit_code, stdout, stderr = vpn_manager.exec_command(["ipsec", "whack", "--trafficstatus"])
    result["trafficstatus"] = {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    }
    
    # Raw ipsec status (first 50 lines)
    exit_code2, stdout2, stderr2 = vpn_manager.exec_command(["ipsec", "status"])
    result["ipsec_status"] = {
        "exit_code": exit_code2,
        "stdout": "\n".join(stdout2.split("\n")[:50]) if stdout2 else "",
        "stderr": stderr2
    }
    
    # Parsed result
    vpn_status = vpn_manager.get_status()
    result["parsed_connections"] = vpn_status.get('active_connections', [])
    
    return result


@app.get("/api/connection-logs")
async def api_connection_logs(
    limit: int = 100,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Get connection logs from database"""
    from datetime import datetime
    
    # Get recent logs from database
    result = await db.execute(
        select(ConnectionLog)
        .order_by(ConnectionLog.connected_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    # Get stats
    result = await db.execute(select(func.count(ConnectionLog.id)))
    total = result.scalar() or 0
    
    result = await db.execute(
        select(func.count(ConnectionLog.id))
        .where(ConnectionLog.status == 'connected')
    )
    active = result.scalar() or 0
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(ConnectionLog.id))
        .where(ConnectionLog.connected_at >= today)
    )
    today_count = result.scalar() or 0
    
    return {
        "logs": [log.to_dict() for log in logs],
        "stats": {
            "total": total,
            "active": active,
            "today": today_count
        }
    }


# ========== API Routes - Certificate Binding & Audit ==========

@app.get("/api/cert-bindings")
async def api_list_cert_bindings(
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """List all certificate-user bindings"""
    result = await db.execute(select(UserCertBinding).order_by(UserCertBinding.assigned_at.desc()))
    bindings = result.scalars().all()
    return {"bindings": [b.to_dict() for b in bindings]}


@app.post("/api/cert-bindings")
async def api_create_cert_binding(
    request: Request,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Create a new certificate-user binding"""
    data = await request.json()
    cert_name = data.get('cert_name')
    target_username = data.get('username')
    description = data.get('description', '')
    
    if not cert_name or not target_username:
        raise HTTPException(status_code=400, detail="证书名和用户名不能为空")
    
    # Check if cert already bound
    result = await db.execute(
        select(UserCertBinding)
        .where(UserCertBinding.cert_name == cert_name)
        .where(UserCertBinding.is_active == True)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"证书 '{cert_name}' 已绑定到用户 '{existing.username}'")
    
    binding = UserCertBinding(
        username=target_username,
        cert_name=cert_name,
        assigned_by=user,
        description=description
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    
    return {"success": True, "binding": binding.to_dict()}


@app.delete("/api/cert-bindings/{binding_id}")
async def api_delete_cert_binding(
    binding_id: int,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a certificate binding"""
    result = await db.execute(
        select(UserCertBinding).where(UserCertBinding.id == binding_id)
    )
    binding = result.scalar_one_or_none()
    
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    binding.is_active = False
    await db.commit()
    
    return {"success": True, "message": "绑定已解除"}


@app.get("/api/cert-audit/{cert_name}")
async def api_cert_audit_log(
    cert_name: str,
    limit: int = 50,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Get audit log for a specific certificate"""
    # Get binding info
    result = await db.execute(
        select(UserCertBinding)
        .where(UserCertBinding.cert_name == cert_name)
    )
    binding = result.scalar_one_or_none()
    
    # Get usage logs
    result = await db.execute(
        select(CertUsageLog)
        .where(CertUsageLog.cert_name == cert_name)
        .order_by(CertUsageLog.connected_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    # Get stats
    result = await db.execute(
        select(func.count(CertUsageLog.id))
        .where(CertUsageLog.cert_name == cert_name)
    )
    total_usage = result.scalar() or 0
    
    # Get unique IPs
    result = await db.execute(
        select(CertUsageLog.client_ip)
        .where(CertUsageLog.cert_name == cert_name)
        .distinct()
    )
    unique_ips = [r[0] for r in result.all()]
    
    return {
        "cert_name": cert_name,
        "bound_user": binding.username if binding else None,
        "binding_active": binding.is_active if binding else False,
        "total_usage_count": total_usage,
        "unique_client_ips": unique_ips,
        "recent_logs": [log.to_dict() for log in logs]
    }


# ========== API Routes - System User Management ==========

@app.get("/api/system-users")
async def api_list_system_users(
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """List all system users with their VPN bindings"""
    result = await db.execute(
        select(SystemUser).order_by(SystemUser.created_at.desc())
    )
    users = result.scalars().all()
    return {"users": [u.to_dict() for u in users]}


@app.get("/api/system-users/{user_id}")
async def api_get_system_user(
    user_id: int,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific system user with details"""
    result = await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )
    system_user = result.scalar_one_or_none()
    
    if not system_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # Get activity logs
    result = await db.execute(
        select(UserActivityLog)
        .where(UserActivityLog.system_user_id == user_id)
        .order_by(UserActivityLog.created_at.desc())
        .limit(20)
    )
    activities = result.scalars().all()
    
    return {
        "user": system_user.to_dict(),
        "recent_activities": [a.to_dict() for a in activities]
    }


@app.post("/api/system-users")
async def api_create_system_user(
    request: Request,
    current_user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Create a new system user with optional VPN bindings"""
    data = await request.json()
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    
    # Check if username exists
    result = await db.execute(
        select(SystemUser).where(SystemUser.username == username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # Check VPN cert uniqueness
    vpn_cert_name = data.get('vpn_cert_name')
    if vpn_cert_name:
        result = await db.execute(
            select(SystemUser).where(SystemUser.vpn_cert_name == vpn_cert_name)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"证书 '{vpn_cert_name}' 已被其他用户绑定")
    
    # Check VPN username uniqueness
    vpn_username = data.get('vpn_username')
    if vpn_username:
        result = await db.execute(
            select(SystemUser).where(SystemUser.vpn_username == vpn_username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"VPN用户名 '{vpn_username}' 已被其他用户绑定")
    
    # Hash password (simple hash for now, should use bcrypt in production)
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    system_user = SystemUser(
        username=username,
        password_hash=password_hash,
        vpn_cert_name=vpn_cert_name,
        vpn_username=vpn_username,
        vpn_password=data.get('vpn_password'),  # Should encrypt this
        display_name=data.get('display_name'),
        email=data.get('email'),
        is_admin=data.get('is_admin', False),
        description=data.get('description'),
        created_by=current_user
    )
    db.add(system_user)
    await db.commit()
    await db.refresh(system_user)
    
    return {"success": True, "user": system_user.to_dict()}


@app.put("/api/system-users/{user_id}")
async def api_update_system_user(
    user_id: int,
    request: Request,
    current_user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Update a system user and their VPN bindings"""
    data = await request.json()
    
    result = await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )
    system_user = result.scalar_one_or_none()
    
    if not system_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # Update VPN cert binding
    new_cert_name = data.get('vpn_cert_name')
    if new_cert_name and new_cert_name != system_user.vpn_cert_name:
        result = await db.execute(
            select(SystemUser).where(
                SystemUser.vpn_cert_name == new_cert_name,
                SystemUser.id != user_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"证书 '{new_cert_name}' 已被其他用户绑定")
        system_user.vpn_cert_name = new_cert_name
    
    # Update VPN username binding
    new_vpn_username = data.get('vpn_username')
    if new_vpn_username and new_vpn_username != system_user.vpn_username:
        result = await db.execute(
            select(SystemUser).where(
                SystemUser.vpn_username == new_vpn_username,
                SystemUser.id != user_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"VPN用户名 '{new_vpn_username}' 已被其他用户绑定")
        system_user.vpn_username = new_vpn_username
    
    # Update other fields
    if 'display_name' in data:
        system_user.display_name = data['display_name']
    if 'email' in data:
        system_user.email = data['email']
    if 'description' in data:
        system_user.description = data['description']
    if 'is_active' in data:
        system_user.is_active = data['is_active']
    if 'vpn_password' in data:
        system_user.vpn_password = data['vpn_password']
    
    await db.commit()
    await db.refresh(system_user)
    
    return {"success": True, "user": system_user.to_dict()}


@app.delete("/api/system-users/{user_id}")
async def api_delete_system_user(
    user_id: int,
    current_user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Delete a system user and thoroughly clean up VPN certificates and configuration"""
    result = await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )
    system_user = result.scalar_one_or_none()
    
    if not system_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if system_user.username == current_user:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")
    
    if system_user.username == settings.admin_username:
        raise HTTPException(status_code=400, detail="不能删除系统管理员账号")

    username = system_user.username
    vpn_cert_name = system_user.vpn_cert_name
    vpn_username = system_user.vpn_username

    # 1. 断开该用户的活跃 VPN 连接
    try:
        vpn_status = vpn_manager.get_status()
        active_conns = vpn_status.get('active_connections', [])
        for conn in active_conns:
            conn_user = conn.get('username')
            session_id = conn.get('id')
            if conn_user and session_id:
                if (vpn_cert_name and conn_user == vpn_cert_name) or \
                   (vpn_username and conn_user == vpn_username) or \
                   (conn_user == username):
                    vpn_manager.disconnect_connection(session_id)
                    print(f"[DELETE-USER] Kicked active session {session_id} for user {username}")
    except Exception as e:
        print(f"[DELETE-USER] Error disconnecting sessions for {username}: {e}")

    # 2. 注销并清理 VPN 证书
    cert_names_to_clean = set()
    if vpn_cert_name:
        cert_names_to_clean.add(vpn_cert_name)
    # 检查是否有与 username 同名的证书
    res_cert = await db.execute(
        select(IKEv2Certificate).where(IKEv2Certificate.client_name == username)
    )
    if res_cert.scalar_one_or_none():
        cert_names_to_clean.add(username)

    for cert_name in cert_names_to_clean:
        # 容器内注销证书及清理文件
        try:
            vpn_manager.revoke_ikev2_cert(cert_name)
            print(f"[DELETE-USER] Revoked certificate '{cert_name}'")
        except Exception as e:
            print(f"[DELETE-USER] Error revoking cert '{cert_name}': {e}")
        
        # 数据库中删除证书记录
        try:
            await db.execute(
                delete(IKEv2Certificate).where(IKEv2Certificate.client_name == cert_name)
            )
        except Exception as e:
            print(f"[DELETE-USER] Error deleting cert '{cert_name}' from DB: {e}")
        
        # 数据库中删除证书绑定记录
        try:
            await db.execute(
                delete(UserCertBinding).where(UserCertBinding.cert_name == cert_name)
            )
        except Exception as e:
            print(f"[DELETE-USER] Error deleting cert binding '{cert_name}' from DB: {e}")

    # 3. 删除 VPN 账号配置
    vpn_users_to_clean = set()
    if vpn_username:
        vpn_users_to_clean.add(vpn_username)
    # 检查是否有与 username 同名的 VPN 账号
    res_vpn_user = await db.execute(
        select(VPNUser).where(VPNUser.username == username)
    )
    if res_vpn_user.scalar_one_or_none():
        vpn_users_to_clean.add(username)

    for v_user in vpn_users_to_clean:
        # 容器内删除 VPN 账号 (/etc/ipsec.d/passwd & chap-secrets)
        try:
            vpn_manager.delete_user(v_user)
            print(f"[DELETE-USER] Deleted VPN user '{v_user}' from container")
        except Exception as e:
            print(f"[DELETE-USER] Error deleting VPN user '{v_user}' from container: {e}")
        
        # 数据库中删除 VPNUser
        try:
            await db.execute(
                delete(VPNUser).where(VPNUser.username == v_user)
            )
        except Exception as e:
            print(f"[DELETE-USER] Error deleting VPN user '{v_user}' from DB: {e}")

    # 4. 从数据库完全删除系统用户
    await db.delete(system_user)
    await db.commit()

    return {
        "success": True,
        "message": f"用户 '{username}' 及其关联的 VPN 证书和配置已彻底删除"
    }


@app.get("/api/system-users/{user_id}/vpn-status")
async def api_get_user_vpn_status(
    user_id: int,
    user: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Get current VPN connection status for a system user"""
    result = await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )
    system_user = result.scalar_one_or_none()
    
    if not system_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # Get active VPN connections
    vpn_status = vpn_manager.get_status()
    active_conns = vpn_status.get('active_connections', [])
    
    # Find connections matching this user's VPN identities
    user_connections = []
    for conn in active_conns:
        if (system_user.vpn_cert_name and conn.get('username') == system_user.vpn_cert_name) or \
           (system_user.vpn_username and conn.get('username') == system_user.vpn_username):
            user_connections.append(conn)
    
    return {
        "user_id": user_id,
        "username": system_user.username,
        "vpn_cert_name": system_user.vpn_cert_name,
        "vpn_username": system_user.vpn_username,
        "is_online": len(user_connections) > 0,
        "active_connections": user_connections
    }


# ========== WebSocket for Real-time Updates ==========

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Receive ping from client
            data = await websocket.receive_text()
            print(f"[DEBUG] WS received: {data}")
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "status":
                status = vpn_manager.get_status()
                
                # Convert cert names to bound usernames
                async with AsyncSessionLocal() as db:
                    for conn in status.get('active_connections', []):
                        cert_name = conn.get('username', '')
                        if cert_name:
                            result = await db.execute(
                                select(SystemUser)
                                .where(SystemUser.vpn_cert_name == cert_name)
                                .where(SystemUser.is_active == True)
                            )
                            system_user = result.scalar_one_or_none()
                            if system_user:
                                conn['username'] = system_user.username
                                print(f"[WS] Mapped {cert_name} -> {system_user.username}")
                
                print(f"[DEBUG] WS get_status: {len(status['active_connections'])} connections")
                await websocket.send_json({"type": "status", "data": status})
                print(f"[DEBUG] WS status sent")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ========== Error Handlers ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail}
        )
    return HTMLResponse(content=f"Error: {exc.detail}", status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
