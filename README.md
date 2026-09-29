# VPN Manager

一个基于 Web 的 docker-ipsec-vpn-server 管理面板，支持用户管理、IKEv2 证书管理和实时状态监控。

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![Docker](https://img.shields.io/badge/Docker-compatible-blue.svg)

## 功能特性

- 🔐 **用户管理** - 添加、删除、修改 VPN 用户密码
- 📜 **证书管理** - 生成和撤销 IKEv2 证书 (.p12)
- 📊 **实时监控** - WebSocket 实时显示连接状态
- 📝 **日志查看** - 查看 VPN 容器日志
- 🔒 **安全认证** - JWT + Session 双认证机制
- 📱 **响应式设计** - 支持桌面和移动设备

## 快速开始

### 方式一：直接运行

1. 克隆项目
```bash
cd vpnmgr
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，设置管理员密码等
```

4. 启动服务
```bash
python start.py
```

访问 http://localhost:8080，默认用户名 `admin`，密码 `admin123`

### 方式二：Docker 运行

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 配置说明

编辑 `.env` 文件：

```env
# 管理员账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# 安全密钥 (请修改)
SECRET_KEY=your-secret-key

# Docker 容器名称 (必须与你的 VPN 容器名称一致)
VPN_CONTAINER_NAME=ipsec-vpn-server

# 服务器设置
HOST=0.0.0.0
PORT=8080
```

## 使用说明

### 添加 VPN 用户

1. 进入"用户管理"页面
2. 点击"添加用户"按钮
3. 输入用户名和密码（可点击随机生成按钮）
4. 保存即可，用户会立即生效

### 生成 IKEv2 证书

1. 进入"证书管理"页面
2. 点击"生成证书"按钮
3. 输入客户端名称（如：iPhone-张三）
4. 下载 .p12 文件并安装到设备

**各平台安装方式：**
- **iOS/macOS**: 通过邮件/AirDrop 发送，点击安装
- **Windows**: 双击导入到"个人"证书存储
- **Android**: 设置 -> 安全 -> 从存储安装证书

### 查看实时状态

概览页面通过 WebSocket 实时显示：
- VPN 容器运行状态
- 当前活跃连接数
- 已连接用户信息

## 项目结构

```
vpnmgr/
├── vpnmgr/
│   ├── main.py              # FastAPI 主应用
│   ├── config.py            # 配置管理
│   ├── schemas.py           # Pydantic 模型
│   ├── models/              # 数据库模型
│   │   ├── database.py
│   │   ├── vpn_user.py
│   │   └── ikev2_cert.py
│   ├── utils/               # 工具模块
│   │   ├── vpn_manager.py   # Docker 容器管理
│   │   └── auth.py          # 认证工具
│   ├── templates/           # HTML 模板
│   └── static/              # 静态文件
│       ├── css/
│       └── js/
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── start.py
└── README.md
```

## 与 VPN 容器通信

本管理面板通过 Docker API 与 `hwdsl2/ipsec-vpn-server` 容器通信，执行以下操作：

- 添加/删除 VPN 用户（通过 `useradd`/`userdel` 或 `chpasswd`）
- 生成 IKEv2 证书（通过 `ikev2.sh` 脚本）
- 获取连接状态（通过 `ipsec whack --trafficstatus`）
- 获取容器日志

**注意**：如果 VPN 容器名称不是默认的 `ipsec-vpn-server`，请在 `.env` 中修改 `VPN_CONTAINER_NAME`。

## 安全建议

1. **修改默认密码** - 部署后立即修改 `ADMIN_PASSWORD`
2. **更换密钥** - 修改 `SECRET_KEY` 为一个随机字符串
3. **使用 HTTPS** - 生产环境建议使用 HTTPS 反向代理
4. **限制访问** - 通过防火墙限制管理面板访问IP

## 反向代理配置 (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name vpnmgr.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
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

## 故障排除

### 无法连接到 Docker 容器

确保 VPN Manager 有权限访问 Docker：
```bash
# 如果使用 docker-compose，确保挂载了 docker.sock
-v /var/run/docker.sock:/var/run/docker.sock:ro

# 或者直接运行，确保用户在 docker 组
sudo usermod -aG docker $USER
```

### 添加用户失败

检查 VPN 容器是否运行：
```bash
docker ps | grep ipsec-vpn-server
docker logs ipsec-vpn-server
```

### WebSocket 连接失败

如果使用反向代理，确保配置了 WebSocket 支持（见上方 Nginx 配置）。

## 技术栈

- **Backend**: FastAPI, SQLAlchemy, Docker SDK
- **Frontend**: Vanilla JS, CSS3, Font Awesome
- **Database**: SQLite (async via aiosqlite)
- **Real-time**: WebSocket

## License

MIT License
