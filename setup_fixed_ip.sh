#!/bin/bash
# 为证书分配固定IP（通过脚本实现）

# 定义证书到IP的映射（示例）
# 格式: "证书名:IP"
# 可在实际环境中根据需求修改，或通过外部配置加载
declare -A CERT_IP_MAP=(
    ["client1"]="192.168.43.11"
    ["client2"]="192.168.43.12"
    # 添加更多映射...
)

VPN_CONTAINER="${VPN_CONTAINER_NAME:-ipsec-vpn-server}"
SERVER_DOMAIN="${VPN_SERVER_DOMAIN:-${VPN_DOMAIN:-vpn.example.com}}"

# 为每个证书创建独立连接配置
for cert in "${!CERT_IP_MAP[@]}"; do
    ip="${CERT_IP_MAP[$cert]}"
    
    # 创建独立连接配置（使用narrowing限制特定ID）
    cat << CONF | docker exec -i $VPN_CONTAINER tee /etc/ipsec.d/${cert}.conf
default $cert {
    left=%defaultroute
    leftcert=$SERVER_DOMAIN
    right=%any
    rightid="CN=$cert, O=IKEv2 VPN"
    rightaddresspool=$ip-$ip
    narrowing=yes
    auto=add
    ikev2=insist
    also=ikev2-cp
}
CONF

    echo "✓ 证书 $cert -> IP $ip (Domain: $SERVER_DOMAIN)"
done

# 重启 ipsec
docker exec $VPN_CONTAINER ipsec restart
