from __future__ import annotations

from typing import Any

from mcp import Client
from mcp.server import MCPServer

mcp = MCPServer("cell-kn-aql-test")
SERVER_URL = "http://127.0.0.1:8000/mcp"


@mcp.tool()
async def run_aql(
    query: str,
    bind_vars: dict[str, Any] | None = None,
):
    """Execute AQL against Cell-KN-Phenotypes through the local server."""
    async with Client(SERVER_URL) as connection:
        return await connection.call_tool(
            "run_aql",
            {"query": query, "bind_vars": bind_vars},
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
