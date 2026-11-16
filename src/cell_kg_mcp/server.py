from __future__ import annotations

import sys
from itertools import islice
from threading import Lock
from typing import Any

from mcp.server import MCPServer

from client import connect_arango

MAX_ROWS = 20


def main() -> None:
    driver, database = connect_arango()

    try:
        mcp = MCPServer("cell-kn-aql")
        query_lock = Lock()

        @mcp.tool()
        def run_aql(
            query: str,
            bind_vars: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Execute AQL

            Start with RETURN 1 to test the connection.
            Optional bind_vars supplies AQL bind parameters.
            At most 20 result rows are returned. Include an AQL LIMIT
            when reading collections to limit the query's own work.
            """
            if not query.strip():
                raise ValueError("query must not be empty.")

            with query_lock:
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
