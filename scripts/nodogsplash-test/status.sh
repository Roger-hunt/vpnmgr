#!/bin/bash
# 查看 nodogsplash 状态

VPN_CONTAINER="ipsec-vpn-server"

if ! docker ps --format "{{.Names}}" | grep -q "^${VPN_CONTAINER}$"; then
    echo "❌ VPN 容器未运行"
    exit 1
fi

echo "========================================"
echo "  Nodogsplash 状态检查"
echo "========================================"
echo ""

# 检查进程
if docker exec $VPN_CONTAINER pgrep nodogsplash > /dev/null; then
    NDS_PID=$(docker exec $VPN_CONTAINER pgrep nodogsplash)
    echo "✓ nodogsplash 运行中 (PID: $NDS_PID)"
else
    echo "✗ nodogsplash 未运行"
fi
echo ""

# 查看 ndsctl 状态
echo "--- ndsctl 状态 ---"
docker exec $VPN_CONTAINER ndsctl status 2>/dev/null || echo "无法获取状态"
echo ""

# 查看最近的日志
echo "--- 最近日志 ---"
docker exec $VPN_CONTAINER tail -n 30 /var/log/nodogsplash/nodogsplash.log 2>/dev/null || echo "日志文件不存在"
echo ""

# 查看 iptables 规则
echo "--- 相关 iptables 规则 ---"
docker exec $VPN_CONTAINER bash -c "
    echo 'NAT 表 PREROUTING:'
    iptables -t nat -L PREROUTING -n -v --line-numbers 2>/dev/null | grep -E '(nds|2050|8080)' || echo '无相关规则'
    echo ''
    echo 'Filter 表 INPUT:'
    iptables -L INPUT -n -v --line-numbers 2>/dev/null | grep -E '(nds|2050|8080|192.168.43)' || echo '无相关规则'
"
echo ""
