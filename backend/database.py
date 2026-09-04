import os
from pathlib import Path
from dotenv import load_dotenv
from prisma import Prisma

# Load environment variables
_root_env = Path(__file__).resolve().parent.parent / ".env"
_backend_env = Path(__file__).resolve().parent / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env)
elif _backend_env.exists():
    load_dotenv(dotenv_path=_backend_env)
else:
    load_dotenv()

# Global prisma client
prisma = Prisma()

async def init_db():
    """Initialize the database connection."""
    if not prisma.is_connected():
        await prisma.connect()

async def close_db():
    """Close the database connection."""
    if prisma.is_connected():
        await prisma.disconnect()

async def get_db():
    """Dependency to get the database client."""
    if not prisma.is_connected():
        await init_db()
    return prisma

