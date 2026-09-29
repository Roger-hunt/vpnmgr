"""
VPN Connection Log model
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from .database import Base


class ConnectionLog(Base):
    """VPN Connection Log model"""
    __tablename__ = "connection_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True)  # IPsec session ID
    client_name = Column(String(100), index=True)
    username = Column(String(100), index=True)
    tunnel_type = Column(String(50))  # ikev2, l2tp, etc.
    client_ip = Column(String(50))
    assigned_ip = Column(String(50))
    status = Column(String(20), default='connected')  # connected, disconnected
    connected_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=8))))
    disconnected_at = Column(DateTime, nullable=True)
    raw_log = Column(Text)  # Store raw log for reference
    
    # Indexes for faster queries
    __table_args__ = (
        Index('idx_conn_status', 'status', 'connected_at'),
        Index('idx_conn_client', 'client_name', 'connected_at'),
        {'extend_existing': True}
    )
    
    def _format_time(self, dt):
        """Format datetime to GMT+8 string"""
        if not dt:
            return None
        from datetime import timezone, timedelta
        # If datetime is naive (no timezone), assume it's already GMT+8 (stored as naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
        # Convert to GMT+8
        gmt8 = dt.astimezone(timezone(timedelta(hours=8)))
        return gmt8.isoformat()
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "session_id": self.session_id,
            "client_name": self.client_name,
            "username": self.username,
            "tunnel_type": self.tunnel_type,
            "client_ip": self.client_ip,
            "assigned_ip": self.assigned_ip,
            "status": self.status,
            "connected_at": self._format_time(self.connected_at),
            "disconnected_at": self._format_time(self.disconnected_at),
            "raw_log": self.raw_log,
        }
