#!/usr/bin/env python3
"""
VPN Manager Startup Script
"""
import os
import sys
import argparse
import subprocess


def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import sqlalchemy
        import docker
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False


def init_db():
    """Initialize database"""
    print("🗄️  初始化数据库...")
    from vpnmgr.models.database import init_db, engine
    import asyncio
    
    async def _init():
        await init_db()
    
    asyncio.run(_init())
    print("✅ 数据库初始化完成")


def setup_vpn_network():
    """Setup network for VPN clients to access host services with real IP"""
    import subprocess
    import time
    
    VPN_CONTAINER_NAME = "ipsec-vpn-server"
    VPN_SUBNET = "192.168.43.0/24"
    DOCKER_SUBNET = "172.17.0.0/16"
    
    print("🔧 配置 VPN 网络...")
    
    # Check if VPN container is running
    result = subprocess.run(
        ['docker', 'inspect', VPN_CONTAINER_NAME, '--format', '{{.State.Running}}'],
        capture_output=True, text=True, check=False
    )
    
    if result.returncode != 0 or result.stdout.strip() != 'true':
        print("⚠️  VPN 容器未运行，跳过网络配置")
        print("   请在 VPN 容器启动后手动运行: sudo ./setup_vpn_network.sh")
        return
    
    # Get VPN container IP
    result = subprocess.run(
        ['docker', 'inspect', VPN_CONTAINER_NAME, '--format', 
         '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'],
        capture_output=True, text=True, check=False
    )
    
    if result.returncode != 0 or not result.stdout.strip():
        print("⚠️  无法获取 VPN 容器 IP")
        return
    
    vpn_ip = result.stdout.strip()
    print(f"   VPN 容器 IP: {vpn_ip}")
    
    errors = []
    
    # 1. Add route on host for VPN subnet
    try:
        # Check if route exists
        check = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True, check=False)
        if VPN_SUBNET in check.stdout:
            subprocess.run(
                ['sudo', 'ip', 'route', 'replace', VPN_SUBNET, 'via', vpn_ip, 'dev', 'docker0'],
                capture_output=True, check=True
            )
            print(f"   ✓ 更新路由: {VPN_SUBNET} via {vpn_ip}")
        else:
            subprocess.run(
                ['sudo', 'ip', 'route', 'add', VPN_SUBNET, 'via', vpn_ip, 'dev', 'docker0'],
                capture_output=True, check=True
            )
            print(f"   ✓ 添加路由: {VPN_SUBNET} via {vpn_ip}")
    except Exception as e:
        errors.append(f"路由设置失败: {e}")
    
    # 2. Add FORWARD rules to allow traffic between VPN and Docker subnets
    try:
        # VPN -> Docker
        check = subprocess.run(
            ['sudo', 'iptables', '-C', 'FORWARD', '-s', VPN_SUBNET, '-d', DOCKER_SUBNET, '-j', 'ACCEPT'],
            capture_output=True, check=False
        )
        if check.returncode != 0:
            subprocess.run(
                ['sudo', 'iptables', '-I', 'FORWARD', '1', '-s', VPN_SUBNET, '-d', DOCKER_SUBNET, '-j', 'ACCEPT'],
                capture_output=True, check=True
            )
            print(f"   ✓ FORWARD 规则: VPN -> Docker")
        
        # Docker -> VPN
        check = subprocess.run(
            ['sudo', 'iptables', '-C', 'FORWARD', '-s', DOCKER_SUBNET, '-d', VPN_SUBNET, '-j', 'ACCEPT'],
            capture_output=True, check=False
        )
        if check.returncode != 0:
            subprocess.run(
                ['sudo', 'iptables', '-I', 'FORWARD', '1', '-s', DOCKER_SUBNET, '-d', VPN_SUBNET, '-j', 'ACCEPT'],
                capture_output=True, check=True
            )
            print(f"   ✓ FORWARD 规则: Docker -> VPN")
    except Exception as e:
        errors.append(f"FORWARD 规则失败: {e}")
    
    # 3. Add INPUT rule to accept VPN traffic to host
    try:
        check = subprocess.run(
            ['sudo', 'iptables', '-C', 'INPUT', '-s', VPN_SUBNET, '-j', 'ACCEPT'],
            capture_output=True, check=False
        )
        if check.returncode != 0:
            subprocess.run(
                ['sudo', 'iptables', '-I', 'INPUT', '-s', VPN_SUBNET, '-j', 'ACCEPT'],
                capture_output=True, check=True
            )
            print(f"   ✓ INPUT 规则: 接受 VPN 流量")
    except Exception as e:
        errors.append(f"INPUT 规则失败: {e}")
    
    # 4. Add NAT exclusion rules in VPN container
    # Only exclude NAT for traffic from VPN clients going to THIS host specifically.
    # Other LAN services (192.168.1.x) must keep NAT so their reply packets can
    # find their way back through the VPN container.
    try:
        # Get this host's LAN IP to use as the specific NAT exclusion target
        host_ip_result = subprocess.run(
            ['docker', 'inspect', VPN_CONTAINER_NAME, '--format',
             '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}'],
            capture_output=True, text=True, check=False
        )
        # Fallback: detect host LAN IP from hostname
        hostname_result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, check=False)
        host_ips = hostname_result.stdout.strip().split() if hostname_result.returncode == 0 else []
        # Pick the LAN IP (not docker bridge, not VPN subnet)
        host_lan_ip = None
        for ip in host_ips:
            if not ip.startswith('172.') and not ip.startswith('192.168.43.'):
                host_lan_ip = ip
                break
        
        if host_lan_ip:
            # Specific rule: VPN clients → this host only, preserve source IP
            check = subprocess.run(
                ['docker', 'exec', VPN_CONTAINER_NAME, 'iptables', '-t', 'nat',
                 '-C', 'POSTROUTING', '-s', VPN_SUBNET, '-d', f'{host_lan_ip}/32', '-j', 'RETURN'],
                capture_output=True, check=False
            )
            if check.returncode != 0:
                subprocess.run(
                    ['docker', 'exec', VPN_CONTAINER_NAME, 'iptables', '-t', 'nat',
                     '-I', 'POSTROUTING', '1', '-s', VPN_SUBNET, '-d', f'{host_lan_ip}/32', '-j', 'RETURN'],
                    capture_output=True, check=False
                )
                print(f"   ✓ NAT 排除: VPN→{host_lan_ip} 保留真实客户端IP")
            else:
                print(f"   ✓ NAT 排除规则已存在: VPN→{host_lan_ip}")
        else:
            print(f"   ⚠️  无法确定宿主机LAN IP，跳过NAT排除设置")
        
        # Also exclude Docker subnet (keep existing behavior)
        check = subprocess.run(
            ['docker', 'exec', VPN_CONTAINER_NAME, 'iptables', '-t', 'nat',
             '-C', 'POSTROUTING', '-d', DOCKER_SUBNET, '-j', 'RETURN'],
            capture_output=True, check=False
        )
        if check.returncode != 0:
            subprocess.run(
                ['docker', 'exec', VPN_CONTAINER_NAME, 'iptables', '-t', 'nat',
                 '-I', 'POSTROUTING', '1', '-d', DOCKER_SUBNET, '-j', 'RETURN'],
                capture_output=True, check=False
            )
            print(f"   ✓ NAT 排除: Docker 子网 {DOCKER_SUBNET}")
    except Exception as e:
        errors.append(f"NAT 排除规则失败: {e}")

    
    if errors:
        print("⚠️  部分配置失败:")
        for err in errors:
            print(f"   - {err}")
    else:
        print("✅ VPN 网络配置完成")
    print()


def create_env():
    """Create .env file if not exists"""
    if not os.path.exists('.env'):
        print("📝 创建 .env 配置文件...")
        with open('.env.example', 'r') as f:
            content = f.read()
        with open('.env', 'w') as f:
            f.write(content)
        print("✅ 已创建 .env 文件，请根据您的环境编辑配置")
        print()
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='VPN Manager')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--skip-vpn-setup', action='store_true', help='Skip VPN network setup')
    args = parser.parse_args()
    
    print("🚀 VPN Manager 启动中...")
    print()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create .env if needed
    create_env()
    
    # Setup VPN network for client access (unless skipped)
    if not args.skip_vpn_setup:
        setup_vpn_network()
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Start server
    print(f"🌐 启动服务器: http://{args.host}:{args.port}")
    print()
    
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'vpnmgr.main:app',
        '--host', args.host,
        '--port', str(args.port),
    ]
    
    if args.reload:
        cmd.append('--reload')
    
    subprocess.run(cmd)


if __name__ == '__main__':
    main()
