"""
Pydantic schemas for request/response
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ========== Auth Schemas ==========

class LoginRequest(BaseModel):
    username: str
    password: str
    remember: bool = False


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


# ========== VPN User Schemas ==========

class VPNUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class VPNUserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    description: Optional[str] = None


class VPNUserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_connected_at: Optional[str] = None
    description: Optional[str] = None


# ========== Certificate Schemas ==========

class CertCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    # Optional import password for the exported config files.
    # protect_config=None falls back to the global setting.
    protect_config: Optional[bool] = None
    config_password: Optional[str] = Field(None, min_length=6, max_length=128)
    # Certificate validity in months. ikev2.sh accepts 1-120 (120 = 10 years).
    # None falls back to settings.default_cert_validity_months.
    validity_months: Optional[int] = Field(None, ge=1, le=120)


class CertResponse(BaseModel):
    id: int
    client_name: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_active: bool
    description: Optional[str] = None


# ========== Status Schemas ==========

class ConnectionInfo(BaseModel):
    tunnel: str
    id: str
    client_ip: str
    username: str


class VPNStatusResponse(BaseModel):
    container_running: bool
    active_connections: List[ConnectionInfo]
    ipsec_status: str


class SystemStatus(BaseModel):
    vpn_status: VPNStatusResponse
    total_users: int
    total_certs: int
