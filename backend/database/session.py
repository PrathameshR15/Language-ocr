import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import settings
from backend.database.base import Base

# Engine configuration for both SQLite (async) and PostgreSQL
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("sqlite"):
    if not DATABASE_URL.startswith("sqlite+aiosqlite"):
        DATABASE_URL = DATABASE_URL.replace("sqlite", "sqlite+aiosqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
