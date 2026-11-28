from __future__ import annotations

import sys
from threading import Lock
from typing import Any, Literal

from mcp.server import MCPServer

try:
    from .client import CKN_INSTRUCTIONS, CKN_ONLY_POLICY, DIPPER_INSTRUCTIONS, CellKgClient, connect_arango
except ImportError:
    if __package__:
        raise
    from client import CKN_INSTRUCTIONS, CKN_ONLY_POLICY, DIPPER_INSTRUCTIONS, CellKgClient, connect_arango

DIPPER_OPTIONS = DIPPER_INSTRUCTIONS + "\n\nPARAMETERS AND RESULT FORMAT:\n" + """
arm_kind is cell_type, cell_set, or both (default). These are distinct arms:
GS-CL-UBERON versus GS-CS-CSD-UBERON. The CS arm REQUIRES the dataset node.
Dataset-to-tissue evidence is dataset-level context, not a direct CS-tissue edge.
node_ids optionally maps gene, cell_type, cell_set, dataset, anatomy, disease, protein, chemical to
lists of exact CKN _ids. Gene IDs are the most efficient starting constraint.
Supplying only cell_type IDs narrows to that arm; cell_set/dataset IDs narrow
to the CS arm. With both types of arm IDs, search each independently. Dataset
constraints apply only to the CS branch. No CS-CL equivalence is assumed.
role_collections optionally overrides those roles with collection-name lists;
defaults: GS, CL, CS, CSD, UBERON, MONDO, PR, CHEMBL respectively.
relation_rules maps gene_cell_type, cell_type_anatomy, cell_type_cell_type,
gene_cell_set, cell_set_dataset, dataset_anatomy, gene_disease, gene_protein,
protein_chemical, chemical_disease to optional rules:
{\"direction\": \"ANY\", \"field\": \"actual_attribute_name\", \"values\": [\"actual_CKN_value\"]}.
field may also be a list of nested attribute keys. field and values are paired.
Directions are relative to the role order in the rule name. Default ANY.
Absent predicate filters use the user's current convention: each relevant
role pair has one relation type, so the edges establish its meaning.
When additional relations appear, configure filters from CKN edge records.
Defaults can be set in client.py's DEFAULT_RELATION_RULES; per-call entries
replace the default for that connection. An empty entry restores ANY/no filter.
max_hops optionally maps non-closing path names to 1..3. Default 1, except
cell_type_anatomy defaults to 3 and permits only CL-role intermediate nodes.
cell_type_cell_type is a step rule, not a separate max_hops path name.
For CL-to-tissue paths, cell_type_cell_type rules apply to intermediate CL-CL
steps and cell_type_anatomy rules apply to the final CL-UBERON step.
Other predicate filters apply to every edge on their configured path. Longer paths
are explicitly marked as extended topology candidates, not direct relations.
The chemical_disease closing connection is always one direct edge to the
same disease already connected to the gene. Its absence is checked against
ALL accessible non-system edge collections, without an early candidate cap.
Results include all node attributes, actual edge records and directions,
the search scope, and explicit truncation. Parallel evidence paths may give
multiple rows for the same entities. CL matches have six role nodes; CS matches
have seven, including dataset. Every result has arm_kind and distinctly named
cell_type or cell_set node/path entries. Preserve these node/path identities.
For gene-disease findings, every valid path with the same gene _id and disease
_id is duplicate support for ONE relation, across arms, datasets, tissues,
proteins, chemicals, and full/bottomless result sets. Path multiplicity is not
independent evidence or a count of distinct gene-disease relations.
Use gene_disease_key to deduplicate across pages and calls. The returned
gene_disease_groups and unique_gene_disease_count_in_page describe this page
only. Retain paths for provenance; do not claim a database-wide count from a page.
limit is 1..20, default 5; offset pages
over evidence paths. Prefer targeted IDs to unbounded whole-database searches.
""".strip()


def create_server(database) -> MCPServer:
    client = CellKgClient(database)
    lock = Lock()
    mcp = MCPServer("cell-kn-aql", instructions=CKN_INSTRUCTIONS)

    @mcp.tool(description=CKN_ONLY_POLICY + "\n\nReturn the cached collection catalog. "
              "Use for introductory questions, not before every specific query.")
    def get_ckn_overview() -> dict[str, Any]:
        with lock:
            return client.overview()

    @mcp.tool(description=CKN_ONLY_POLICY + "\n\nExplicitly refresh collection names/types "
              "for this server session. Does not scan documents or attributes.")
    def refresh_ckn_catalog() -> dict[str, Any]:
        with lock:
            return client.refresh_catalog()

    @mcp.tool(description=CKN_ONLY_POLICY + "\n\nExecute targeted AQL against the CKN. "
              "No prior discovery is required. Use bind variables and LIMIT. "
              "At most 20 rows are returned; truncated indicates more rows.")
    def run_aql(query: str, bind_vars: dict[str, Any] | None = None) -> dict[str, Any]:
        with lock:
            return client.run_aql(query, bind_vars)

    @mcp.tool(description=CKN_ONLY_POLICY + "\n\nFind full/complete big dippers "
              "(also full dipper / complete dipper), including the direct "
              "chemical-disease closing edge.\n" + DIPPER_OPTIONS)
    def find_full_dippers(
        node_ids: dict[str, list[str]] | None = None,
        role_collections: dict[str, list[str]] | None = None,
        relation_rules: dict[str, dict[str, Any]] | None = None,
        max_hops: dict[str, int] | None = None,
        limit: int = 5, offset: int = 0,
        arm_kind: Literal["cell_type", "cell_set", "both"] = "both",
    ) -> dict[str, Any]:
        with lock:
            return client.find_dippers(
                "full", node_ids, role_collections, relation_rules, max_hops, limit, offset,
                arm_kind=arm_kind,
            )

    @mcp.tool(description=CKN_ONLY_POLICY + "\n\nFind bottomless/incomplete/broken "
              "big dippers (also bottomless/incomplete/broken dipper). Require "
              "the selected typed arm and shared dipper connections, plus absence of the direct closing "
              "chemical-disease relation. These are CKN repurposing hypotheses, "
              "not established treatment claims.\n" + DIPPER_OPTIONS)
    def find_bottomless_dippers(
        node_ids: dict[str, list[str]] | None = None,
        role_collections: dict[str, list[str]] | None = None,
        relation_rules: dict[str, dict[str, Any]] | None = None,
        max_hops: dict[str, int] | None = None,
        limit: int = 5, offset: int = 0,
        arm_kind: Literal["cell_type", "cell_set", "both"] = "both",
    ) -> dict[str, Any]:
        with lock:
            return client.find_dippers(
                "bottomless", node_ids, role_collections, relation_rules, max_hops, limit, offset,
                arm_kind=arm_kind,
            )

    return mcp


def main() -> None:
    driver, database = connect_arango()
    try:
        mcp = create_server(database)
        print(f"Connected to {database.name}. MCP: http://127.0.0.1:8000/mcp",
              file=sys.stderr, flush=True)
        mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
