"""
System User - Unified user model with VPN bindings
One system user = One VPN cert + One VPN username/password
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, UniqueConstraint
from .database import Base


class SystemUser(Base):
    """
    System user with VPN bindings
    Each system user can have:
    - One IKEv2 certificate (for certificate-based VPN)
    - One VPN username/password (for L2TP/XAuth VPN)
    """
    __tablename__ = "system_users"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Website login credentials
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)  # For web login
    
    # VPN Certificate binding (IKEv2) - One-to-One
    vpn_cert_name = Column(String(100), unique=True, nullable=True, index=True)
    
    # VPN Username/Password binding (L2TP/XAuth) - One-to-One  
    vpn_username = Column(String(100), unique=True, nullable=True, index=True)
    vpn_password = Column(String(255), nullable=True)  # Encrypted
    
    # User info
    display_name = Column(String(100))
    email = Column(String(100))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Audit
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=8))))
    last_login_at = Column(DateTime, nullable=True)
    created_by = Column(String(100))  # Who created this user
    
    # Description/notes
    description = Column(Text)
    
    __table_args__ = (
        # Ensure VPN identities are unique across users
        UniqueConstraint('vpn_cert_name', name='unique_vpn_cert'),
        UniqueConstraint('vpn_username', name='unique_vpn_username'),
    )
    
    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_by": self.created_by,
            "description": self.description,
            # VPN bindings (without sensitive data)
            "has_vpn_cert": self.vpn_cert_name is not None,
            "vpn_cert_name": self.vpn_cert_name,
            "has_vpn_user": self.vpn_username is not None,
            "vpn_username": self.vpn_username,
        }
        if include_sensitive:
            data["vpn_password"] = self.vpn_password
        return data


class UserActivityLog(Base):
    """Audit log for user VPN activities"""
    __tablename__ = "user_activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # System user info
    system_user_id = Column(Integer, index=True)
    system_username = Column(String(100), index=True)
    
    # VPN connection info
    connection_type = Column(String(20))  # 'ikev2' or 'l2tp' or 'xauth'
    vpn_identity = Column(String(100))  # cert name or vpn username
    client_ip = Column(String(50))
    assigned_vpn_ip = Column(String(50))
    session_id = Column(String(100), index=True)
    
    # Activity
    activity = Column(String(50))  # 'connected', 'disconnected', 'data_transfer'
    details = Column(Text)
    
    # Stats
    bytes_in = Column(Integer, default=0)
    bytes_out = Column(Integer, default=0)
    
    # Device info
    device_info = Column(String(255))
    
    # Timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=8))))
    
    def to_dict(self):
        return {
            "id": self.id,
            "system_user_id": self.system_user_id,
            "system_username": self.system_username,
            "connection_type": self.connection_type,
            "vpn_identity": self.vpn_identity,
            "client_ip": self.client_ip,
            "assigned_vpn_ip": self.assigned_vpn_ip,
            "session_id": self.session_id,
            "activity": self.activity,
            "details": self.details,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "device_info": self.device_info,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
