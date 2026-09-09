import asyncio
from backend.database import get_db, init_db, close_db

async def main():
    await init_db()
    prisma = await get_db()
    events = await prisma.probeevent.find_many(
        order={"timestamp": "desc"},
        take=20
    )
    for ev in events:
        if ev.status == "ALLOWED" or ev.status == "BLOCKED":
            print(f"[{ev.status}] regex={ev.regexVerdict} | resp={ev.responseExcerpt[:100]}")
    await close_db()

asyncio.run(main())
