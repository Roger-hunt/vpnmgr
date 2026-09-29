"""
IKEv2 Certificate model
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from .database import Base


class IKEv2Certificate(Base):
    """IKEv2 Certificate model"""
    __tablename__ = "ikev2_certificates"
    
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(100), unique=True, index=True, nullable=False)
    cert_path = Column(String(500), nullable=True)
    key_path = Column(String(500), nullable=True)
    p12_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    # Whether the exported config files require an import password
    is_protected = Column(Boolean, default=False)
    # Import password applied to the exported config files (None when unprotected).
    # ikev2.sh only keeps one password slot, so the per-certificate value has to
    # be written back before each export.
    config_password = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    def to_dict(self, include_sensitive: bool = False):
        data = {
            "id": self.id,
            "client_name": self.client_name,
            "cert_path": self.cert_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "is_protected": bool(self.is_protected),
            "description": self.description,
        }
        if include_sensitive:
            data["config_password"] = self.config_password
        return data
