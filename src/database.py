from sqlalchemy.ext.asyncio import create_async_engine
from src.load_secrets import user, password, host, port, db_name

POSTGRES_DATABASE_URL = (
    f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
)

engine = create_async_engine(POSTGRES_DATABASE_URL, pool_size=20, max_overflow=20)

