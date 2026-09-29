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
    description = Column(Text, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "cert_path": self.cert_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "description": self.description,
        }
