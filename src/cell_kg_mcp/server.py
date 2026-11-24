from __future__ import annotations

import sys
from copy import deepcopy
from itertools import islice
from threading import Lock
from typing import Any

from mcp.server import MCPServer

from client import (
    CKN_INSTRUCTIONS,
    OVERVIEW_DESCRIPTION,
    REFRESH_DESCRIPTION,
    RUN_AQL_DESCRIPTION,
    build_catalog,
    connect_arango,
)

MAX_ROWS = 20


def create_server(database) -> MCPServer:
    mcp = MCPServer(
        "cell-kn-aql",
        instructions=CKN_INSTRUCTIONS,
    )

    lock = Lock()

    # Use the bundled catalog immediately.
    # No live collection discovery or document sampling at startup.
    catalog = build_catalog()

    @mcp.tool(description=OVERVIEW_DESCRIPTION)
    def get_ckn_overview() -> dict[str, Any]:
        with lock:
            return deepcopy(catalog)

    @mcp.tool(description=REFRESH_DESCRIPTION)
    def refresh_ckn_catalog() -> dict[str, Any]:
        nonlocal catalog

        with lock:
            # Assign only after the metadata request succeeds.
            refreshed = build_catalog(database.collections())
            catalog = refreshed
            return deepcopy(catalog)

    @mcp.tool(description=RUN_AQL_DESCRIPTION)
    def run_aql(
        query: str,
        bind_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query must not be empty.")

        with lock:
            with database.aql.execute(
                query,
                bind_vars=bind_vars,
                max_runtime=10,
                memory_limit=32 * 1024 * 1024,
                batch_size=MAX_ROWS + 1,
                fail_on_warning=True,
            ) as cursor:
                rows = list(islice(cursor, MAX_ROWS + 1))

        return {
            "database": database.name,
            "results": rows[:MAX_ROWS],
            "truncated": len(rows) > MAX_ROWS,
        }

    return mcp


def main() -> None:
    driver, database = connect_arango()

    try:
        mcp = create_server(database)

        print(
            f"Connected to {database.name}. "
            "Starting MCP at http://127.0.0.1:8000/mcp",
            file=sys.stderr,
            flush=True,
        )

        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8000,
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
