"""
Database configuration and session management
"""
import os
import shutil
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Ensure SQLite storage directory exists and migrate legacy root db if present
if "sqlite" in settings.database_url:
    db_file_path = settings.database_url.split(":///")[-1]
    db_dir = os.path.dirname(db_file_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    # Auto-migration: if data/vpnmgr.db does not exist yet, but legacy ./vpnmgr.db exists
    if os.path.exists("vpnmgr.db") and not os.path.exists(db_file_path) and os.path.abspath("vpnmgr.db") != os.path.abspath(db_file_path):
        try:
            shutil.copy2("vpnmgr.db", db_file_path)
            logger.info("Migrated legacy vpnmgr.db to %s", db_file_path)
        except Exception as e:
            logger.error("Failed to copy legacy vpnmgr.db to %s: %s", db_file_path, e)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables and run lightweight migrations"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Check and add OIDC columns to system_users if missing
        def migrate_system_users(connection):
            from sqlalchemy import inspect, text
            inspector = inspect(connection)
            if "system_users" in inspector.get_table_names():
                cols = [col["name"] for col in inspector.get_columns("system_users")]
                if "auth_provider" not in cols:
                    try:
                        connection.execute(text("ALTER TABLE system_users ADD COLUMN auth_provider VARCHAR(50) DEFAULT 'local'"))
                        logger.info("Migrated system_users: added auth_provider column")
                    except Exception as e:
                        logger.warning("Could not add auth_provider column: %s", e)
                if "oidc_sub" not in cols:
                    try:
                        connection.execute(text("ALTER TABLE system_users ADD COLUMN oidc_sub VARCHAR(255)"))
                        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_system_users_oidc_sub ON system_users (oidc_sub)"))
                        logger.info("Migrated system_users: added oidc_sub column and index")
                    except Exception as e:
                        logger.warning("Could not add oidc_sub column: %s", e)
        
        await conn.run_sync(migrate_system_users)
