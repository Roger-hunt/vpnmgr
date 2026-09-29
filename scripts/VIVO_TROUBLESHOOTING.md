# vivo 手机 Captive Portal 排查指南

## 问题描述
vivo 手机连接 VPN 后没有自动弹出 captive portal 页面。

## 可能原因

### 1. DNS 劫持未生效
vivo 手机使用的 captive portal 检测域名没有被正确劫持到 VPN Manager 服务器。

**vivo 使用的检测域名：**
- `wifi.vivo.com.cn/generate_204`
- `devel.vivo.com.cn/generate_204`

### 2. vivo 手机网络检测设置
部分 vivo 手机可能使用了自定义的网络检测设置，或者关闭了 captive portal 检测。

### 3. 缓存问题
手机可能已经缓存了网络检测结果，认为当前网络可以访问互联网。

---

## 排查步骤

### 步骤 1: 检查 DNS 劫持是否生效

在 VPN 连接的设备上（或在 VPN 服务器上），测试 DNS 解析：

```bash
# 测试 vivo 的检测域名
nslookup wifi.vivo.com.cn
nslookup devel.vivo.com.cn
```

**预期结果：** 应该解析到 VPN Manager 服务器的 IP（如 172.17.0.1）

**如果解析到其他 IP（如 114.114.114.114 等）：** DNS 劫持未生效

### 步骤 2: 检查请求是否到达后端

1. 在 VPN Manager 服务器上查看日志：
```bash
cd /path/to/vpnmgr
tail -f logs/vpnmgr.log 2>/dev/null || echo "查看日志文件"
```

2. 或者访问调试 API：
```bash
# 登录后访问
curl -H "Cookie: session=YOUR_SESSION" http://localhost:8080/api/debug/captive-requests
```

**预期结果：** 应该看到来自 vivo 手机的 `/generate_204` 请求

### 步骤 3: 手动测试检测 URL

在 vivo 手机上打开浏览器，访问：
```
http://wifi.vivo.com.cn/generate_204
```

**预期结果：**
- 未认证时：应该显示 captive portal 页面
- 已认证时：应该返回空白页面（204）

### 步骤 4: 检查 vivo 手机网络设置

1. 进入 vivo 手机 **设置** → **WLAN**
2. 点击已连接的 WiFi 名称
3. 查看是否有 **"网络检测"** 或 **"Captive Portal"** 相关选项

**注意：** 部分 vivo 手机可能需要在开发者选项中调整。

---

## 解决方案

### 方案 1: 重启 dnsmasq 服务

```bash
sudo systemctl restart dnsmasq
sudo systemctl status dnsmasq
```

### 方案 2: 手动添加 iptables 规则

确保 VPN 子网的 DNS 请求被劫持：

```bash
# 清除旧规则
sudo iptables -t nat -D PREROUTING -s 192.168.43.0/24 -p udp --dport 53 -j DNAT --to-destination 172.17.0.1:53 2>/dev/null || true
sudo iptables -t nat -D PREROUTING -s 192.168.43.0/24 -p tcp --dport 53 -j DNAT --to-destination 172.17.0.1:53 2>/dev/null || true

# 添加新规则
sudo iptables -t nat -A PREROUTING -s 192.168.43.0/24 -p udp --dport 53 -j DNAT --to-destination 172.17.0.1:53
sudo iptables -t nat -A PREROUTING -s 192.168.43.0/24 -p tcp --dport 53 -j DNAT --to-destination 172.17.0.1:53
```

### 方案 3: 清除 vivo 手机缓存

1. 断开 VPN 连接
2. 进入 vivo 手机 **设置** → **应用管理** → **显示系统进程**
3. 找到 **"网络"** 或 **"Captive Portal"** 相关应用
4. 清除缓存
5. 重新连接 VPN

### 方案 4: 手动修改 vivo 手机检测 URL

如果 vivo 手机支持 adb：

```bash
# 连接手机
adb shell

# 修改 captive portal 检测 URL
settings put global captive_portal_http_url http://wifi.vivo.com.cn/generate_204
settings put global captive_portal_https_url https://wifi.vivo.com.cn/generate_204

# 启用 captive portal 检测
settings put global captive_portal_mode 1

# 重启手机
reboot
```

### 方案 5: 使用完整的 DNS 劫持方案

如果标准方案无效，可以尝试完整 DNS 劫持（所有域名都劫持）：

```bash
cd /path/to/vpnmgr
sudo bash scripts/setup_dns_hijack.sh
```

**注意：** 此方案会劫持所有网站，请谨慎使用。

---

## 验证方法

### 方法 1: 使用浏览器测试
在 vivo 手机上：
1. 断开 VPN
2. 打开浏览器
3. 访问 `http://neverssl.com`
4. 连接 VPN
5. 再次访问 `http://neverssl.com`

**应该显示 captive portal 页面**

### 方法 2: 查看后端日志
```bash
cd /path/to/vpnmgr
python -c "
from vpnmgr.main import _captive_requests_log
print('Recent captive portal requests:')
for req in _captive_requests_log[-20:]:
    print(f\"  {req['timestamp']} - {req['source']} - {req['client_ip']} - {req['path']} - {req['response_type']}\")
"
```

---

## 常见问题

### Q: vivo 手机显示 "网络连接受限" 但不弹出 portal
**A:** 这是预期的行为， captive portal 即将弹出。等待几秒或下拉通知栏查看。

### Q: 其他品牌手机正常，只有 vivo 不行
**A:** vivo 可能使用了不同的检测机制。尝试使用完整 DNS 劫持方案，或手动修改 vivo 的 captive portal URL。

### Q: vivo 手机弹出后又立即关闭
**A:** 可能是响应时间太长导致超时。检查 VPN Manager 服务器负载，或尝试在 captive.html 中添加自动重定向延迟。

---

## 需要的信息

如果以上方法都无效，请收集以下信息提交 issue：

1. vivo 手机型号和系统版本
2. `nslookup wifi.vivo.com.cn` 的结果
3. VPN Manager 的 captive portal 请求日志 (`/api/debug/captive-requests`)
4. vivo 手机浏览器访问 `http://wifi.vivo.com.cn/generate_204` 的结果（截图）
