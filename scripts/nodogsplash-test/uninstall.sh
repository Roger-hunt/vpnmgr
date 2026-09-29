#!/bin/bash
# 完全卸载 nodogsplash

VPN_CONTAINER="ipsec-vpn-server"

if ! docker ps --format "{{.Names}}" | grep -q "^${VPN_CONTAINER}$"; then
    echo "❌ VPN 容器未运行"
    exit 1
fi

echo "正在卸载 nodogsplash..."

# 停止服务
docker exec $VPN_CONTAINER pkill nodogsplash 2>/dev/null || true

# 卸载软件包
docker exec $VPN_CONTAINER bash -c "
    export DEBIAN_FRONTEND=noninteractive
    apt-get remove -y nodogsplash 2>/dev/null || true
    apt-get autoremove -y 2>/dev/null || true
"

# 删除配置
docker exec $VPN_CONTAINER rm -rf /etc/nodogsplash /var/log/nodogsplash

echo "✓ nodogsplash 已卸载"
