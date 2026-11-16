from itertools import islice
from threading import Lock
from typing import Any

from mcp.server import MCPServer

from client import connect_arango


def main() -> None:
    driver, database = connect_arango("Cell-KN-Phenotypes")

    try:
        mcp = MCPServer("cell-kn-aql-test")
        query_lock = Lock()

        @mcp.tool()
        def run_aql(query: str) -> dict[str, Any]:
            """Execute a short AQL query against Cell-KN-Phenotypes.

            Start with RETURN 1 to test connectivity.
            Include LIMIT when querying collections.
            Returns at most 20 rows.
            """
            with query_lock:
                cursor = database.aql.execute(
                    query,
                    max_runtime=10,
                    memory_limit=32 * 1024 * 1024,
                    batch_size=21,
                )
                try:
                    rows = list(islice(cursor, 21))
                finally:
                    cursor.close()

            return {
                "database": database.name,
                "results": rows[:20],
                "truncated": len(rows) > 20,
            }

        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8000,
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
