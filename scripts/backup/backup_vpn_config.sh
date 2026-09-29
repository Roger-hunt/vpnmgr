#!/bin/bash
# 备份 VPN 和 DNS 配置，以便回退

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${VPNMGR_BACKUP_DIR:-$SCRIPT_DIR/backup_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$BACKUP_DIR"

echo "📦 正在备份配置到 $BACKUP_DIR ..."

# 1. 备份当前 iptables 规则
sudo iptables-save > "$BACKUP_DIR/iptables-backup.rules" 2>/dev/null || echo "⚠️  无法备份 iptables"
sudo iptables -t nat -S > "$BACKUP_DIR/iptables-nat-backup.rules" 2>/dev/null || echo "⚠️  无法备份 NAT 规则"

# 2. 备份 dnsmasq 配置（如果存在）
if [ -f /etc/dnsmasq.conf ]; then
    sudo cp /etc/dnsmasq.conf "$BACKUP_DIR/dnsmasq.conf.bak"
fi
if [ -d /etc/dnsmasq.d ]; then
    sudo cp -r /etc/dnsmasq.d "$BACKUP_DIR/dnsmasq.d.bak" 2>/dev/null || true
fi

# 3. 备份 VPN 容器 DNS 配置
docker exec ipsec-vpn-server cat /etc/ipsec.conf 2>/dev/null > "$BACKUP_DIR/ipsec.conf.bak" || echo "⚠️  无法备份 ipsec.conf"
docker exec ipsec-vpn-server cat /etc/ppp/options.xl2tpd 2>/dev/null > "$BACKUP_DIR/options.xl2tpd.bak" || echo "⚠️  无法备份 xl2tpd 配置"

# 4. 记录当前网络配置
ip route > "$BACKUP_DIR/ip-route.txt" 2>/dev/null || true
ip addr > "$BACKUP_DIR/ip-addr.txt" 2>/dev/null || true

# 5. 保存 Docker 网络信息
docker network inspect ipsec-vpn-network > "$BACKUP_DIR/docker-network.json" 2>/dev/null || true

echo "✅ 备份完成！"
echo "📁 备份目录: $BACKUP_DIR"
echo ""
echo "回退时运行: sudo bash scripts/rollback_dns_hijack.sh $BACKUP_DIR"
