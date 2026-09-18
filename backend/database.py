"""
HunarPath – Database engine & session configuration.

Supports two modes:
  1. PostgreSQL + pgvector (production) – when DATABASE_URL env var is set.
  2. SQLite (local dev fallback)     – automatic when DATABASE_URL is absent.
"""

from __future__ import annotations

import os
import logging
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve database URL
# ---------------------------------------------------------------------------
_DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./hunarpath_dev.db",
)

# Quick sanity: if someone passes the psycopg2 sync URL by mistake, swap driver
if _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

# Clean query params: asyncpg expects ssl=require or sslcontext rather than sslmode=require
if "asyncpg" in _DATABASE_URL:
    # Remove sslmode / channel_binding query params if present, asyncpg uses connect_args
    import re
    _DATABASE_URL = re.sub(r"[?&]channel_binding=[^&]*", "", _DATABASE_URL)
    _DATABASE_URL = re.sub(r"[?&]sslmode=[^&]*", "", _DATABASE_URL)
    # Ensure clean query string ending
    if _DATABASE_URL.endswith("?"):
        _DATABASE_URL = _DATABASE_URL[:-1]

IS_POSTGRES: bool = _DATABASE_URL.startswith("postgresql")
IS_SQLITE: bool = _DATABASE_URL.startswith("sqlite")

logger.info("Database backend: %s", "PostgreSQL+pgvector" if IS_POSTGRES else "SQLite (fallback)")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_engine_kwargs: dict = {
    "echo": os.getenv("SQL_ECHO", "0") == "1",
    "future": True,
}

if IS_POSTGRES:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(_DATABASE_URL, **_engine_kwargs)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency – yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """
    Create the pgvector extension (PostgreSQL only) and all tables.

    Call this once at application startup (e.g. in a FastAPI lifespan event).
    """
    async with engine.begin() as conn:
        if IS_POSTGRES:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension ensured.")

        # Import models so Base.metadata knows about every table
        import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
        logger.info("All tables created / verified.")


async def dispose_engine() -> None:
    """Gracefully close the connection pool."""
    await engine.dispose()
