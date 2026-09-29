#!/bin/bash
# Setup network for VPN client access to host services
# Run this script after VPN container starts

VPN_CONTAINER_NAME="ipsec-vpn-server"
VPN_SUBNET="192.168.43.0/24"
DOCKER_SUBNET="172.17.0.0/16"

echo "Setting up VPN network..."

# Get VPN container IP
VPN_IP=$(docker inspect $VPN_CONTAINER_NAME --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)

if [ -z "$VPN_IP" ]; then
    echo "❌ VPN container not found"
    exit 1
fi

echo "✓ VPN container IP: $VPN_IP"

# 1. Add route on host for VPN subnet
if ip route show | grep -q "$VPN_SUBNET"; then
    sudo ip route replace $VPN_SUBNET via $VPN_IP dev docker0
    echo "✓ Updated route: $VPN_SUBNET via $VPN_IP"
else
    sudo ip route add $VPN_SUBNET via $VPN_IP dev docker0
    echo "✓ Added route: $VPN_SUBNET via $VPN_IP"
fi

# 2. Add FORWARD rules to allow traffic between VPN and Docker subnets
if ! sudo iptables -C FORWARD -s $VPN_SUBNET -d $DOCKER_SUBNET -j ACCEPT 2>/dev/null; then
    sudo iptables -I FORWARD 1 -s $VPN_SUBNET -d $DOCKER_SUBNET -j ACCEPT
    echo "✓ Added FORWARD rule: VPN -> Docker"
fi

if ! sudo iptables -C FORWARD -s $DOCKER_SUBNET -d $VPN_SUBNET -j ACCEPT 2>/dev/null; then
    sudo iptables -I FORWARD 1 -s $DOCKER_SUBNET -d $VPN_SUBNET -j ACCEPT
    echo "✓ Added FORWARD rule: Docker -> VPN"
fi

# 3. Add INPUT rule to accept VPN traffic to host
if ! sudo iptables -C INPUT -s $VPN_SUBNET -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT -s $VPN_SUBNET -j ACCEPT
    echo "✓ Added INPUT rule to accept VPN traffic"
fi

# 4. Add NAT exclusion rules in VPN container for all host IPs
echo "✓ Adding NAT exclusions for host IPs..."
HOST_IPS=$(hostname -I 2>/dev/null || echo "172.17.0.1")
for IP in $HOST_IPS; do
    # 跳过 VPN 子网内的 IP
    if [[ "$IP" == 192.168.43.* ]]; then
        continue
    fi
    docker exec $VPN_CONTAINER_NAME iptables -t nat -C POSTROUTING -d $IP -j RETURN 2>/dev/null || \
    docker exec $VPN_CONTAINER_NAME iptables -t nat -I POSTROUTING 1 -d $IP -j RETURN 2>/dev/null
    echo "  - NAT exclusion for $IP"
done

# 5. Also exclude entire Docker subnet
docker exec $VPN_CONTAINER_NAME iptables -t nat -C POSTROUTING -d $DOCKER_SUBNET -j RETURN 2>/dev/null || \
docker exec $VPN_CONTAINER_NAME iptables -t nat -I POSTROUTING 1 -d $DOCKER_SUBNET -j RETURN 2>/dev/null
echo "  - NAT exclusion for $DOCKER_SUBNET"

echo ""
echo "✅ VPN network setup complete"
echo ""
echo "VPN clients can now access host services with their real IP (192.168.43.x)"
