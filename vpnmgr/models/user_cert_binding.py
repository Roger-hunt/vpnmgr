"""
User Certificate Binding - Maps admin user to VPN certificate with audit logging
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, UniqueConstraint, Index
from .database import Base


class UserCertBinding(Base):
    """Stores binding between admin user and VPN certificate"""
    __tablename__ = "user_cert_bindings"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, index=True)  # Admin username
    cert_name = Column(String(100), nullable=False, index=True)  # VPN certificate CN
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=8))))
    assigned_by = Column(String(100))  # Who assigned this binding
    is_active = Column(Boolean, default=True)
    description = Column(String(255))
    
    # One cert can only bind to one user
    __table_args__ = (
        UniqueConstraint('cert_name', name='unique_cert_binding'),
        Index('idx_user_cert', 'username', 'cert_name'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "cert_name": self.cert_name,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "assigned_by": self.assigned_by,
            "is_active": self.is_active,
            "description": self.description,
        }


class CertUsageLog(Base):
    """Audit log for certificate usage - tracks when and who used the cert"""
    __tablename__ = "cert_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    cert_name = Column(String(100), nullable=False, index=True)
    username = Column(String(100), nullable=True)  # Bound user (if any)
    client_ip = Column(String(50))  # Public IP
    assigned_vpn_ip = Column(String(50))  # VPN assigned IP
    session_id = Column(String(100), index=True)  # IPsec session ID
    connected_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=8))))
    disconnected_at = Column(DateTime, nullable=True)
    bytes_in = Column(Integer, default=0)
    bytes_out = Column(Integer, default=0)
    device_info = Column(String(255))  # User-Agent or device fingerprint
    
    # Indexes for queries
    __table_args__ = (
        Index('idx_cert_usage', 'cert_name', 'connected_at'),
        Index('idx_session', 'session_id', 'connected_at'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "cert_name": self.cert_name,
            "username": self.username,
            "client_ip": self.client_ip,
            "assigned_vpn_ip": self.assigned_vpn_ip,
            "session_id": self.session_id,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "device_info": self.device_info,
        }
