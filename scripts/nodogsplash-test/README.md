# Nodogsplash 测试方案（方案一）

在 IPsec VPN 容器内运行 nodogsplash，为 VPN 客户端提供 Captive Portal 功能。

## 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│                    VPN 容器 (ipsec-vpn-server)               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Nodogsplash (端口 2050)                 │    │
│  │  ┌───────────────────────────────────────────────┐  │    │
│  │  │  1. 拦截 HTTP 请求                              │  │    │
│  │  │  2. 重定向到 Splash 页面                        │  │    │
│  │  │  3. 用户点击"继续"后放行                         │  │    │
│  │  └───────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                 │
│  ┌────────────────────────┼─────────────────────────────┐   │
│  │  VPN 客户端子网        │  192.168.43.0/24            │   │
│  │  (手机/电脑设备)       │                             │   │
│  └────────────────────────┴─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装并启动

```bash
cd scripts/nodogsplash-test
chmod +x install-and-start.sh
sudo ./install-and-start.sh
```

### 2. 测试

1. **连接 VPN**：使用 IKEv2/IPsec 连接 VPN
2. **触发 Captive Portal**：
   - 打开浏览器
   - 访问任意 HTTP 网站（如 http://example.com）
   - 或者等待系统自动检测
3. **完成认证**：点击"点击继续上网"按钮
4. **正常上网**：之后可以访问所有网站

### 3. 管理命令

```bash
# 查看状态
./status.sh

# 停止服务
./stop.sh

# 完全卸载
./uninstall.sh

# 查看实时日志
docker exec ipsec-vpn-server tail -f /var/log/nodogsplash/nodogsplash.log

# 查看 ndsctl 详细状态
docker exec ipsec-vpn-server ndsctl status

# 手动重启
docker exec ipsec-vpn-server pkill nodogsplash
docker exec -d ipsec-vpn-server nodogsplash -c /etc/nodogsplash/nodogsplash.conf -f
```

## 已知问题与限制

### 1. 容器重启后失效
- **问题**：VPN 容器重启后，nodogsplash 需要重新安装
- **解决**：考虑创建自定义镜像或挂载持久化卷

### 2. 无 MAC 地址
- **问题**：IPsec VPN 没有真实的二层 MAC 地址
- **影响**：MAC 白名单功能无法使用
- **解决**：使用 IP 地址管理会话

### 3. HTTPS 限制
- **问题**：Captive Portal 只能劫持 HTTP 流量
- **影响**：访问 HTTPS 网站时会显示证书错误
- **解决**：这是 Captive Portal 的普遍限制，现代浏览器/系统会自动处理

### 4. 国产手机的特殊处理

部分国产手机（Vivo、OPPO、小米、华为）有自己的 Captive Portal 检测机制，可能需要额外配置：

```bash
# 在 VPN 容器内添加额外的 DNS 劫持
docker exec ipsec-vpn-server bash -c "
    # 安装 dnsmasq（如果未安装）
    apt-get install -y dnsmasq
    
    # 配置 DNS 劫持
    echo 'address=/wifi.vivo.com.cn/192.168.43.1' >> /etc/dnsmasq.conf
    echo 'address=/conn1.oppomobile.com/192.168.43.1' >> /etc/dnsmasq.conf
    echo 'address=/connect.rom.miui.com/192.168.43.1' >> /etc/dnsmasq.conf
    
    # 重启 dnsmasq
    service dnsmasq restart
"
```

## 配置说明

### 配置文件路径
- **主配置**：`/etc/nodogsplash/nodogsplash.conf`
- **Splash 页面**：`/etc/nodogsplash/htdocs/splash.html`
- **日志**：`/var/log/nodogsplash/nodogsplash.log`

### 关键配置项

```conf
# 会话超时设置
IdleTimeout 1800          # 空闲 30 分钟后断开
ForceTimeout 86400        # 最大 24 小时会话

# 最大客户端数
MaxClients 100

# 调试级别（0-7，数字越大越详细）
DebugLevel 3
```

## 调试技巧

### 查看实时日志
```bash
docker exec ipsec-vpn-server tail -f /var/log/nodogsplash/nodogsplash.log
```

### 检查 iptables 规则
```bash
# NAT 表
docker exec ipsec-vpn-server iptables -t nat -L -n -v

# Filter 表  
docker exec ipsec-vpn-server iptables -L -n -v
```

### 手动测试重定向
```bash
# 从 VPN 客户端执行
curl -I http://example.com
# 应该返回 302 重定向到 captive portal
```

## 与之前 Python 方案的对比

| 特性 | Python 方案 | Nodogsplash 方案 |
|------|------------|-----------------|
| 实现层级 | 应用层 (HTTP) | 网络层 (iptables) |
| 依赖 | DNS 劫持 | 直接拦截 HTTP |
| 稳定性 | 依赖 DNS 配置 | 更稳定 |
| 容器重启 | 配置持久 | 需要重新安装 |
| 维护成本 | 自建代码 | 成熟开源项目 |

## 下一步

如果此方案测试成功，可以：
1. 创建自定义 VPN 镜像（内置 nodogsplash）
2. 添加更多品牌的 Captive Portal 检测支持
3. 集成到 VPN Manager Web 界面进行管理
