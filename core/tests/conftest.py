"""Test setup for core/: no test may reach the network."""

import ipaddress
import socket

import pytest

@pytest.fixture(autouse=True)
def no_outbound_network(monkeypatch):
    """Fail any test that opens a non-loopback connection, so no test can reach a
    model API. Loopback stays open (Prisma talks to its local query engine)."""

    def check(address):
        host = address[0] if isinstance(address, tuple) else None  # AF_UNIX paths are local
        if host is None or host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise RuntimeError(f"tests must not use the network (tried to connect to {address!r})")

    for name in ("connect", "connect_ex"):
        def guarded(self, address, _real=getattr(socket.socket, name)):
            check(address)
            return _real(self, address)

        monkeypatch.setattr(socket.socket, name, guarded)
