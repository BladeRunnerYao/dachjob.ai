from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def get_async_database_url(settings=None):
    if settings is None:
        settings = get_settings()
    if settings.cloud_sql_connection_name and settings.database_password:
        return URL.create(
            "postgresql+asyncpg",
            username=settings.database_user,
            password=settings.database_password,
            database=settings.database_name,
            query={"host": f"/cloudsql/{settings.cloud_sql_connection_name}"},
        )
    return settings.database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")


def get_engine():
    async_url = get_async_database_url()
    return create_async_engine(
        async_url,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


engine = get_engine()
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
