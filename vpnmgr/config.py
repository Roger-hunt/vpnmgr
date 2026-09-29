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

    # VPN client network (IKEv2 assigned subnet)
    vpn_subnet: str = "192.168.43.0/24"
    
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
    
    # OIDC / SSO Configuration
    oidc_enabled: bool = False
    oidc_issuer_url: str = ""        # e.g., https://sso.example.com
    oidc_client_id: str = ""         # Client ID
    oidc_client_secret: str = ""     # Client Secret
    oidc_redirect_uri: str = ""      # e.g., http://<host>:8080/api/auth/sso/callback
    oidc_scopes: str = "openid profile email"
    oidc_provider_name: str = "SSO 单点登录"
    oidc_auto_create_user: bool = True  # Automatically provision user on first login

    @property
    def is_oidc_active(self) -> bool:
        return self.oidc_enabled or bool(self.oidc_issuer_url and self.oidc_client_id)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
