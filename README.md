# VPN Manager

一个基于 Web 的 docker-ipsec-vpn-server 管理面板，支持用户管理、IKEv2 证书全生命周期管理（生成、下载、注销）和实时状态监控。

<p align="right">
  <b>简体中文</b> | <a href="./README.en.md">English</a>
</p>

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![Docker](https://img.shields.io/badge/Docker-compatible-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 功能特性

- 🔐 **用户管理** - 添加、删除、修改 VPN 用户密码及配额
- 📜 **证书管理** - 生成、下载及彻底注销 IKEv2 证书 (.p12, .mobileconfig, .sswan)
- 🌐 **多语言支持** - 内置中英文一键无缝即时切换 (English / 简体中文)
- 📊 **实时监控** - WebSocket 毫秒级展示活跃连接、流量与容器健康状态
- 📝 **日志查看** - 实时查看与追踪 VPN 容器运行日志
- 🔒 **安全认证** - JWT + Session 双重会话鉴权
- 📱 **响应式设计** - 移动端自适应，UI 现代大气
- 🗄️ **持久化存储** - SQLite 数据库规范归档于 `./data/vpnmgr.db`，支持数据卷持久化

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

证书管理已整合进「用户管理」页面，每个用户对应唯一的 VPN 身份。

1. 进入"用户管理"页面，新增用户或点击已有用户的编辑按钮
2. 在「IKEv2 证书」区块填入证书名称（可点「自动生成」）
3. 按需勾选「使用导入密码保护配置文件」并设置密码（留空则自动生成）
4. 点击"生成新证书"，下载 .p12 文件并安装到设备
5. 区块内会显示该证书的有效期与剩余天数

> 开启导入密码保护后，导出的 .p12 / .mobileconfig / .sswan 都需要密码才能导入。
> 密码在生成时展示一次，请立即保存；后续下载会再次回显。

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
├── data/                    # 数据库持久化存储目录
│   ├── .gitkeep
│   └── vpnmgr.db            # SQLite 数据库
├── vpnmgr/                  # 核心应用包
│   ├── main.py              # FastAPI 核心服务与 API 路由
│   ├── config.py            # 应用设置与环境变量加载
│   ├── schemas.py           # Pydantic 数据验证模型
│   ├── models/              # SQLAlchemy 数据库模型
│   │   ├── database.py      # 异步数据库引擎与自动平滑迁移
│   │   ├── vpn_user.py      # VPN 账号模型
│   │   ├── ikev2_cert.py    # IKEv2 证书模型
│   │   └── system_user.py   # 管理员用户模型
│   ├── utils/               # 工具模块
│   │   ├── vpn_manager.py   # Docker 与 strongSwan 命令交互
│   │   └── auth.py          # 密码哈希与 JWT 认证
│   ├── templates/           # Jinja2 HTML 模板
│   └── static/              # 静态资源
│       ├── css/             # 样式文件 (modern.css / style.css)
│       └── js/
│           ├── app.js       # 控制台交互与 WebSocket 客户端
│           └── i18n.js      # 中英文多语言字典
├── scripts/                 # 网络配置与运维脚本
├── requirements.txt         # Python 依赖
├── docker-compose.yml       # Docker 编排配置
├── Dockerfile               # 容器构建镜像定义
├── ecosystem.config.js      # PM2 生产进程管理配置
├── start.py                 # 应用启动入口
├── README.md                # 中文文档
└── README.en.md             # 英文文档
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
