# 运维脚本

VPN Manager 的辅助运维脚本。

## 文件说明

| 文件 | 说明 |
|------|------|
| `backup/backup_vpn_config.sh` | 备份当前 iptables / NAT / dnsmasq 配置，便于回退 |

## 使用方法

```bash
# 备份当前网络配置（建议在改动 iptables 或 DNS 之前执行）
sudo bash scripts/backup/backup_vpn_config.sh
```

备份会输出到 `scripts/backup/backup_<时间戳>/`，也可通过 `VPNMGR_BACKUP_DIR`
环境变量指定目录。

## 关于 Captive Portal

本项目的 Captive Portal（强制门户）方案已于 2026-09 移除，相关脚本与排查文档
（`nodogsplash-test/`、`VIVO_TROUBLESHOOTING.md`、`rollback_dns_hijack.sh`）已删除。

原因：**Captive Portal 在 IPsec/IKEv2 隧道上无法工作**。

- Android 的 `NetworkMonitor` 不对 `TRANSPORT_VPN` 网络做连通性/门户探测
- iOS 的 Captive Network Assistant 由 WiFi 关联触发，VPN 接口不触发
- 探测跑在物理网络层，隧道内的 iptables 拦截对它完全不可见

也就是说，无论怎么配置 DNS 劫持或防火墙，系统级的门户弹窗都不会出现。

更根本地说，VPN 访问已经由**客户端证书**完整把关：没有通过 Libreswan 证书校验的
客户端根本拿不到 VPN IP。在网络层再查一遍账号绑定，只是重复推导隧道已经证明过的
身份，不产生任何新增判断。

因此现在由 `vpnmgr/utils/vpn_forwarding.py` 在启动时确保 VPN 子网正常出网，并清理
历史遗留的 `CAPTIVE_AUTH` 链。`/welcome` 页面保留为纯信息落地页，不再拦截流量。
