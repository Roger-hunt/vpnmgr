#!/bin/bash
# Nodogsplash 测试脚本 - 方案一：在 VPN 容器内运行
# 用于 IPsec VPN 的 Captive Portal

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VPN_CONTAINER="ipsec-vpn-server"
VPN_SUBNET="192.168.43.0/24"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Nodogsplash for IPsec VPN 测试脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 VPN 容器是否运行
if ! docker ps --format "{{.Names}}" | grep -q "^${VPN_CONTAINER}$"; then
    echo -e "${RED}❌ VPN 容器 ${VPN_CONTAINER} 未运行${NC}"
    echo "请先启动 VPN 容器"
    exit 1
fi
echo -e "${GREEN}✓ VPN 容器正在运行${NC}"

# 获取 VPN 容器 IP
VPN_IP=$(docker inspect $VPN_CONTAINER --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
echo -e "${BLUE}  VPN 容器 IP: ${VPN_IP}${NC}"

# 步骤 1: 更新容器并安装依赖
echo ""
echo -e "${YELLOW}[1/5] 安装 nodogsplash...${NC}"

# 检测容器 OS 类型并安装
OS_TYPE=$(docker exec $VPN_CONTAINER sh -c 'if [ -f /etc/alpine-release ]; then echo alpine; elif [ -f /etc/debian_version ]; then echo debian; else echo unknown; fi')

if [ "$OS_TYPE" = "alpine" ]; then
    echo -e "${BLUE}  检测到 Alpine Linux，从源码编译安装...${NC}"
    docker exec $VPN_CONTAINER sh -c "
        apk update
        apk add --no-cache gcc musl-dev make linux-headers iptables libmicrohttpd-dev git json-c-dev
        
        # 从源码编译 nodogsplash (使用最新 master 分支以兼容新 libmicrohttpd)
        cd /tmp
        git clone --depth 1 https://github.com/nodogsplash/nodogsplash.git
        cd nodogsplash
        
        # 修复 libmicrohttpd 兼容性问题
        sed -i 's/int libmicrohttpd_cb/enum MHD_Result libmicrohttpd_cb/' src/http_microhttpd.h
        sed -i 's/int libmicrohttpd_cb/enum MHD_Result libmicrohttpd_cb/' src/http_microhttpd.c
        sed -i 's/static int send_error/static enum MHD_Result send_error/' src/http_microhttpd.c
        sed -i 's/static int show_splash/static enum MHD_Result show_splash/' src/http_microhttpd.c
        sed -i 's/static int show_status/static enum MHD_Result show_status/' src/http_microhttpd.c
        sed -i 's/static int authenticate_client/static enum MHD_Result authenticate_client/' src/http_microhttpd.c
        sed -i 's/static int encode_and_redirect/static enum MHD_Result encode_and_redirect/' src/http_microhttpd.c
        sed -i 's/static int redirect_to_splash/static enum MHD_Result redirect_to_splash/' src/http_microhttpd.c
        
        make
        make install
        
        # 创建必要的目录
        mkdir -p /etc/nodogsplash/htdocs/images
        mkdir -p /var/log/nodogsplash
        
        # 清理
        cd /
        rm -rf /tmp/nodogsplash
    " || {
        echo -e "${RED}❌ Alpine 安装失败${NC}"
        exit 1
    }
elif [ "$OS_TYPE" = "debian" ]; then
    echo -e "${BLUE}  检测到 Debian/Ubuntu，使用 apt 安装...${NC}"
    docker exec $VPN_CONTAINER bash -c "
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq nodogsplash iptables-persistent
        mkdir -p /etc/nodogsplash/htdocs/images
        mkdir -p /var/log/nodogsplash
    " || {
        echo -e "${RED}❌ Debian 安装失败${NC}"
        exit 1
    }
else
    echo -e "${RED}❌ 不支持的容器操作系统${NC}"
    exit 1
fi

echo -e "${GREEN}✓ nodogsplash 安装完成${NC}"

# 步骤 2: 复制配置文件
echo ""
echo -e "${YELLOW}[2/5] 配置 nodogsplash...${NC}"

# 创建配置文件
docker exec $VPN_CONTAINER bash -c "cat > /etc/nodogsplash/nodogsplash.conf << 'EOFNODOG'
# Nodogsplash Configuration for IPsec VPN
# 自动生成的配置文件

# 网关接口 - VPN 内部接口 eth0
GatewayInterface eth0

# 网关地址
GatewayAddress 192.168.43.1

# Web服务器配置
GatewayPort 2050
WebRoot /etc/nodogsplash/htdocs

# 验证页面设置
# 自动重定向到欢迎页面
RedirectURL http://192.168.43.1:8080/

# 调试模式（测试时开启）
DebugLevel 3
SyslogFacility 0

# 防火墙规则集
FirewallRuleSet authenticated-users {
    FirewallRule allow all
}

# 未认证用户允许访问（白名单）
FirewallRuleSet preauthenticated-users {
    # 允许访问 VPN Manager
    FirewallRule allow tcp port 8080 to 192.168.43.1
    
    # 允许 HTTP/HTTPS 访问网关
    FirewallRule allow tcp port 80
    FirewallRule allow tcp port 443
    FirewallRule allow tcp port 2050
    
    # 允许 DNS
    FirewallRule allow udp port 53
    FirewallRule allow tcp port 53
    
    # 允许 Ping
    FirewallRule allow icmp
}

# 客户端到路由器的规则
FirewallRuleSet users-to-router {
    FirewallRule allow tcp port 80
    FirewallRule allow tcp port 443
    FirewallRule allow tcp port 2050
    FirewallRule allow tcp port 8080
    FirewallRule allow tcp port 22
    FirewallRule allow udp port 53
}
EOFNODOG
"

# 步骤 3: 创建 Splash 页面
echo ""
echo -e "${YELLOW}[3/5] 创建 Captive Portal 页面...${NC}"

# 创建现代的 splash 页面
docker exec $VPN_CONTAINER bash -c "cat > /etc/nodogsplash/htdocs/splash.html << 'EOFSPLASH'
<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no\">
    <meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\">
    <meta http-equiv=\"Pragma\" content=\"no-cache\">
    <meta http-equiv=\"Expires\" content=\"0\">
    <title>VPN 连接成功 - VPN Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            color: #e8e8e8;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            -webkit-font-smoothing: antialiased;
        }
        
        .card {
            background: rgba(26, 26, 46, 0.95);
            border-radius: 24px;
            padding: 48px 32px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(10px);
        }
        
        .icon {
            width: 90px;
            height: 90px;
            background: linear-gradient(135deg, rgba(76, 175, 80, 0.2), rgba(76, 175, 80, 0.1));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 28px;
            color: #5dd35d;
            font-size: 44px;
            animation: pulse 2s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.4); }
            50% { transform: scale(1.02); box-shadow: 0 0 0 15px rgba(76, 175, 80, 0); }
        }
        
        h1 {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 12px;
            color: #ffffff;
        }
        
        .subtitle {
            color: #a0a0b0;
            margin-bottom: 32px;
            line-height: 1.6;
        }
        
        .info-box {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 28px;
            text-align: left;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            font-size: 0.9375rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }
        
        .info-row:last-child {
            border-bottom: none;
        }
        
        .info-label {
            color: #9090a0;
        }
        
        .info-value {
            color: #5dd35d;
            font-family: monospace;
        }
        
        .btn {
            width: 100%;
            background: linear-gradient(135deg, #4caf50, #43a047);
            color: white;
            padding: 16px 32px;
            border-radius: 14px;
            border: none;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
        }
        
        .footer {
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            color: #666;
            font-size: 0.8125rem;
        }
        
        .loading {
            display: none;
            margin-top: 20px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class=\"card\">
        <div class=\"icon\">✓</div>
        
        <h1>连接成功</h1>
        <p class=\"subtitle\">您已成功连接到 VPN</p>
        
        <div class=\"info-box\">
            <div class=\"info-row\">
                <span class=\"info-label\">状态</span>
                <span class=\"info-value\">已安全连接</span>
            </div>
            <div class=\"info-row\">
                <span class=\"info-label\">您的 IP</span>
                <span class=\"info-value\" id=\"client-ip\">获取中...</span>
            </div>
            <div class=\"info-row\">
                <span class=\"info-label\">网络</span>
                <span class=\"info-value\">VPN Network</span>
            </div>
        </div>
        
        <form method=\"get\" action=\"\$authaction\">
            <input type=\"hidden\" name=\"tok\" value=\"\$tok\">
            <input type=\"hidden\" name=\"redir\" value=\"http://www.baidu.com\">
            <button type=\"submit\" class=\"btn\" onclick=\"showLoading()\">
                点击继续上网
            </button>
        </form>
        
        <div class=\"loading\" id=\"loading\">
            正在跳转...
        </div>
        
        <div class=\"footer\">
            VPN Manager &copy; 2026<br>
            <small>安全 · 稳定 · 快速</small>
        </div>
    </div>
    
    <script>
        // 显示客户端 IP
        fetch('/nodogsplash_ajax.php')
            .then(r => r.json())
            .then(data => {
                document.getElementById('client-ip').textContent = data.ip || '未知';
            })
            .catch(() => {
                document.getElementById('client-ip').textContent = '\$clientip' || '192.168.43.x';
            });
        
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
        }
    </script>
</body>
</html>
EOFSPLASH
"

# 创建简单的状态页面
docker exec $VPN_CONTAINER bash -c "cat > /etc/nodogsplash/htdocs/status.html << 'EOFSTATUS'
<!DOCTYPE html>
<html>
<head>
    <meta charset=\"UTF-8\">
    <title>Status</title>
</head>
<body>
    <h1>Authenticated</h1>
    <p>You are now connected to the internet.</p>
</body>
</html>
EOFSTATUS
"

echo -e "${GREEN}✓ Captive Portal 页面创建完成${NC}"

# 步骤 4: 配置 iptables 规则
echo ""
echo -e "${YELLOW}[4/5] 配置防火墙规则...${NC}"

# 在容器内配置 iptables 规则
docker exec $VPN_CONTAINER bash -c "
    # 清除可能存在的旧规则
    iptables -t nat -F ndsOUT 2>/dev/null || true
    iptables -t filter -F ndsNET 2>/dev/null || true
    
    # 允许 nodogsplash 端口
    iptables -I INPUT -p tcp --dport 2050 -j ACCEPT 2>/dev/null || true
    iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
    
    # 允许从 VPN 子网访问
    iptables -I INPUT -s ${VPN_SUBNET} -j ACCEPT 2>/dev/null || true
    iptables -t nat -I PREROUTING -s ${VPN_SUBNET} -j ACCEPT 2>/dev/null || true
"

echo -e "${GREEN}✓ 防火墙规则配置完成${NC}"

# 步骤 5: 启动 nodogsplash
echo ""
echo -e "${YELLOW}[5/5] 启动 nodogsplash...${NC}"

# 先停止可能存在的旧进程
docker exec $VPN_CONTAINER bash -c "
    pkill nodogsplash 2>/dev/null || true
    sleep 1
"

# 启动 nodogsplash
docker exec -d $VPN_CONTAINER bash -c "
    nodogsplash -c /etc/nodogsplash/nodogsplash.conf -d 3 -f > /var/log/nodogsplash/nodogsplash.log 2>&1
"

# 等待启动
sleep 2

# 检查是否运行
if docker exec $VPN_CONTAINER pgrep nodogsplash > /dev/null; then
    echo -e "${GREEN}✓ nodogsplash 启动成功${NC}"
    NDS_PID=$(docker exec $VPN_CONTAINER pgrep nodogsplash)
    echo -e "${BLUE}  进程 PID: ${NDS_PID}${NC}"
else
    echo -e "${RED}❌ nodogsplash 启动失败${NC}"
    echo -e "${YELLOW}查看日志:${NC}"
    docker exec $VPN_CONTAINER cat /var/log/nodogsplash/nodogsplash.log 2>/dev/null || echo "日志文件未创建"
    exit 1
fi

# 显示状态
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Nodogsplash 测试环境部署完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}配置信息:${NC}"
echo "  • VPN 容器: ${VPN_CONTAINER}"
echo "  • VPN 子网: ${VPN_SUBNET}"
echo "  • Gateway Interface: eth0"
echo "  • Captive Portal 端口: 2050"
echo ""
echo -e "${BLUE}测试步骤:${NC}"
echo "  1. 使用 VPN 客户端连接"
echo "  2. 打开浏览器访问任意 HTTP 网站"
echo "  3. 应该会看到 Captive Portal 页面"
echo "  4. 点击'点击继续上网'按钮"
echo "  5. 之后应该可以正常访问互联网"
echo ""
echo -e "${BLUE}管理命令:${NC}"
echo "  查看日志:  docker exec ${VPN_CONTAINER} tail -f /var/log/nodogsplash/nodogsplash.log"
echo "  查看状态:  docker exec ${VPN_CONTAINER} ndsctl status"
echo "  停止服务:  ${SCRIPT_DIR}/stop.sh"
echo "  完全卸载:  ${SCRIPT_DIR}/uninstall.sh"
echo ""
echo -e "${YELLOW}注意: 容器重启后需要重新运行此脚本${NC}"
echo ""
