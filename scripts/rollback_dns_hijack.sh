#!/bin/bash
# DNS 劫持回退脚本
# 用法: sudo bash rollback_dns_hijack.sh [备份目录]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKUP_DIR="${1:-}"
VPN_SUBNET="192.168.43.0/24"
HOST_IP="172.17.0.1"

echo -e "${GREEN}🔄 DNS 劫持回退脚本${NC}"
echo "================================"
echo ""

# 1. 恢复 iptables 规则
echo -e "${YELLOW}1. 清除 DNS 劫持 iptables 规则...${NC}"

# 删除 DNS 劫持规则
sudo iptables -t nat -D PREROUTING -s $VPN_SUBNET -p udp --dport 53 -j DNAT --to-destination $HOST_IP:53 2>/dev/null || true
sudo iptables -t nat -D PREROUTING -s $VPN_SUBNET -p tcp --dport 53 -j DNAT --to-destination $HOST_IP:53 2>/dev/null || true

# 删除 HTTP 重定向规则
sudo iptables -t nat -D PREROUTING -s $VPN_SUBNET -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || true

# 如果有备份，恢复原始 iptables 规则
if [ -f "$BACKUP_DIR/iptables-backup.rules" ]; then
    echo "恢复原始 iptables 规则..."
    sudo iptables-restore < "$BACKUP_DIR/iptables-backup.rules"
fi

echo -e "${GREEN}✓ iptables 规则已恢复${NC}"
echo ""

# 2. 停止并禁用 dnsmasq
echo -e "${YELLOW}2. 停止 dnsmasq 服务...${NC}"
sudo systemctl stop dnsmasq 2>/dev/null || true
sudo systemctl disable dnsmasq 2>/dev/null || true
echo -e "${GREEN}✓ dnsmasq 已停止${NC}"
echo ""

# 3. 恢复 dnsmasq 配置
echo -e "${YELLOW}3. 恢复 dnsmasq 配置...${NC}"
if [ -f "$BACKUP_DIR/dnsmasq.conf.bak" ]; then
    sudo cp "$BACKUP_DIR/dnsmasq.conf.bak" /etc/dnsmasq.conf
    echo "恢复原始 dnsmasq.conf"
else
    # 删除我们的配置
    sudo rm -f /etc/dnsmasq.d/vpn-captive.conf
    echo "删除 VPN DNS 配置"
fi

# 恢复 dnsmasq.d 目录
if [ -d "$BACKUP_DIR/dnsmasq.d.bak" ]; then
    sudo rm -rf /etc/dnsmasq.d
    sudo cp -r "$BACKUP_DIR/dnsmasq.d.bak" /etc/dnsmasq.d
    echo "恢复 dnsmasq.d 目录"
fi
echo -e "${GREEN}✓ dnsmasq 配置已恢复${NC}"
echo ""

# 4. 恢复系统 DNS 配置
echo -e "${YELLOW}4. 恢复系统 DNS 配置...${NC}"
sudo rm -f /etc/resolv.conf
sudo systemctl enable systemd-resolved 2>/dev/null || true
sudo systemctl start systemd-resolved 2>/dev/null || true
echo -e "${GREEN}✓ 系统 DNS 已恢复${NC}"
echo ""

# 5. 恢复 VPN 容器配置
echo -e "${YELLOW}5. 恢复 VPN 容器配置...${NC}"
if [ -f "$BACKUP_DIR/ipsec.conf.bak" ] && [ -s "$BACKUP_DIR/ipsec.conf.bak" ]; then
    docker cp "$BACKUP_DIR/ipsec.conf.bak" ipsec-vpn-server:/etc/ipsec.conf
    docker exec ipsec-vpn-server ipsec restart
    echo "恢复 VPN DNS 配置"
fi
echo -e "${GREEN}✓ VPN 配置已恢复${NC}"
echo ""

# 6. 清理日志
echo -e "${YELLOW}6. 清理日志文件...${NC}"
sudo rm -f /var/log/dnsmasq.log
echo -e "${GREEN}✓ 日志已清理${NC}"
echo ""

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ DNS 劫持已回退完成！${NC}"
echo ""
echo "系统已恢复到配置前的状态："
echo "  • DNS 劫持规则已清除"
echo "  • dnsmasq 已停止"
echo "  • 原始 DNS 配置已恢复"
echo ""
echo -e "${YELLOW}注意:${NC}"
echo "  VPN 客户端需要重新连接才能使用正常 DNS"
echo ""
