# VPN Captive Portal 配置脚本

用于实现 VPN 连接后的 Captive Portal（强制门户）功能，让 VPN 客户端连接后自动弹出连接成功页面。

## 文件说明

| 文件 | 说明 |
|------|------|
| `backup/backup_vpn_config.sh` | 备份当前配置 |
| `setup_captive_portal.sh` | 标准 Captive Portal 配置（推荐） |
| `setup_dns_hijack.sh` | 完整 DNS 劫持配置（激进方案） |
| `rollback_dns_hijack.sh` | 回退配置 |

## 两种配置方案对比

### 方案一：标准 Captive Portal（推荐）

**特点：**
- 只劫持 Captive Portal 检测域名
- 不影响正常上网
- 各种设备兼容性更好

**适用场景：**
- 大多数用户使用
- 需要正常访问互联网

### 方案二：完整 DNS 劫持（激进方案）

**特点：**
- 劫持所有 DNS 请求
- 所有 HTTP 请求都显示 welcome 页面
- 需要点击按钮后才能正常上网

**适用场景：**
- 需要强制用户查看欢迎页面
- 内部网络环境

## 使用方法

### 标准 Captive Portal 配置（推荐）

```bash
cd /path/to/vpnmgr
sudo bash scripts/setup_captive_portal.sh
```

此脚本会：
- 安装并配置 dnsmasq
- 只劫持 Captive Portal 检测域名到本机
- 配置 VPN 客户端使用新的 DNS
- 保持正常上网功能

**支持的检测域名：**
- **iOS/macOS**: `captive.apple.com`, `www.apple.com`, `www.ibook.info` 等
- **Android**: `connectivitycheck.gstatic.com`, `connectivitycheck.android.com`, `clients3.google.com` 等
- **Windows**: `www.msftconnecttest.com`, `msftconnecttest.com`, `dns.msftncsi.com` 等
- **Firefox**: `detectportal.firefox.com`, `captive.mozilla.org`
- **国内厂商**: `wifi.vivo.com.cn`, `wifi.cmcc`

### 完整 DNS 劫持配置

```bash
cd /path/to/vpnmgr
sudo bash scripts/setup_dns_hijack.sh
```

此脚本会：
- 安装并配置 dnsmasq
- 将所有 DNS 请求劫持到本机
- 将所有 HTTP 请求重定向到 welcome 页面
- 配置 VPN 客户端使用新的 DNS

**注意：** 此方案下访问 HTTPS 网站会出现证书警告

### 回退配置

```bash
# 方法1：使用自动创建的备份
sudo bash scripts/rollback_dns_hijack.sh

# 方法2：指定备份目录
sudo bash scripts/rollback_dns_hijack.sh scripts/backup/backup_20260323_120000
```

## 工作原理

### 标准 Captive Portal (Session-based)

```
VPN 客户端连接
    ↓
系统发送 Captive Portal 检测请求
    ↓
DNS 劫持 → 检测域名解析到 172.17.0.1
    ↓
请求 /hotspot-detect.html (iOS) 或 /generate_204 (Android)
    ↓
返回 captive.html 页面
    ↓
显示连接成功弹窗
    ↓
用户点击"完成"
    ↓
记录会话认证状态（当前连接期间不再显示）
    ↓
返回 204/Success 响应， captive portal 关闭
    ↓
正常上网
```

**Session-based 特性：**
- 每个 VPN 连接会话只显示一次 captive portal
- 用户点击"完成"后，当前连接期间不再显示
- VPN 断开后，下次连接重新显示
- 1 小时无活动自动清除认证状态

### 完整 DNS 劫持

```
VPN 客户端连接
    ↓
连接 VPN (192.168.43.x)
    ↓
DNS 查询 → 被劫持到 172.17.0.1:53
    ↓
所有域名解析到 172.17.0.1
    ↓
HTTP 请求 → 被重定向到 172.17.0.1:8080
    ↓
显示 Welcome 页面
    ↓
点击"访问百度测试"后正常上网
```

## 后端 API 端点

应用提供了以下 API 端点支持 Captive Portal 功能：

### 检测端点（各系统自动调用）

| 端点 | 用途 | 支持系统 |
|------|------|---------|
| `/hotspot-detect.html` | Captive Portal 检测 | iOS, macOS |
| `/generate_204` | Captive Portal 检测 | Android |
| `/gen_204` | Captive Portal 检测 | 部分 Android |
| `/connecttest.txt` | 网络连接测试 | Windows |
| `/ncsi.txt` | 网络状态指示器 | Windows |
| `/success.txt` | 门户检测 | Firefox |
| `/captive.apple.com/hotspot-detect.html` | 完整路径检测 | iOS, macOS |
| `/library/test/success.html` | 旧版检测 | iOS, macOS |
| `/mobile/status.php` | 应用检测 | Facebook App |
| `/fwlink/` | Windows 重定向 | Windows |

### API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/captive/status` | 获取当前客户端的 captive portal 状态 |
| `GET /api/captive/session-status` | 获取当前会话的认证状态（是否已点击完成） |
| `POST /api/captive/complete` | 标记当前会话已完成 captive portal（点击完成按钮时调用） |
| `GET /api/captive/detect-urls` | 获取所有支持的检测 URL 列表 |

### Session-based 认证流程

```
1. VPN 客户端连接
   → DNS 劫持触发 captive portal 检测
   → 返回 captive.html 页面

2. 用户点击"完成"按钮
   → JavaScript 调用 POST /api/captive/complete
   → 后端记录该 IP 已认证
   → 关闭 captive portal 窗口

3. 后续检测请求（同一会话）
   → 检查 IP 是否已认证
   → 已认证：返回 204/Success（不再显示 portal）
   → 未认证：继续显示 captive.html

4. VPN 断开
   → 自动清除该 IP 的认证状态
   → 下次连接重新显示 captive portal
```

### 示例 API 响应

```bash
# 获取 captive portal 状态
curl http://localhost:8080/api/captive/status
```

响应：
```json
{
  "success": true,
  "data": {
    "is_vpn_client": true,
    "client_ip": "192.168.43.10",
    "captive_portal_enabled": true,
    "auto_close": false,
    "auto_close_delay": 10,
    "user": {
      "bound_username": "zhangsan",
      "cert_name": "iPhone-ZhangSan",
      "connection_info": {...}
    }
  }
}
```

## 配置选项

在 `.env` 文件中可以配置以下选项：

```env
# Captive Portal Settings
# Enable captive portal detection pages
CAPTIVE_PORTAL_ENABLED=true

# Auto-close captive portal window after connection
CAPTIVE_PORTAL_AUTO_CLOSE=false

# Auto-close delay in seconds
CAPTIVE_PORTAL_AUTO_CLOSE_DELAY=10

# VPN subnet for identifying VPN clients
VPN_SUBNET=192.168.43.0/24
```

## 注意事项

1. **VPN 客户端需要重新连接** - 配置完成后，VPN 客户端需要断开再重新连接才能生效

2. **HTTPS 网站证书警告**（仅完整 DNS 劫持方案）- 这是正常的，因为 DNS 解析的 IP 和证书不匹配

3. **iOS 弹窗** - 标准 Captive Portal 方案在 iOS 上会显示系统弹窗，这是预期的行为

4. **Android 兼容性** - 部分国产 Android 系统可能需要额外的配置

## 故障排除

### 检查 DNS 是否工作

```bash
# 从 VPN 客户端测试 DNS 解析
nslookup captive.apple.com
nslookup google.com
```

### 检查 dnsmasq 状态

```bash
sudo systemctl status dnsmasq
sudo journalctl -u dnsmasq -n 50
```

### 检查 iptables 规则

```bash
sudo iptables -t nat -L PREROUTING -n -v
```

### 测试 Captive Portal 端点

```bash
# 从 VPN 客户端测试
curl -I http://captive.apple.com/hotspot-detect.html
curl -I http://connectivitycheck.gstatic.com/generate_204
```

## 手动排除特定域名（标准方案）

编辑 `/etc/dnsmasq.d/vpn-captive.conf`，在文件末尾添加：

```
# 允许这些域名正常解析
server=/example.com/8.8.8.8
server=/api.example.com/8.8.8.8
```

然后重启 dnsmasq：

```bash
sudo systemctl restart dnsmasq
```
