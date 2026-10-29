import asyncio
import logging

from prisma import Prisma

logger = logging.getLogger(__name__)

#: Seconds to wait for the query engine to stop. Prisma ends it with SIGINT and waits with no limit;
#: a process started with `&` in a non-interactive shell has SIGINT ignored, so disconnect() never returned.
DISCONNECT_TIMEOUT = 5

# Global prisma client
prisma = Prisma()

async def init_db():
    """Initialize the database connection."""
    if not prisma.is_connected():
        await prisma.connect()

async def close_db():
    """Close the database connection."""
    if prisma.is_connected():
        try:
            await asyncio.wait_for(prisma.disconnect(), timeout=DISCONNECT_TIMEOUT)
        except Exception as exc:  # TimeoutError included: the process is exiting, the engine goes with it
            logger.warning("prisma disconnect did not finish cleanly: %r", exc)

async def get_db():
    """Dependency to get the database client."""
    if not prisma.is_connected():
        await init_db()
    return prisma
