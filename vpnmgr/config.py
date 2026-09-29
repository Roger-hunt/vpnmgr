"""
VPN Manager Configuration
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Admin credentials
    admin_username: str = "admin"
    admin_password: str = "admin123"
    
    # Security
    secret_key: str = "change-me-in-production"
    
    # Docker
    vpn_container_name: str = "ipsec-vpn-server"
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/vpnmgr.db"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    
    # Optional LAN health check probe (configurable, default disabled)
    lan_check_host: str = ""
    lan_check_port: int = 0
    app_title: str = "VPN Manager"
    
    # VPN env file path (optional)
    vpn_env_file: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
