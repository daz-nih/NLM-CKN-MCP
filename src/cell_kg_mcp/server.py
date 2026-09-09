from __future__ import annotations

from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from .client import DEFAULT_SEARCH_FIELDS, EDGE_DIRECTIONS, CellKgSearchClient

mcp = MCPServer("cell-kg-search")
client = CellKgSearchClient()


def _compact_result(item: dict[str, Any]) -> dict[str, Any]:
    # Keep the highest-value fields compact for LLM context size.
    keys = [
        "_id",
        "_key",
        "label",
        "author_cell_term",
        "markers",
        "definition",
        "comment",
        "description",
        "hasExactSynonym",
        "exact_synonym",
    ]
    compact = {k: item[k] for k in keys if k in item}
    if not compact:
        compact = item
    return compact

def _compact_link(link: dict[str, Any]) -> dict[str, Any]:
    keys = ["_from", "_to", "Label", "Source"]
    return {k: link[k] for k in keys if k in link}

@mcp.tool()
def search_cell_kn(
    query: str,
    db: Literal["phenotypes", "ontologies"] = "phenotypes",
    limit: int = 10,
    search_fields: list[str] | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Search the NLM Cell Knowledge Network via https://stage.nlm-ckn.org/arango_api/search/."""
    results = client.search(
        query=query,
        db=db,
        search_fields=search_fields,
        limit=limit,
    )

    compact_results = [_compact_result(item) for item in results]
    payload: dict[str, Any] = {
        "query": query,
        "db": db,
        "count": len(results),
        "results": compact_results,
        "default_search_fields": DEFAULT_SEARCH_FIELDS[db],
    }
    if include_raw:
        payload["raw_results"] = results
    return payload


@mcp.tool()
def get_cell_kn_search_defaults() -> dict[str, list[str]]:
    """Return supported graph databases and the default search fields."""
    return DEFAULT_SEARCH_FIELDS

@mcp.tool()
def list_cell_kn_collections() -> dict[str, list[str]]:
    """List available graph collections / ontology prefixes (CL, GO, UBERON, …).
    Use these values for the `allowed_collections` argument of `get_cell_kn_neighbors`.
    """
    return {"collections": client.collections()}


@mcp.tool()
def get_cell_kn_neighbors(
    node_ids: list[str] | str,
    depth: int = 1,
    edge_direction: Literal["ANY", "OUTBOUND", "INBOUND"] = "ANY",
    allowed_collections: list[str] | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Explore the knowledge graph around one or more nodes.

    Pass node `_id`s obtained from `search_cell_kn` (e.g. "CL/0000084").
    `depth` must be >= 1. `edge_direction` is ANY / OUTBOUND / INBOUND (uppercase).
    Returns compacted nodes and links per queried id.
    """
    raw = client.graph(
        node_ids=node_ids,
        depth=depth,
        edge_direction=edge_direction,
        allowed_collections=allowed_collections,
    )
    summary: dict[str, Any] = {}
    for nid, payload in raw.items():
        nodes = payload.get("nodes", [])
        links = payload.get("links", [])
        summary[nid] = {
            "node_count": len(nodes),
            "link_count": len(links),
            "nodes": [_compact_result(n) for n in nodes],
            "links": [_compact_link(l) for l in links],
        }
    out: dict[str, Any] = {
        "depth": depth,
        "edge_direction": edge_direction,
        "results": summary,
    }
    if include_raw:
        out["raw_results"] = raw
    return out


@mcp.tool()
def get_cell_kn_node(node_id: str, include_raw: bool = False) -> dict[str, Any]:
    """Fetch a single node's full record by `_id` (e.g. "CL/0000084").
    Returns `{"found": false}` if the id is not present.
    """
    node = client.get_node(node_id)
    if node is None:
        return {"found": False, "node_id": node_id}
    out: dict[str, Any] = {"found": True, "node_id": node_id, "node": _compact_result(node)}
    if include_raw:
        out["raw_node"] = node
    return out

def main() -> None:
    """Run the MCP server.

    Transport is chosen by the MCP_TRANSPORT env var:
      - unset / "stdio"  -> local stdio (Claude Desktop, Claude Code). Default.
      - "http"           -> Streamable HTTP for remote/web hosting (claude.ai).
                            Serves the MCP endpoint at /mcp on HOST:PORT.
                            HOST defaults to 0.0.0.0; PORT defaults to 8000
                            (cloud hosts like Render/Railway inject PORT).
    """
    import os

    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport in ("http", "streamable-http"):
        from mcp.server.transport_security import TransportSecuritySettings

        mcp.settings.host = os.environ.get("HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("PORT", "8000"))

        # MCPServer auto-enables DNS-rebinding protection with a LOCALHOST-only
        # allow-list (it's constructed while host is still 127.0.0.1). Behind a
        # managed HTTPS host (Render/AWS) the incoming Host header is the public
        # domain, which that policy rejects with HTTP 421 "Invalid Host header".
        # Override it here:
        #   - MCP_ALLOWED_HOSTS set  -> keep protection on, trust those hosts
        #     (comma-separated, e.g. "nlm-ckn-mcp.onrender.com").
        #   - unset (default)        -> disable it; safe here because the server
        #     is public, read-only, and sits behind the host's HTTPS proxy.
        allowed = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()
        if allowed:
            hosts = [h.strip() for h in allowed.split(",") if h.strip()]
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=hosts,
                allowed_origins=[f"https://{h}" for h in hosts],
            )
        else:
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            )

        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
