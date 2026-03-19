"""research-neo4j → AuraDB バックアップ移行スクリプト.

.mcp.json から接続情報を自動読み取りし、ローカルの research-neo4j データを
AuraDB に MERGE ベースで冪等に転送する。

Usage:
    uv run --with neo4j python .claude/skills/backup-auradb/scripts/migrate_to_aura.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

# ノードラベルと主キーのマッピング
LABEL_KEYS: dict[str, str] = {
    "Entity": "entity_id",
    "Source": "source_id",
    "Claim": "claim_id",
    "Chunk": "chunk_id",
    "Fact": "fact_id",
    "FinancialDataPoint": "datapoint_id",
    "Topic": "topic_id",
    "Insight": "insight_id",
    "Author": "author_id",
    "Stance": "stance_id",
    "FiscalPeriod": "period_id",
    "Metric": "metric_id",
    "Sector": "name",
}

# バックアップ対象外のラベル
EXCLUDE_LABELS = {"Memory", "Implementation"}

BATCH_SIZE = 100


def load_connection_config() -> tuple[dict, dict]:
    """Load connection config from .mcp.json."""
    mcp_path = Path(".mcp.json")
    if not mcp_path.exists():
        # フォールバック: プロジェクトルートから探す
        for p in [Path("/Users/yukihata/Desktop/note-finance/.mcp.json")]:
            if p.exists():
                mcp_path = p
                break

    if not mcp_path.exists():
        print("ERROR: .mcp.json not found", file=sys.stderr)
        sys.exit(1)

    with open(mcp_path) as f:
        mcp = json.load(f)

    servers = mcp.get("mcpServers", {})

    def extract_config(server_name: str) -> dict:
        server = servers[server_name]
        args = server["args"]
        config = {}
        for i, arg in enumerate(args):
            if arg == "--db-url" and i + 1 < len(args):
                config["uri"] = args[i + 1]
            elif arg == "--username" and i + 1 < len(args):
                config["username"] = args[i + 1]
            elif arg == "--password" and i + 1 < len(args):
                config["password"] = args[i + 1]
            elif arg == "--database" and i + 1 < len(args):
                config["database"] = args[i + 1]
        return config

    local = extract_config("neo4j-research")
    aura = extract_config("neo4j-aura")
    return local, aura


def ensure_constraints(aura_driver: object, database: str) -> None:
    """Create unique constraints on AuraDB if they don't exist."""
    constraints = [
        ("Entity", "entity_id"),
        ("Source", "source_id"),
        ("Claim", "claim_id"),
        ("Chunk", "chunk_id"),
        ("Fact", "fact_id"),
        ("FinancialDataPoint", "datapoint_id"),
        ("Topic", "topic_id"),
        ("Insight", "insight_id"),
        ("Author", "author_id"),
        ("Stance", "stance_id"),
        ("FiscalPeriod", "period_id"),
        ("Metric", "metric_id"),
        ("Sector", "name"),
    ]

    with aura_driver.session(database=database) as session:
        for label, prop in constraints:
            try:
                constraint_name = f"{label.lower()}_{prop}_unique"
                session.run(
                    f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                )
            except Exception:
                pass  # Constraint might already exist

    print("  Constraints ensured")


def get_local_stats(driver: object, database: str) -> dict:
    """Get node/rel counts from local DB."""
    with driver.session(database=database) as session:
        result = session.run(
            "MATCH (n) RETURN count(n) AS nodes"
        )
        nodes = result.single()["nodes"]
        result = session.run(
            "MATCH ()-[r]->() RETURN count(r) AS rels"
        )
        rels = result.single()["rels"]

        # Label counts
        result = session.run(
            "MATCH (n) UNWIND labels(n) AS l "
            "RETURN l, count(n) AS cnt ORDER BY cnt DESC"
        )
        labels = {r["l"]: r["cnt"] for r in result}

    return {"nodes": nodes, "rels": rels, "labels": labels}


def migrate_nodes(local_driver, aura_driver, local_db: str, aura_db: str) -> dict:
    """Migrate all nodes from local to AuraDB."""
    stats: dict[str, int] = {}

    with local_driver.session(database=local_db) as session:
        result = session.run("CALL db.labels()")
        labels = [r["label"] for r in result]

    for label in labels:
        if label in EXCLUDE_LABELS:
            continue

        # Read from local
        with local_driver.session(database=local_db) as session:
            result = session.run(
                f"MATCH (n:{label}) RETURN properties(n) AS props"
            )
            nodes = [dict(r["props"]) for r in result]

        if not nodes:
            continue

        pk = LABEL_KEYS.get(label)

        # Batch write to AuraDB
        written = 0
        for i in range(0, len(nodes), BATCH_SIZE):
            batch = nodes[i : i + BATCH_SIZE]

            with aura_driver.session(database=aura_db) as session:
                if pk and all(pk in p for p in batch):
                    query = (
                        f"UNWIND $items AS item "
                        f"MERGE (n:{label} {{{pk}: item.{pk}}}) "
                        f"SET n = item"
                    )
                else:
                    query = (
                        f"UNWIND $items AS item "
                        f"CREATE (n:{label}) "
                        f"SET n = item"
                    )
                session.run(query, items=batch)
                written += len(batch)

        stats[label] = written
        print(f"  {label}: {written}")

    return stats


def migrate_relationships(
    local_driver, aura_driver, local_db: str, aura_db: str
) -> dict:
    """Migrate all relationships from local to AuraDB."""
    stats: dict[str, int] = {}

    with local_driver.session(database=local_db) as session:
        result = session.run(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN relationshipType"
        )
        rel_types = [r["relationshipType"] for r in result]

    # Build CASE expression for key lookup
    case_expr = "\n".join(
        f"WHEN '{label}' IN labels(node) THEN node.{pk}"
        for label, pk in LABEL_KEYS.items()
    )
    label_list = str(list(LABEL_KEYS.keys()))

    for rel_type in rel_types:
        with local_driver.session(database=local_db) as session:
            query = f"""
                MATCH (a)-[r:{rel_type}]->(b)
                WITH a, r, b, labels(a) AS a_labels, labels(b) AS b_labels,
                     properties(r) AS r_props
                WITH a, r, b, a_labels, b_labels, r_props,
                     [l IN a_labels WHERE l IN {label_list} | l][0] AS a_label,
                     [l IN b_labels WHERE l IN {label_list} | l][0] AS b_label
                WHERE a_label IS NOT NULL AND b_label IS NOT NULL
                WITH a_label, b_label,
                     CASE {case_expr.replace("node", "a")} END AS a_key,
                     CASE {case_expr.replace("node", "b")} END AS b_key,
                     r_props
                WHERE a_key IS NOT NULL AND b_key IS NOT NULL
                RETURN a_label, a_key, b_label, b_key, r_props
            """
            result = session.run(query)
            rels = [
                {
                    "a_label": r["a_label"],
                    "a_key": r["a_key"],
                    "b_label": r["b_label"],
                    "b_key": r["b_key"],
                    "props": dict(r["r_props"]) if r["r_props"] else {},
                }
                for r in result
            ]

        if not rels:
            continue

        # Group by label pair
        groups: dict[tuple[str, str], list] = {}
        for rel in rels:
            key = (rel["a_label"], rel["b_label"])
            groups.setdefault(key, []).append(rel)

        total_written = 0
        for (a_label, b_label), group_rels in groups.items():
            a_pk = LABEL_KEYS.get(a_label, "name")
            b_pk = LABEL_KEYS.get(b_label, "name")

            for i in range(0, len(group_rels), BATCH_SIZE):
                batch = group_rels[i : i + BATCH_SIZE]
                items = [
                    {"a_key": r["a_key"], "b_key": r["b_key"], "props": r["props"]}
                    for r in batch
                ]

                write_query = (
                    f"UNWIND $items AS item "
                    f"MATCH (a:{a_label} {{{a_pk}: item.a_key}}) "
                    f"MATCH (b:{b_label} {{{b_pk}: item.b_key}}) "
                    f"CREATE (a)-[r:{rel_type}]->(b) "
                    f"SET r = item.props"
                )

                with aura_driver.session(database=aura_db) as session:
                    try:
                        session.run(write_query, items=items)
                        total_written += len(batch)
                    except Exception as e:
                        print(f"    WARN {rel_type} ({a_label}->{b_label}): {e}")

        stats[rel_type] = total_written
        print(f"  {rel_type}: {total_written}")

    return stats


def clear_auradb(aura_driver, aura_db: str) -> None:
    """Clear all data from AuraDB before fresh backup."""
    print("  Clearing existing AuraDB data...")
    with aura_driver.session(database=aura_db) as session:
        # Delete in batches to avoid memory issues
        while True:
            result = session.run(
                "MATCH ()-[r]->() WITH r LIMIT 5000 DELETE r RETURN count(r) AS cnt"
            )
            cnt = result.single()["cnt"]
            if cnt == 0:
                break

        while True:
            result = session.run(
                "MATCH (n) WITH n LIMIT 5000 DETACH DELETE n RETURN count(n) AS cnt"
            )
            cnt = result.single()["cnt"]
            if cnt == 0:
                break

    print("  Cleared")


def verify(aura_driver, aura_db: str) -> dict:
    """Verify AuraDB data after migration."""
    with aura_driver.session(database=aura_db) as session:
        result = session.run("MATCH (n) RETURN count(n) AS cnt")
        node_cnt = result.single()["cnt"]
        result = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
        rel_cnt = result.single()["cnt"]

        result = session.run(
            "MATCH (n) UNWIND labels(n) AS l "
            "RETURN l, count(n) AS cnt ORDER BY cnt DESC"
        )
        labels = {r["l"]: r["cnt"] for r in result}

    return {"nodes": node_cnt, "rels": rel_cnt, "labels": labels}


def main() -> None:
    """Run the migration."""
    print("=" * 50)
    print("research-neo4j -> AuraDB Backup")
    print("=" * 50)

    # Load config
    local_cfg, aura_cfg = load_connection_config()

    local_driver = GraphDatabase.driver(
        local_cfg["uri"], auth=(local_cfg["username"], local_cfg["password"])
    )
    aura_driver = GraphDatabase.driver(
        aura_cfg["uri"], auth=(aura_cfg["username"], aura_cfg["password"])
    )

    local_db = local_cfg["database"]
    aura_db = aura_cfg["database"]

    try:
        # Phase 1: Connection test
        print("\n[1/5] Connection test...")
        local_driver.verify_connectivity()
        print("  Local (research-neo4j): OK")
        aura_driver.verify_connectivity()
        print("  AuraDB: OK")

        # Get local stats
        local_stats = get_local_stats(local_driver, local_db)
        print(f"  Local: {local_stats['nodes']} nodes, {local_stats['rels']} rels")

        # Phase 2: Clear AuraDB (fresh backup)
        print("\n[2/5] Clear AuraDB...")
        clear_auradb(aura_driver, aura_db)

        # Phase 3: Ensure constraints
        print("\n[3/5] Ensure constraints...")
        ensure_constraints(aura_driver, aura_db)

        # Phase 4: Migrate nodes
        print("\n[4/5] Migrating nodes...")
        t0 = time.time()
        node_stats = migrate_nodes(local_driver, aura_driver, local_db, aura_db)
        node_time = time.time() - t0
        total_nodes = sum(node_stats.values())
        print(f"  Total: {total_nodes} nodes in {node_time:.1f}s")

        # Phase 5: Migrate relationships
        print("\n[5/5] Migrating relationships...")
        t0 = time.time()
        rel_stats = migrate_relationships(local_driver, aura_driver, local_db, aura_db)
        rel_time = time.time() - t0
        total_rels = sum(rel_stats.values())
        print(f"  Total: {total_rels} rels in {rel_time:.1f}s")

        # Verification
        print("\n--- Verification ---")
        aura_stats = verify(aura_driver, aura_db)

        excluded_count = sum(
            local_stats["labels"].get(l, 0) for l in EXCLUDE_LABELS
        )
        expected_nodes = local_stats["nodes"] - excluded_count

        print(f"\n  Local:  {local_stats['nodes']} nodes, {local_stats['rels']} rels")
        print(f"  AuraDB: {aura_stats['nodes']} nodes, {aura_stats['rels']} rels")
        print(f"  Excluded: {excluded_count} nodes ({', '.join(EXCLUDE_LABELS)})")

        node_pct = (aura_stats["nodes"] / expected_nodes * 100) if expected_nodes else 0
        rel_pct = (
            (aura_stats["rels"] / local_stats["rels"] * 100)
            if local_stats["rels"]
            else 0
        )
        print(f"  Node coverage:  {node_pct:.1f}%")
        print(f"  Rel coverage:   {rel_pct:.1f}%")
        print(f"  Total time:     {node_time + rel_time:.1f}s")

        # Label breakdown
        print("\n  Label breakdown:")
        for label, cnt in sorted(
            aura_stats["labels"].items(), key=lambda x: -x[1]
        ):
            local_cnt = local_stats["labels"].get(label, 0)
            marker = " *" if cnt != local_cnt else ""
            print(f"    {label}: {cnt}/{local_cnt}{marker}")

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise
    finally:
        local_driver.close()
        aura_driver.close()

    print("\n" + "=" * 50)
    print("Backup Complete")
    print("=" * 50)


if __name__ == "__main__":
    main()
