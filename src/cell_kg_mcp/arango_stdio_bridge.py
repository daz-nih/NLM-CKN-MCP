from __future__ import annotations

import anyio

from mcp.client.streamable_http import streamable_http_client
from mcp.server.stdio import stdio_server

SERVER_URL = "http://127.0.0.1:8000/mcp"


async def relay(source, destination, cancel_scope) -> None:
    try:
        async for message in source:
            if isinstance(message, Exception):
                raise message
            await destination.send(message)
    finally:
        cancel_scope.cancel()


async def main() -> None:
    async with stdio_server() as (desktop_read, desktop_write):
        async with streamable_http_client(SERVER_URL) as streams:
            server_read, server_write = streams[:2]

            async with anyio.create_task_group() as tasks:
                tasks.start_soon(
                    relay,
                    desktop_read,
                    server_write,
                    tasks.cancel_scope,
                )
                tasks.start_soon(
                    relay,
                    server_read,
                    desktop_write,
                    tasks.cancel_scope,
                )


if __name__ == "__main__":
    anyio.run(main)
