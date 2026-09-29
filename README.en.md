# VPN Manager

A modern, responsive web management dashboard for [hwdsl2/docker-ipsec-vpn-server](https://github.com/hwdsl2/docker-ipsec-vpn-server), featuring VPN user management, IKEv2 client certificate lifecycle management (generation, download, and revocation), real-time WebSocket monitoring, and network diagnostics.

<p align="right">
  <b>English</b> | <a href="./README.md">简体中文</a>
</p>

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![Docker](https://img.shields.io/badge/Docker-compatible-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## ✨ Features

- 🔐 **User Management** - Create, delete, and modify VPN users and credentials.
- 📜 **IKEv2 Certificate Management** - Generate, export, and revoke client certificates (`.p12`, `.mobileconfig`, `.sswan`).
- 🌐 **Multi-Language Support** - Built-in bilingual UI (English / 简体中文) with one-click instant toggle.
- 📊 **Real-time Monitoring** - Live WebSocket stream showing server health, active connections, and client sessions.
- 📝 **Container Logs** - View and tail VPN container runtime logs directly from the dashboard.
- 🛡️ **Authentication & Security** - Session + JWT authentication with configurable security keys.
- 📱 **Modern & Responsive UI** - Polished dashboard interface optimized for mobile and desktop screens.
- 🗄️ **Persistent Storage** - SQLite database cleanly managed in `./data/vpnmgr.db` with Docker volume support.

---

## 🚀 Quick Start

### Method 1: Local / Host Installation

#### 1. Clone the repository
```bash
git clone https://github.com/Roger-hunt/vpnmgr.git
cd vpnmgr
```

#### 2. Create virtual environment & install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env to customize admin credentials and security secrets
```

#### 4. Start the service
```bash
python start.py
```
Open your browser and navigate to `http://localhost:8080`.
- **Default username**: `admin`
- **Default password**: `admin123` *(Please change upon first login)*

---

### Method 2: Docker Compose (Recommended for Production)

```bash
# Build and run containers in background
docker-compose up -d

# Inspect container logs
docker-compose logs -f
```

---

## ⚙️ Configuration Reference

Edit the `.env` file to customize settings:

```env
# Web UI Administrator Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# Session & JWT Secret Key (generate a strong random string)
SECRET_KEY=generate-a-secure-random-secret-key

# Docker Container Name (must match your IPsec VPN server container)
VPN_CONTAINER_NAME=ipsec-vpn-server

# Database Connection URL
DATABASE_URL=sqlite+aiosqlite:///./data/vpnmgr.db

# Server Listening Address
HOST=0.0.0.0
PORT=8080
DEBUG=false

# Optional: LAN health check probe
LAN_CHECK_HOST=
LAN_CHECK_PORT=0
```

---

## 📖 Usage Guide

### 1. Managing VPN Users
1. Go to the **User Management** page (`/users`).
2. Click **Add User**, enter the desired username and password (or click the random password generator).
3. Click Save. The user credentials become active immediately in the VPN container.

### 2. Issuing & Revoking IKEv2 Certificates
1. Go to the **Certificates** page (`/certs`).
2. Click **Generate Certificate**, input the client identifier (e.g. `iPhone-Alice`).
3. Download the configuration file for your platform:
   - **iOS / macOS**: Download `.mobileconfig` or `.p12` and install via Settings.
   - **Android**: Download `.sswan` (for strongSwan VPN Client) or import `.p12`.
   - **Windows**: Import `.p12` into the "Personal" certificate store.
4. **Revocation**: Click **Revoke** on any certificate to invalidate access immediately and unbind users.

### 3. Real-time Monitoring & Dashboard
The **Dashboard** (`/`) connects via WebSocket to provide live status:
- VPN server container status (Running / Stopped / CPU / Memory).
- Active connected clients with leased IP addresses and traffic stats.
- Network connectivity diagnostics.

---

## 📁 Directory Structure

```
vpnmgr/
├── data/                    # Database storage directory (persisted)
│   ├── .gitkeep
│   └── vpnmgr.db            # SQLite database
├── vpnmgr/                  # Core application package
│   ├── main.py              # FastAPI application & API endpoints
│   ├── config.py            # Application settings & environment loader
│   ├── schemas.py           # Pydantic data validation schemas
│   ├── models/              # SQLAlchemy database models
│   │   ├── database.py      # Async DB engine & automatic migration
│   │   ├── vpn_user.py      # VPN account model
│   │   ├── ikev2_cert.py    # IKEv2 certificate model
│   │   └── system_user.py   # Admin accounts
│   ├── utils/               # Helper utilities
│   │   ├── vpn_manager.py   # Docker & strongSwan CLI bridge
│   │   └── auth.py          # Password hashing & JWT handlers
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # Static frontend assets
│       ├── css/             # Modern CSS styles
│       └── js/
│           ├── app.js       # Dashboard logic & WebSocket handlers
│           └── i18n.js      # Bilingual translation dictionary
├── scripts/                 # Network & maintenance utility scripts
├── requirements.txt         # Python dependencies
├── docker-compose.yml       # Docker deployment configuration
├── Dockerfile               # Container build file
├── ecosystem.config.js      # PM2 process manager configuration
├── start.py                 # Startup entrypoint
└── README.md                # Documentation (Chinese / English)
```

---

## 🔒 Security Best Practices

1. **Rotate Default Password**: Change the initial `admin123` password immediately upon installation.
2. **Generate Strong Secret**: Set a unique `SECRET_KEY` in `.env` using `openssl rand -hex 32`.
3. **Use HTTPS**: In production, deploy behind an SSL reverse proxy (e.g., Nginx, Caddy, or Cloudflare).
4. **Firewall Isolation**: Expose only port 8080 (Web UI) to trusted administration networks, while opening UDP 500/4500 publicly for VPN traffic.

---

## 🌐 Nginx Reverse Proxy Example

```nginx
server {
    listen 443 ssl http2;
    server_name vpn.example.com;
    
    ssl_certificate /etc/letsencrypt/live/vpn.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vpn.example.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🛠️ Troubleshooting

### Cannot connect to Docker container
Verify that the application has permissions to communicate with `/var/run/docker.sock`:
```bash
# Ensure current user belongs to the docker group
sudo usermod -aG docker $USER
```

### Reset Admin Password
If you lose your administrative credentials, reset them locally using the CLI utility:
```bash
python3 reset_pwd.py [new_password]
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
