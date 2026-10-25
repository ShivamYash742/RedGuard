import socket

import pytest


def test_outbound_connections_fail_but_loopback_works():
    with pytest.raises(RuntimeError, match="must not use the network"):
        socket.create_connection(("192.0.2.1", 80), timeout=1)  # TEST-NET-1: never routable

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    socket.create_connection(server.getsockname(), timeout=1).close()
    server.close()
