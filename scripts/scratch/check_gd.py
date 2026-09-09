import asyncio
from scanner import _probe_groups
async def main():
    groups = await _probe_groups()
    gd = [p for cat, p in groups if cat == 'GOAL_DIVERSION'][0]
    for p in gd: print(repr(p))
asyncio.run(main())
