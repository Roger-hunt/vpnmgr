/**
 * VPN Manager - Internationalization (i18n) Engine
 * Supports Simplified Chinese (zh) and English (en)
 */

(function () {
    const STORAGE_KEY = 'vpnmgr_lang';

    const translations = {
        zh: {
            // App & Navigation
            'app.name': 'VPN Manager',
            'nav.overview': '概览',
            'nav.users': '用户管理',
            'nav.certs': '证书管理',
            'nav.logs': '连接记录',
            'nav.debug': '调试信息',
            'nav.logout': '退出登录',
            'nav.admin': '管理员',
            'nav.user': '普通用户',
            'nav.switchLang': 'English',

            // Common labels and actions
            'common.save': '保存',
            'common.cancel': '取消',
            'common.delete': '删除',
            'common.edit': '编辑',
            'common.view': '查看',
            'common.viewDetails': '查看详情',
            'common.refresh': '刷新',
            'common.export': '导出',
            'common.search': '搜索',
            'common.close': '关闭',
            'common.confirm': '确认',
            'common.status': '状态',
            'common.actions': '操作',
            'common.loading': '加载中...',
            'common.empty': '暂无数据',
            'common.online': '在线',
            'common.offline': '离线',
            'common.active': '有效',
            'common.revoked': '已撤销',
            'common.enabled': '启用',
            'common.disabled': '禁用',
            'common.configured': '已配置',
            'common.notConfigured': '未配置',
            'common.success': '成功',
            'common.failed': '失败',
            'common.warning': '警告',
            'common.description': '描述',
            'common.notes': '备注',
            'common.createdAt': '创建时间',
            'common.time': '时间',
            'common.username': '用户名',
            'common.password': '密码',
            'common.email': '邮箱',
            'common.displayName': '显示名称',
            'common.role': '角色',
            'common.random': '随机生成',
            'common.optional': '可选',
            'common.allStatus': '全部状态',
            'common.connected': '已连接',
            'common.disconnected': '已断开',
            'common.required': '必填',
            'common.none': '无',

            // Dashboard
            'dashboard.title': '系统概览',
            'dashboard.vpnStatus': 'VPN 服务状态',
            'dashboard.totalUsers': '总用户数',
            'dashboard.onlineUsers': '在线用户',
            'dashboard.activeConns': '活跃连接',
            'dashboard.realtime': '实时',
            'dashboard.noConns': '暂无活跃连接',
            'dashboard.clientIp': '客户端 IP',
            'dashboard.assignedIp': '分配 IP',
            'dashboard.tunnelType': '隧道类型',
            'dashboard.connId': '连接 ID',
            'dashboard.running': '运行中',
            'dashboard.stopped': '已停止',
            'dashboard.kick': '断开',
            'dashboard.kickAll': '断开所有连接',
            'dashboard.kickConfirm': '确定要断开此 VPN 连接吗？',
            'dashboard.kickAllConfirm': '确定要断开所有活动的 VPN 连接吗？',
            'dashboard.kickSuccess': '连接已断开',
            'dashboard.kickAllSuccess': '已断开所有活跃连接',

            // Users
            'users.title': '用户管理',
            'users.addUser': '添加用户',
            'users.editUser': '编辑用户',
            'users.viewUser': '用户详情',
            'users.tableUsername': '用户名',
            'users.tableVpnConfig': 'VPN 配置',
            'users.tableStatus': '状态',
            'users.tableCreatedAt': '创建时间',
            'users.tableActions': '操作',
            'users.noUsers': '暂无用户',
            'users.vpnCertTip': '证书: {name}',
            'users.vpnUserTip': '账号: {name}',
            'users.roleAdmin': '管理员',
            'users.roleUser': '普通用户',
            'users.certStatus': 'IKEv2 证书',
            'users.vpnUserStatus': 'L2TP / XAuth 账号',
            'users.basicInfo': '基本信息',
            'users.vpnStatus': 'VPN 连接状态',
            'users.assignedIp': 'VPN IP',
            'users.downloadCertP12': '下载证书 (.p12)',
            'users.downloadCertProfile': 'iOS/macOS 配置',
            'users.usernamePlaceholder': '字母、数字或下划线',
            'users.passwordPlaceholder': '登录管理面板的密码',
            'users.passwordHint': '(留空则不修改密码)',
            'users.displayNamePlaceholder': '如：张三',
            'users.emailPlaceholder': 'user@example.com',
            'users.notesPlaceholder': '用户说明或备注信息',
            'users.adminPrivilege': '设为管理员 (可登录管理面板)',
            'users.certNamePlaceholder': '例如: user_vpn',
            'users.certNameHint': '生成用于 IKEv2 的证书文件',
            'users.generateNewCert': '生成证书',
            'users.downloadCert': '下载证书',
            'users.vpnUsernamePlaceholder': '用于 L2TP/XAuth 连接的账号',
            'users.vpnPasswordPlaceholder': '留空则保持原密码',
            'users.vpnPasswordHint': '用于 L2TP/XAuth 协议连接的独立密码',
            'users.deleteConfirm': '确定要彻底删除用户 "{username}" 吗？\n\n警告：这将同时注销并删除该用户的 VPN 证书和配置！',
            'users.deleteSuccess': '用户及关联配置已删除',
            'users.createSuccess': '用户创建成功',
            'users.updateSuccess': '用户更新成功',
            'users.generateCertConfirm': '确定要为该用户生成证书 "{certName}" 吗？',
            'users.generateCertSuccess': '证书生成成功！请保存后下载证书文件。',
            'users.certPrompt': '请先输入证书名称',
            'users.certDownloadStart': '证书下载开始',
            'users.downloadFailed': '下载失败',

            // Certs
            'certs.title': 'IKEv2 证书管理',
            'certs.generateCert': '生成证书',
            'certs.banner': 'IKEv2 证书用于 iOS/macOS/Windows/Android 设备的 VPN 连接。证书与系统用户 1:1 绑定，确保身份可信。',
            'certs.listTitle': '证书列表',
            'certs.clientName': '客户端名称',
            'certs.boundUser': '绑定用户',
            'certs.status': '状态',
            'certs.createdAt': '创建时间',
            'certs.actions': '操作',
            'certs.noCerts': '暂无证书',
            'certs.unbound': '未绑定',
            'certs.bind': '绑定',
            'certs.unbind': '解绑',
            'certs.revoke': '撤销',
            'certs.download': '下载',
            'certs.revokeConfirm': '确定要撤销证书 "{clientName}" 吗？撤销后该客户端将无法连接 VPN。',
            'certs.revokeSuccess': '证书已撤销',
            'certs.unbindConfirm': '确定要解除证书 "{clientName}" 的绑定吗？',
            'certs.unbindSuccess': '绑定已解除',
            'certs.bindSuccess': '证书绑定成功',
            'certs.modalGenerateTitle': '生成 IKEv2 证书',
            'certs.modalBindTitle': '证书绑定',
            'certs.inputCertName': '证书名称 *',
            'certs.inputCertNamePlaceholder': '例如：ZhangsanVPN',
            'certs.inputCertNameHint': '建议使用有意义的名称，将与系统用户绑定',
            'certs.selectUser': '绑定到系统用户',
            'certs.selectUserPlaceholder': '-- 选择用户 --',
            'certs.selectUserHint': '选择要绑定此证书的系统用户（可选）',
            'certs.descPlaceholder': '可选',
            'certs.currentBindStatus': '当前绑定状态',
            'certs.boundToUser': '已绑定到用户: {username}',
            'certs.notBound': '未绑定到任何用户',
            'certs.certGenSuccess': '证书生成成功',
            'certs.certGenSuccessTip': '证书已成功生成！请下载并保存 .p12 文件。',
            'certs.installGuide': '安装说明:',
            'certs.guideIos': 'iOS/macOS: 通过邮件或 AirDrop 发送 .p12 文件到设备，点击安装',
            'certs.guideWin': 'Windows: 双击 .p12 文件，按向导导入到"个人"证书存储',
            'certs.guideAndroid': 'Android: 在设置 -> 安全 -> 从存储安装证书',
            'certs.downloadP12': '下载 .p12 文件',
            'certs.noDownloadableCert': '没有可下载的证书',
            'certs.downloadingFormat': '正在导出 {format} 格式...',
            'certs.downloadSuccess': '证书 {filename} 下载成功',
            'certs.viewBinding': '查看绑定',
            'certs.selectUserError': '请选择要绑定的用户',

            // Logs
            'logs.title': 'VPN 连接记录',
            'logs.refresh': '刷新',
            'logs.export': '导出',
            'logs.total': '总连接数',
            'logs.online': '当前在线',
            'logs.today': '今日连接',
            'logs.searchPlaceholder': '搜索客户端...',
            'logs.tableTime': '时间',
            'logs.tableClient': '客户端',
            'logs.tableUser': '系统用户',
            'logs.tableType': '类型',
            'logs.tableClientIp': '客户端 IP',
            'logs.tableAssignedIp': '分配 IP',
            'logs.tableStatus': '状态',
            'logs.tableDuration': '在线时长',
            'logs.noLogs': '暂无连接记录',
            'logs.detailTitle': '连接详情',
            'logs.connectTime': '连接时间',
            'logs.disconnectTime': '断开时间',
            'logs.rawLog': '原始日志',

            // Debug
            'debug.title': '系统调试信息',
            'debug.networkInfo': '本机网络信息',
            'debug.realIp': '您的实际 IP',
            'debug.realIpDesc': '您访问此页面使用的 IP',
            'debug.serverIp': '服务器看到的 IP',
            'debug.serverIpDesc': 'Web 服务器直接看到的客户端 IP',
            'debug.activeCount': '活跃连接数',
            'debug.activeCountDesc': '服务器当前 VPN 连接数',
            'debug.ipVerified': 'IP 验证状态',
            'debug.ipVerifiedDesc': '验证 IP 是否来自合法的 VPN 连接',
            'debug.detecting': '检测中...',
            'debug.trafficStatus': '实时流量与连接',
            'debug.systemStatus': '系统诊断',
            'debug.activeConnsTitle': '当前活跃的 VPN 连接',
            'debug.colClient': '证书名/用户名',
            'debug.colPublicIp': '公网 IP',
            'debug.colInternalIp': '分配的内网 IP',
            'debug.noConns': '当前没有活跃的 VPN 连接',
            'debug.reqDetails': '请求详情',
            'debug.detectTime': '检测时间:',
            'debug.refreshInfo': '刷新信息',
            'debug.copyInfo': '复制信息',
            'debug.verified': '已验证',
            'debug.unverified': '未验证',
            'debug.nonVpn': '非 VPN IP',
            'debug.connecting': '连接中',
            'debug.instructions': '说明',
            'debug.securityMechanism': '安全机制',
            'debug.copySuccess': '信息已复制到剪贴板',
            'debug.copyFail': '复制失败',
            'debug.waitLoad': '请先等待数据加载',
            'debug.note1': '<strong>本机网络信息</strong>显示您当前访问此页面的 IP 和活跃连接数',
            'debug.note2': '<strong>IP 验证状态</strong>：已验证表示来自合法 VPN 连接；未验证提示可能存在安全风险',
            'debug.note3': '<strong>活跃的 VPN 连接</strong>列表显示服务器上所有当前的 VPN 连接',
            'debug.note4': '请在<strong>证书名</strong>列中找到您使用的证书名，对应的就是您的连接',
            'debug.note5': '<strong>分配的内网 IP</strong>是 VPN 连接成功后分配给您的地址（如 192.168.43.x）',
            'debug.note6': '如果列表为空，说明当前没有用户连接到 VPN',
            'debug.sec1': '<strong>IPsec/IKEv2 协议</strong>：确保 IP 地址由服务器强制分配，客户端无法自行声明',
            'debug.sec2': '<strong>内核级验证</strong>：IPsec SA（安全关联）确保只有匹配的数据包能通过隧道',
            'debug.sec3': '<strong>应用层验证</strong>：每次请求都验证 IP 是否在当前活跃 VPN 连接列表中',
            'debug.sec4': '<strong>地址池隔离</strong>：VPN 客户端只能从 192.168.43.0/24 子网获取 IP，无法占用其他地址',
            'debug.sec5': '<strong>单设备限制</strong>：每个证书只能同时在线一个设备（新连接会踢掉旧连接）',

            // Login
            'login.title': 'VPN Manager - 登录',
            'login.welcome': '欢迎回来',
            'login.subtitle': '请登录您的管理账号',
            'login.username': '用户名',
            'login.password': '密码',
            'login.usernamePlaceholder': '输入用户名',
            'login.passwordPlaceholder': '输入密码',
            'login.rememberMe': '记住我',
            'login.signIn': '登录',
            'login.signingIn': '登录中...',
            'login.failed': '登录失败',
            'login.invalidCreds': '用户名或密码错误',
            'login.networkError': '网络错误，请稍后重试',

            // Welcome page
            'login.footerBrand': 'VPN Manager',
            'welcome.brandTitle': 'VPN Manager',
            'welcome.title': '欢迎 - VPN Manager',
            'welcome.connStatus': '连接状态',
            'welcome.connected': '已连接',
            'welcome.notConnected': '未连接',
            'welcome.username': '用户名',
            'welcome.publicIp': '公网 IP',
            'welcome.yourIp': '您的 IP',
            'welcome.serviceStatus': '服务状态',
            'welcome.running': '运行中',
            'welcome.stopped': '已停止',
            'welcome.diagnostics': '网络诊断',
            'welcome.adminPanel': '管理后台',
        },
        en: {
            // App & Navigation
            'app.name': 'VPN Manager',
            'nav.overview': 'Overview',
            'nav.users': 'Users',
            'nav.certs': 'Certificates',
            'nav.logs': 'Logs',
            'nav.debug': 'Diagnostics',
            'nav.logout': 'Sign Out',
            'nav.admin': 'Administrator',
            'nav.user': 'Standard User',
            'nav.switchLang': '中文',

            // Common labels and actions
            'common.save': 'Save',
            'common.cancel': 'Cancel',
            'common.delete': 'Delete',
            'common.edit': 'Edit',
            'common.view': 'View',
            'common.viewDetails': 'View Details',
            'common.refresh': 'Refresh',
            'common.export': 'Export',
            'common.search': 'Search',
            'common.close': 'Close',
            'common.confirm': 'Confirm',
            'common.status': 'Status',
            'common.actions': 'Actions',
            'common.loading': 'Loading...',
            'common.empty': 'No data available',
            'common.online': 'Online',
            'common.offline': 'Offline',
            'common.active': 'Valid',
            'common.revoked': 'Revoked',
            'common.enabled': 'Enabled',
            'common.disabled': 'Disabled',
            'common.configured': 'Configured',
            'common.notConfigured': 'Unconfigured',
            'common.success': 'Success',
            'common.failed': 'Failed',
            'common.warning': 'Warning',
            'common.description': 'Description',
            'common.notes': 'Notes',
            'common.createdAt': 'Created At',
            'common.time': 'Time',
            'common.username': 'Username',
            'common.password': 'Password',
            'common.email': 'Email',
            'common.displayName': 'Display Name',
            'common.role': 'Role',
            'common.random': 'Random',
            'common.optional': 'Optional',
            'common.allStatus': 'All Status',
            'common.connected': 'Connected',
            'common.disconnected': 'Disconnected',
            'common.required': 'Required',
            'common.none': 'None',

            // Dashboard
            'dashboard.title': 'System Overview',
            'dashboard.vpnStatus': 'VPN Service Status',
            'dashboard.totalUsers': 'Total Users',
            'dashboard.onlineUsers': 'Online Users',
            'dashboard.activeConns': 'Active Connections',
            'dashboard.realtime': 'Realtime',
            'dashboard.noConns': 'No active connections',
            'dashboard.clientIp': 'Client IP',
            'dashboard.assignedIp': 'Assigned IP',
            'dashboard.tunnelType': 'Tunnel Type',
            'dashboard.connId': 'Session ID',
            'dashboard.running': 'Running',
            'dashboard.stopped': 'Stopped',
            'dashboard.kick': 'Disconnect',
            'dashboard.kickAll': 'Disconnect All',
            'dashboard.kickConfirm': 'Are you sure you want to disconnect this VPN session?',
            'dashboard.kickAllConfirm': 'Are you sure you want to disconnect ALL active VPN sessions?',
            'dashboard.kickSuccess': 'Session disconnected',
            'dashboard.kickAllSuccess': 'All active connections disconnected',

            // Users
            'users.title': 'User Management',
            'users.addUser': 'Add User',
            'users.editUser': 'Edit User',
            'users.viewUser': 'User Details',
            'users.tableUsername': 'Username',
            'users.tableVpnConfig': 'VPN Config',
            'users.tableStatus': 'Status',
            'users.tableCreatedAt': 'Created At',
            'users.tableActions': 'Actions',
            'users.noUsers': 'No users found',
            'users.vpnCertTip': 'Certificate: {name}',
            'users.vpnUserTip': 'Account: {name}',
            'users.roleAdmin': 'Admin',
            'users.roleUser': 'User',
            'users.certStatus': 'IKEv2 Certificate',
            'users.vpnUserStatus': 'L2TP / XAuth Account',
            'users.basicInfo': 'Basic Information',
            'users.vpnStatus': 'VPN Status',
            'users.assignedIp': 'VPN IP',
            'users.downloadCertP12': 'Download Cert (.p12)',
            'users.downloadCertProfile': 'iOS/macOS Profile',
            'users.usernamePlaceholder': 'Letters, numbers, underscores',
            'users.passwordPlaceholder': 'Panel login password',
            'users.passwordHint': '(Leave blank to keep unchanged)',
            'users.displayNamePlaceholder': 'e.g., John Doe',
            'users.emailPlaceholder': 'user@example.com',
            'users.notesPlaceholder': 'Description or notes',
            'users.adminPrivilege': 'Admin Privileges (can log in to panel)',
            'users.certNamePlaceholder': 'e.g., user_vpn',
            'users.certNameHint': 'Generates client certificate for IKEv2',
            'users.generateNewCert': 'Generate Cert',
            'users.downloadCert': 'Download Cert',
            'users.vpnUsernamePlaceholder': 'Username for L2TP/XAuth login',
            'users.vpnPasswordPlaceholder': 'Leave blank to keep unchanged',
            'users.vpnPasswordHint': 'Dedicated credentials for L2TP/XAuth VPN',
            'users.deleteConfirm': 'Are you sure you want to permanently delete user "{username}"?\n\nWarning: This will also revoke their VPN certificate and wipe their configuration!',
            'users.deleteSuccess': 'User and associated configuration deleted',
            'users.createSuccess': 'User created successfully',
            'users.updateSuccess': 'User updated successfully',
            'users.generateCertConfirm': 'Are you sure you want to generate certificate "{certName}" for this user?',
            'users.generateCertSuccess': 'Certificate generated successfully! Please save and download.',
            'users.certPrompt': 'Please enter a certificate name first',
            'users.certDownloadStart': 'Certificate download started',
            'users.downloadFailed': 'Download failed',

            // Certs
            'certs.title': 'IKEv2 Certificate Management',
            'certs.generateCert': 'Generate Certificate',
            'certs.banner': 'IKEv2 certificates are used for VPN connections on iOS/macOS/Windows/Android. Bound 1:1 with system users for trusted authentication.',
            'certs.listTitle': 'Certificates List',
            'certs.clientName': 'Client Name',
            'certs.boundUser': 'Bound User',
            'certs.status': 'Status',
            'certs.createdAt': 'Created At',
            'certs.actions': 'Actions',
            'certs.noCerts': 'No certificates found',
            'certs.unbound': 'Unbound',
            'certs.bind': 'Bind',
            'certs.unbind': 'Unbind',
            'certs.revoke': 'Revoke',
            'certs.download': 'Download',
            'certs.revokeConfirm': 'Are you sure you want to revoke certificate "{clientName}"? This client will no longer be able to connect.',
            'certs.revokeSuccess': 'Certificate revoked successfully',
            'certs.unbindConfirm': 'Are you sure you want to unbind certificate "{clientName}"?',
            'certs.unbindSuccess': 'Binding removed',
            'certs.bindSuccess': 'Certificate bound successfully',
            'certs.modalGenerateTitle': 'Generate IKEv2 Certificate',
            'certs.modalBindTitle': 'Certificate Binding',
            'certs.inputCertName': 'Certificate Name *',
            'certs.inputCertNamePlaceholder': 'e.g. ZhangsanVPN',
            'certs.inputCertNameHint': 'A descriptive name bound to a system user',
            'certs.selectUser': 'Bind to System User',
            'certs.selectUserPlaceholder': '-- Select User --',
            'certs.selectUserHint': 'Optionally bind this certificate to a user',
            'certs.descPlaceholder': 'Optional',
            'certs.currentBindStatus': 'Current Binding Status',
            'certs.boundToUser': 'Bound to user: {username}',
            'certs.notBound': 'Not bound to any user',
            'certs.certGenSuccess': 'Certificate Generated',
            'certs.certGenSuccessTip': 'Certificate generated successfully! Please download and save the .p12 file.',
            'certs.installGuide': 'Installation Guide:',
            'certs.guideIos': 'iOS/macOS: Send .p12 file via Mail or AirDrop, tap to install',
            'certs.guideWin': 'Windows: Double-click .p12 file and import into "Personal" store',
            'certs.guideAndroid': 'Android: Settings -> Security -> Install from storage',
            'certs.downloadP12': 'Download .p12 File',
            'certs.noDownloadableCert': 'No certificate available to download',
            'certs.downloadingFormat': 'Exporting {format} format...',
            'certs.downloadSuccess': 'Certificate {filename} downloaded successfully',
            'certs.viewBinding': 'View Binding',
            'certs.selectUserError': 'Please select a user to bind',

            // Logs
            'logs.title': 'VPN Connection Logs',
            'logs.refresh': 'Refresh',
            'logs.export': 'Export',
            'logs.total': 'Total Sessions',
            'logs.online': 'Currently Online',
            'logs.today': 'Sessions Today',
            'logs.searchPlaceholder': 'Search client...',
            'logs.tableTime': 'Time',
            'logs.tableClient': 'Client',
            'logs.tableUser': 'System User',
            'logs.tableType': 'Type',
            'logs.tableClientIp': 'Client IP',
            'logs.tableAssignedIp': 'Assigned IP',
            'logs.tableStatus': 'Status',
            'logs.tableDuration': 'Duration',
            'logs.noLogs': 'No connection records found',
            'logs.detailTitle': 'Connection Details',
            'logs.connectTime': 'Connected At',
            'logs.disconnectTime': 'Disconnected At',
            'logs.rawLog': 'Raw Log',

            // Debug
            'debug.title': 'System Diagnostics',
            'debug.networkInfo': 'Host Network Information',
            'debug.realIp': 'Your Real IP',
            'debug.realIpDesc': 'IP used to access this management panel',
            'debug.serverIp': 'Server-Detected IP',
            'debug.serverIpDesc': 'Client IP detected directly by Web server',
            'debug.activeCount': 'Active Connections',
            'debug.activeCountDesc': 'Current VPN client count on server',
            'debug.ipVerified': 'IP Verification Status',
            'debug.ipVerifiedDesc': 'Verifies if IP originates from an active VPN tunnel',
            'debug.detecting': 'Detecting...',
            'debug.trafficStatus': 'Realtime Traffic & Connections',
            'debug.systemStatus': 'System Diagnostics',
            'debug.activeConnsTitle': 'Active VPN Connections',
            'debug.colClient': 'Certificate / Username',
            'debug.colPublicIp': 'Public IP',
            'debug.colInternalIp': 'Assigned Internal IP',
            'debug.noConns': 'No active VPN connections currently',
            'debug.reqDetails': 'Request Details',
            'debug.detectTime': 'Detection Time:',
            'debug.refreshInfo': 'Refresh Info',
            'debug.copyInfo': 'Copy Info',
            'debug.verified': 'Verified',
            'debug.unverified': 'Unverified',
            'debug.nonVpn': 'Non-VPN IP',
            'debug.connecting': 'Connected',
            'debug.instructions': 'Instructions',
            'debug.securityMechanism': 'Security Architecture',
            'debug.copySuccess': 'Information copied to clipboard',
            'debug.copyFail': 'Failed to copy',
            'debug.waitLoad': 'Please wait for data to load',
            'debug.note1': '<strong>Host Network Information</strong> displays your access IP and active connection count',
            'debug.note2': '<strong>IP Verification</strong>: Verified indicates authentic VPN tunnel; Unverified warns of security risks',
            'debug.note3': '<strong>Active VPN Connections</strong> table shows all currently connected clients',
            'debug.note4': 'Locate your client/certificate name in the list to inspect your connection',
            'debug.note5': '<strong>Assigned Internal IP</strong> is the private IP leased to your device (e.g. 192.168.43.x)',
            'debug.note6': 'If the list is empty, no clients are currently connected to the VPN server',
            'debug.sec1': '<strong>IPsec/IKEv2 Protocol</strong>: Ensures IP addresses are forcefully leased by server; clients cannot spoof IPs',
            'debug.sec2': '<strong>Kernel-level Verification</strong>: IPsec SA ensures only matching packets can pass through the tunnel',
            'debug.sec3': '<strong>Application-level Check</strong>: Every request validates the caller IP against active VPN sessions',
            'debug.sec4': '<strong>Subnet Isolation</strong>: Clients only lease from 192.168.43.0/24 subnet without occupying other ranges',
            'debug.sec5': '<strong>Single-Device Concurrency</strong>: Each certificate permits one concurrent device (new replaces old)',

            // Login
            'login.title': 'VPN Manager - Sign In',
            'login.welcome': 'Welcome Back',
            'login.subtitle': 'Sign in to access the administrator panel',
            'login.username': 'Username',
            'login.password': 'Password',
            'login.usernamePlaceholder': 'Enter username',
            'login.passwordPlaceholder': 'Enter password',
            'login.rememberMe': 'Remember me',
            'login.signIn': 'Sign In',
            'login.signingIn': 'Signing in...',
            'login.failed': 'Sign In Failed',
            'login.invalidCreds': 'Invalid username or password',
            'login.networkError': 'Network request failed, please try again',

            // Welcome page
            'login.footerBrand': 'VPN Manager',
            'welcome.brandTitle': 'VPN Manager',
            'welcome.title': 'Welcome - VPN Manager',
            'welcome.connStatus': 'Connection Status',
            'welcome.connected': 'Connected',
            'welcome.notConnected': 'Not Connected',
            'welcome.username': 'Username',
            'welcome.publicIp': 'Public IP',
            'welcome.yourIp': 'Your IP',
            'welcome.serviceStatus': 'Service Status',
            'welcome.running': 'Running',
            'welcome.stopped': 'Stopped',
            'welcome.diagnostics': 'Network Diagnostics',
            'welcome.adminPanel': 'Admin Panel',
        }
    };

    let currentLang = localStorage.getItem(STORAGE_KEY) || 'zh';
    const listeners = [];

    function getLanguage() {
        return currentLang;
    }

    function t(key, params, fallback) {
        let text = translations[currentLang]?.[key];
        if (!text) {
            text = translations['zh']?.[key] || fallback || key;
        }
        if (params && typeof params === 'object') {
            for (const [k, v] of Object.entries(params)) {
                text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
            }
        }
        return text;
    }

    function applyDOM(root = document) {
        // Elements with data-i18n
        root.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                el.textContent = t(key);
            }
        });

        // Elements with data-i18n-html
        root.querySelectorAll('[data-i18n-html]').forEach(el => {
            const key = el.getAttribute('data-i18n-html');
            if (key) {
                el.innerHTML = t(key);
            }
        });

        // Input placeholders
        root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) {
                el.placeholder = t(key);
            }
        });

        // Tooltips / Titles
        root.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                el.title = t(key);
            }
        });

        // Update language switcher buttons text
        document.querySelectorAll('.current-lang-text').forEach(el => {
            el.textContent = currentLang === 'zh' ? 'EN' : '中';
        });

        // Update html lang attribute
        document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
    }

    function setLanguage(lang) {
        if (!translations[lang]) return;
        currentLang = lang;
        try {
            localStorage.setItem(STORAGE_KEY, lang);
        } catch (e) {
            console.error('Failed to save language to localStorage:', e);
        }
        applyDOM();
        listeners.forEach(fn => {
            try { fn(currentLang); } catch (e) { console.error('i18n listener error:', e); }
        });
    }

    function toggleLanguage() {
        setLanguage(currentLang === 'zh' ? 'en' : 'zh');
    }

    function onChange(callback) {
        if (typeof callback === 'function') {
            listeners.push(callback);
        }
    }

    // Expose to window
    window.i18n = {
        getLanguage,
        setLanguage,
        toggleLanguage,
        t,
        applyDOM,
        onChange,
        translations
    };
    window.t = t;

    // Run automatically when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => applyDOM());
    } else {
        applyDOM();
    }
})();
