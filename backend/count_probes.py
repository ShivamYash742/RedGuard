import asyncio
from scanner import _probe_groups
async def main():
    groups = await _probe_groups()
    print({cat: len(p) for cat, p in groups})
asyncio.run(main())
