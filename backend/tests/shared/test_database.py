"""OPS-01: shutting down must not hang on a query engine that ignores SIGINT."""

import asyncio
import time

import pytest

import database


class _StuckPrisma:
    def is_connected(self):
        return True

    async def disconnect(self):
        await asyncio.Event().wait()        # never returns, like Prisma's _kill_process under `cmd &`


@pytest.mark.asyncio
async def test_close_db_gives_up_on_a_disconnect_that_never_returns(monkeypatch):
    monkeypatch.setattr(database, "prisma", _StuckPrisma())
    monkeypatch.setattr(database, "DISCONNECT_TIMEOUT", 0.05)
    started = time.monotonic()
    await database.close_db()
    assert time.monotonic() - started < 2
