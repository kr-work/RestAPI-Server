from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.create_postgres_engine import engine

# Centralized session factory to avoid creating it in router modules.
Session = async_sessionmaker(
    autocommit=False,
    class_=AsyncSession,
    autoflush=True,
    bind=engine,
)
