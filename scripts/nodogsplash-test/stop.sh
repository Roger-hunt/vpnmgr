#!/bin/bash
# 停止 nodogsplash

VPN_CONTAINER="ipsec-vpn-server"

if ! docker ps --format "{{.Names}}" | grep -q "^${VPN_CONTAINER}$"; then
    echo "❌ VPN 容器未运行"
    exit 1
fi

echo "正在停止 nodogsplash..."
docker exec $VPN_CONTAINER pkill nodogsplash 2>/dev/null || true

# 清除 iptables 规则
docker exec $VPN_CONTAINER bash -c "
    # 清除 nodogsplash 创建的链
    iptables -t nat -F ndsOUT 2>/dev/null || true
    iptables -t nat -X ndsOUT 2>/dev/null || true
    iptables -t filter -F ndsNET 2>/dev/null || true
    iptables -t filter -X ndsNET 2>/dev/null || true
    iptables -t filter -F ndsAUT 2>/dev/null || true
    iptables -t filter -X ndsAUT 2>/dev/null || true
"

echo "✓ nodogsplash 已停止"
