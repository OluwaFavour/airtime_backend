from contextlib import asynccontextmanager

from app.db.config import client


@asynccontextmanager
async def get_session_context():
    """
    Context manager to handle session lifecycle.

    Yields:
        AsyncSession: An instance of AsyncSession for database operations.
    """
    async with client.start_session() as session:
        yield session
