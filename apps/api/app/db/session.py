from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    settings = get_settings()
    async_url = settings.database_url.replace(
        "postgresql+psycopg://", "postgresql+asyncpg://"
    )
    return create_async_engine(
        async_url,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


engine = get_engine()
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
