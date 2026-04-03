#!/usr/bin/env python3
"""note-neo4j に CodeEntity / Document ノードを投入するバッチスクリプト。

既存の Discussion / Decision / ActionItem のテキストからリポジトリ内パスを抽出し、
CodeEntity（実装ファイル）と Document（知識ファイル）として構造化する。

Usage
-----
::

    # ドライラン（抽出結果確認、DB 書き込みなし）
    uv run python scripts/populate_note_code_entities.py --dry-run

    # 本番実行
    uv run python scripts/populate_note_code_entities.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from neo4j_utils import create_driver

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOTE_NEO4J_URI = "bolt://localhost:7687"

KNOWN_EXTENSIONS = frozenset(
    {"py", "md", "yaml", "yml", "json", "toml", "sh", "txt", "csv", "html", "js", "ts"}
)

# Domains to exclude from standalone filename matching
DOMAIN_SUFFIXES = frozenset({"com", "org", "net", "io", "co", "jp", "id", "dev", "go"})

# Regex: path with at least one /  (e.g. src/foo/bar.py, .claude/skills/, docs/plan/)
_PATH_WITH_SLASH = re.compile(
    r"""
    (                             # capture group
        \.?[\w][\w._-]*           # first segment (optionally dot-prefixed)
        (?:/[\w._{}*-]+)+         # one or more /segment
        (?:\.[\w]+)?              # optional extension
        /?                        # optional trailing slash
    )
    """,
    re.VERBOSE,
)

# Regex: standalone filename  (e.g. entity_linker.py, SKILL.md)
_EXT_PATTERN = "|".join(KNOWN_EXTENSIONS)
_STANDALONE_FILE = re.compile(
    rf"(?:^|[\s（(「『,;:])([A-Za-z_.][A-Za-z0-9_.-]*\.(?:{_EXT_PATTERN}))(?=$|[\s）)」』,;:\u3002\u3001])",
)


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

_CODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^scripts/"), "script"),
    (re.compile(r"^src/"), "module"),
    (re.compile(r"^\.claude/skills/[^/]+/"), "skill"),
    (re.compile(r"^\.claude/agents/"), "agent"),
    (re.compile(r"^\.agents/"), "agent"),
    (re.compile(r"^\.claude/commands/"), "command"),
    (re.compile(r"^\.claude/rules/"), "rule"),
    (re.compile(r"^\.claude/hooks/"), "config"),
    (re.compile(r"^\.claude/resources/"), "config"),
    (re.compile(r"^\.claude/guidelines/"), "config"),
    (re.compile(r"^\.claude/settings\.json"), "config"),
    (re.compile(r"^tests/"), "test"),
    (re.compile(r"^data/"), "config"),
    (re.compile(r"^template/"), "config"),
    (re.compile(r"^Makefile$"), "config"),
    (re.compile(r"^pyproject\.toml$"), "config"),
]

_DOC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^docs/plan/"), "plan"),
    (re.compile(r"^docs/guidelines/"), "guideline"),
    (re.compile(r"^docs/research-neo4j/"), "incident"),
    (re.compile(r"^docs/market-comment/"), "plan"),
    (re.compile(r"^docs/MTG_memo/"), "plan"),
    (re.compile(r"^docs/obsidian/"), "plan"),
    (re.compile(r"^docs/"), "guideline"),
    (re.compile(r"^articles/"), "article"),
    (re.compile(r"^CLAUDE\.md$"), "project_def"),
    (re.compile(r"^AGENTS\.md$"), "project_def"),
    (re.compile(r"^snippets/"), "guideline"),
]


def classify_path(path: str) -> tuple[str, str]:
    """Classify a path as ``(label, type_value)``.

    Returns ``('CodeEntity', type)`` or ``('Document', type)``.
    For directories, ``type='directory'`` unless it represents
    a specific concept (e.g. a skill directory).
    """
    is_dir = path.endswith("/")

    # Document patterns first
    for pattern, doc_type in _DOC_PATTERNS:
        if pattern.search(path):
            if is_dir:
                return ("Document", "directory")
            return ("Document", doc_type)

    # Code patterns
    for pattern, code_type in _CODE_PATTERNS:
        if pattern.search(path):
            if is_dir:
                # Special: .claude/skills/X/ → skill directory
                if re.match(r"^\.claude/skills/[^/]+/$", path):
                    return ("CodeEntity", "skill")
                return ("CodeEntity", "directory")
            return ("CodeEntity", code_type)

    # Fallback
    if is_dir:
        return ("CodeEntity", "directory")
    ext = Path(path).suffix.lstrip(".")
    if ext in {"py", "sh", "toml", "yaml", "yml", "json"}:
        return ("CodeEntity", "config")
    return ("Document", "guideline")


# ---------------------------------------------------------------------------
# Git index
# ---------------------------------------------------------------------------


def build_git_index() -> tuple[set[str], dict[str, list[str]], dict[str, list[str]]]:
    """Build indexes from ``git ls-files``.

    Returns
    -------
    all_files : set[str]
        All tracked file paths.
    basename_index : dict[str, list[str]]
        Basename (e.g. ``entity_linker.py``) to full paths.
    stem_index : dict[str, list[str]]
        Stem without extension (e.g. ``entity_linker``) to full paths.
    """
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    all_files: set[str] = set()
    basename_index: dict[str, list[str]] = {}
    stem_index: dict[str, list[str]] = {}

    for line in result.stdout.strip().split("\n"):
        path = line.strip()
        if not path:
            continue
        all_files.add(path)
        bname = Path(path).name
        basename_index.setdefault(bname, []).append(path)
        stem = Path(path).stem
        stem_index.setdefault(stem, []).append(path)

    return all_files, basename_index, stem_index


def build_dir_set(all_files: set[str]) -> set[str]:
    """Build set of all directories containing tracked files."""
    dirs: set[str] = set()
    for p in all_files:
        parts = Path(p).parts
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]) + "/")
    return dirs


def build_article_index(all_files: set[str]) -> dict[str, str]:
    """Build slug -> article directory path mapping.

    E.g. ``'index-investing-portfolio'`` ->
    ``'articles/asset_management/2026-03-06_index-investing-portfolio/'``
    """
    article_dirs: dict[str, str] = {}
    seen_dirs: set[str] = set()
    for f in all_files:
        if not f.startswith("articles/"):
            continue
        parts = Path(f).parts
        if len(parts) >= 3:
            dir_path = "/".join(parts[:3]) + "/"
            if dir_path in seen_dirs:
                continue
            seen_dirs.add(dir_path)
            # Extract slug: remove date prefix if present
            dirname = parts[2]
            article_dirs[dirname] = dir_path
            # Also index without date prefix
            slug_match = re.match(r"\d{4}-\d{2}-\d{2}_(.*)", dirname)
            if slug_match:
                article_dirs[slug_match.group(1)] = dir_path
    return article_dirs


def build_skill_cmd_index(all_files: set[str]) -> dict[str, str]:
    """Build skill/command name -> path mapping.

    E.g. ``'finance-article-writer'`` ->
    ``'.claude/skills/finance-article-writer/'``
    """
    index: dict[str, str] = {}
    seen: set[str] = set()
    for f in all_files:
        # Skills: .claude/skills/<name>/...
        m = re.match(r"^\.claude/skills/([^/]+)/", f)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            index[m.group(1)] = f".claude/skills/{m.group(1)}/"

        # Commands: .claude/commands/<name>.md
        m = re.match(r"^\.claude/commands/([^/]+)\.md$", f)
        if m:
            index[m.group(1)] = f

        # Agents: .claude/agents/<name>.md
        m = re.match(r"^\.claude/agents/([^/]+)\.md$", f)
        if m:
            index[m.group(1)] = f

    return index


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------


def _resolve_candidate(
    candidate: str,
    all_files: set[str],
    basename_index: dict[str, list[str]],
) -> str | None:
    """Try to resolve a candidate string to a tracked file path."""
    # Direct match
    if candidate in all_files:
        return candidate
    # Strip trailing slash for directory check
    candidate_clean = candidate.rstrip("/")
    # Try as suffix of known paths
    for f in all_files:
        if f.endswith(candidate) or f.endswith(candidate_clean):
            return f
    # Try basename
    bname = Path(candidate_clean).name
    if bname in basename_index and len(basename_index[bname]) == 1:
        return basename_index[bname][0]
    return None


def extract_paths_from_text(
    text: str,
    all_files: set[str],
    basename_index: dict[str, list[str]],
    dir_set: set[str],
    article_index: dict[str, str],
) -> set[str]:
    """Extract file/directory paths from free-form text."""
    if not text:
        return set()

    resolved: set[str] = set()

    # 1. Paths with / separators
    for m in _PATH_WITH_SLASH.finditer(text):
        candidate = m.group(1).rstrip("。、）)")
        # Skip URLs
        start = m.start()
        prefix = text[max(0, start - 8) : start]
        if "://" in prefix:
            continue

        # Resolve
        if candidate.endswith("/"):
            if candidate in dir_set:
                resolved.add(candidate)
        else:
            hit = _resolve_candidate(candidate, all_files, basename_index)
            if hit:
                resolved.add(hit)
            # Also check if it's a directory reference without trailing /
            elif candidate + "/" in dir_set:
                resolved.add(candidate + "/")

    # 2. Standalone filenames
    for m in _STANDALONE_FILE.finditer(text):
        bname = m.group(1)
        # Skip domain-like patterns (note.com, bi.go.id)
        ext = bname.rsplit(".", 1)[-1]
        if ext in DOMAIN_SUFFIXES:
            continue
        if bname in basename_index:
            if len(basename_index[bname]) == 1:
                resolved.add(basename_index[bname][0])

    # 3. Article slug references
    for slug, dir_path in article_index.items():
        if slug in text and len(slug) > 10:  # avoid short false positives
            resolved.add(dir_path)

    return resolved


def extract_paths_from_topics(
    topics: list[str],
    all_files: set[str],
    basename_index: dict[str, list[str]],
    stem_index: dict[str, list[str]],
    skill_cmd_index: dict[str, str],
) -> set[str]:
    """Extract file paths from ``Discussion.topics`` array."""
    if not topics:
        return set()

    resolved: set[str] = set()
    for topic in topics:
        # 1. Direct basename match (e.g. "ontology.yaml")
        if "." in topic and not topic.startswith("http"):
            ext = topic.rsplit(".", 1)[-1]
            if ext not in DOMAIN_SUFFIXES and topic in basename_index:
                if len(basename_index[topic]) == 1:
                    resolved.add(basename_index[topic][0])
                continue

        # 2. Stem match (e.g. "entity_linker" -> entity_linker.py)
        if topic in stem_index and len(stem_index[topic]) == 1:
            resolved.add(stem_index[topic][0])
            continue

        # 3. Skill/command/agent name match
        if topic in skill_cmd_index:
            resolved.add(skill_cmd_index[topic])
            continue

        # 4. Try with common extensions
        for ext in ("py", "yaml", "md"):
            candidate = f"{topic}.{ext}"
            if candidate in basename_index and len(basename_index[candidate]) == 1:
                resolved.add(basename_index[candidate][0])
                break

    return resolved


# ---------------------------------------------------------------------------
# Directory hierarchy
# ---------------------------------------------------------------------------


def get_parent_chain(path: str) -> list[str]:
    """Return parent directories from shallowest to deepest.

    ``'src/data_pipeline/neo4j_loader.py'``
    -> ``['src/', 'src/data_pipeline/']``
    """
    clean = path.rstrip("/")
    parts = Path(clean).parts
    return ["/".join(parts[:i]) + "/" for i in range(1, len(parts))]


# ---------------------------------------------------------------------------
# Neo4j operations
# ---------------------------------------------------------------------------


def create_constraints(driver: Any) -> None:
    """Create UNIQUE constraints for CodeEntity and Document."""
    queries = [
        "CREATE CONSTRAINT code_entity_path IF NOT EXISTS "
        "FOR (c:CodeEntity) REQUIRE c.path IS UNIQUE",
        "CREATE CONSTRAINT document_path IF NOT EXISTS "
        "FOR (d:Document) REQUIRE d.path IS UNIQUE",
    ]
    with driver.session() as session:
        for q in queries:
            session.run(q)
            logger.info("Constraint created: %s", q[:60])


def batch_create_nodes(
    driver: Any,
    nodes: dict[str, tuple[str, str]],
) -> int:
    """MERGE all CodeEntity and Document nodes in batches.

    Parameters
    ----------
    nodes : dict[str, tuple[str, str]]
        ``{path: (label, type_value)}``

    Returns
    -------
    int
        Number of nodes created/merged.
    """
    code_nodes = [
        {
            "path": p,
            "type": t,
            "name": Path(p.rstrip("/")).name or p,
            "status": "active",
        }
        for p, (lbl, t) in nodes.items()
        if lbl == "CodeEntity"
    ]
    doc_nodes = [
        {
            "path": p,
            "type": t,
            "name": Path(p.rstrip("/")).name or p,
            "status": "active",
        }
        for p, (lbl, t) in nodes.items()
        if lbl == "Document"
    ]

    count = 0
    with driver.session() as session:
        if code_nodes:
            session.run(
                """
                UNWIND $nodes AS n
                MERGE (c:CodeEntity {path: n.path})
                SET c.type = n.type, c.name = n.name, c.status = n.status
                """,
                nodes=code_nodes,
            )
            count += len(code_nodes)

        if doc_nodes:
            session.run(
                """
                UNWIND $nodes AS n
                MERGE (d:Document {path: n.path})
                SET d.type = n.type, d.name = n.name, d.status = n.status
                """,
                nodes=doc_nodes,
            )
            count += len(doc_nodes)

    return count


def batch_create_relationships(
    driver: Any,
    rels: list[tuple[str, str, str, str, str, str]],
) -> int:
    """Create relationships in batches.

    Parameters
    ----------
    rels : list of (from_label, from_prop, from_val, rel_type, to_label, to_val)

    Returns
    -------
    int
        Number of relationships created/merged.
    """
    # Group by (from_label, rel_type, to_label)
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for from_lbl, from_prop, from_val, rel_type, to_lbl, to_val in rels:
        key = (from_lbl, rel_type, to_lbl, from_prop)
        groups.setdefault(key, []).append({"from_val": from_val, "to_val": to_val})

    count = 0
    with driver.session() as session:
        for (from_lbl, rel_type, to_lbl, from_prop), items in groups.items():
            cypher = (
                f"UNWIND $items AS item "
                f"MATCH (a:{from_lbl} {{{from_prop}: item.from_val}}) "
                f"MATCH (b:{to_lbl} {{path: item.to_val}}) "
                f"MERGE (a)-[:{rel_type}]->(b)"
            )
            session.run(cypher, items=items)
            count += len(items)

    return count


def batch_create_contains(
    driver: Any,
    contains: list[tuple[str, str, str, str]],
) -> int:
    """Create CONTAINS relationships.

    Parameters
    ----------
    contains : list of (parent_label, parent_path, child_label, child_path)
    """
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for p_lbl, p_path, c_lbl, c_path in contains:
        key = (p_lbl, c_lbl)
        groups.setdefault(key, []).append({"parent": p_path, "child": c_path})

    count = 0
    with driver.session() as session:
        for (p_lbl, c_lbl), items in groups.items():
            cypher = (
                f"UNWIND $items AS item "
                f"MATCH (p:{p_lbl} {{path: item.parent}}) "
                f"MATCH (c:{c_lbl} {{path: item.child}}) "
                f"MERGE (p)-[:CONTAINS]->(c)"
            )
            session.run(cypher, items=items)
            count += len(items)

    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate note-neo4j with CodeEntity/Document nodes"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show extraction results without writing to DB",
    )
    parser.add_argument("--neo4j-password", default=None)
    args = parser.parse_args()

    # ── 1. Build git indexes ──────────────────────────────────────────────
    logger.info("Building git file index...")
    all_files, basename_index, stem_index = build_git_index()
    dir_set = build_dir_set(all_files)
    article_index = build_article_index(all_files)
    skill_cmd_index = build_skill_cmd_index(all_files)
    logger.info(
        "Indexed %d files, %d dirs, %d articles, %d skills/cmds",
        len(all_files),
        len(dir_set),
        len(article_index),
        len(skill_cmd_index),
    )

    # ── 2. Connect to note-neo4j ──────────────────────────────────────────
    password = args.neo4j_password or os.environ.get("NEO4J_PASSWORD")
    driver = create_driver(uri=NOTE_NEO4J_URI, password=password)

    # ── 3. Read existing nodes ────────────────────────────────────────────
    with driver.session() as session:
        discussions = [
            dict(r["d"]) for r in session.run("MATCH (d:Discussion) RETURN d")
        ]
        decisions = [dict(r["d"]) for r in session.run("MATCH (d:Decision) RETURN d")]
        action_items = [
            dict(r["a"]) for r in session.run("MATCH (a:ActionItem) RETURN a")
        ]

    logger.info(
        "Read %d Discussions, %d Decisions, %d ActionItems",
        len(discussions),
        len(decisions),
        len(action_items),
    )

    # ── 4. Extract paths ─────────────────────────────────────────────────
    all_nodes: dict[str, tuple[str, str]] = {}  # path -> (label, type)
    # (from_label, from_id_prop, from_id_val, rel_type, to_label, to_path)
    rels: list[tuple[str, str, str, str, str, str]] = []

    for disc in discussions:
        disc_id = disc.get("discussion_id", "")
        paths: set[str] = set()

        # Title
        paths.update(
            extract_paths_from_text(
                disc.get("title", ""), all_files, basename_index, dir_set, article_index
            )
        )

        # Topics
        paths.update(
            extract_paths_from_topics(
                disc.get("topics") or [],
                all_files,
                basename_index,
                stem_index,
                skill_cmd_index,
            )
        )

        # doc_path → RECORDED_IN
        doc_path = disc.get("doc_path", "")
        if doc_path and doc_path in all_files:
            label, type_val = classify_path(doc_path)
            all_nodes[doc_path] = (label, type_val)
            rels.append(
                ("Discussion", "discussion_id", disc_id, "RECORDED_IN", label, doc_path)
            )

        # Other paths → MENTIONS
        for p in paths:
            label, type_val = classify_path(p)
            all_nodes[p] = (label, type_val)
            rels.append(("Discussion", "discussion_id", disc_id, "MENTIONS", label, p))

    for dec in decisions:
        dec_id = dec.get("decision_id", "")
        paths = set()
        for field_name in ("content", "context"):
            paths.update(
                extract_paths_from_text(
                    dec.get(field_name, ""),
                    all_files,
                    basename_index,
                    dir_set,
                    article_index,
                )
            )
        for p in paths:
            label, type_val = classify_path(p)
            all_nodes[p] = (label, type_val)
            rels.append(("Decision", "decision_id", dec_id, "AFFECTS", label, p))

    for ai in action_items:
        ai_id = ai.get("action_id", "")
        paths = extract_paths_from_text(
            ai.get("description", ""),
            all_files,
            basename_index,
            dir_set,
            article_index,
        )
        for p in paths:
            label, type_val = classify_path(p)
            all_nodes[p] = (label, type_val)
            rels.append(("ActionItem", "action_id", ai_id, "TARGETS", label, p))

    # ── 5. Compute directory hierarchy ────────────────────────────────────
    dir_nodes: dict[str, tuple[str, str]] = {}
    for path in list(all_nodes.keys()):
        for d in get_parent_chain(path):
            if d not in all_nodes and d not in dir_nodes:
                label, _ = classify_path(d)
                dir_nodes[d] = (label, "directory")

    all_nodes.update(dir_nodes)

    # Build CONTAINS edges
    contains: list[tuple[str, str, str, str]] = []  # (p_lbl, p_path, c_lbl, c_path)
    for path in all_nodes:
        chain = get_parent_chain(path)
        if chain:
            parent = chain[-1]
            if parent in all_nodes and parent != path:
                p_lbl = all_nodes[parent][0]
                c_lbl = all_nodes[path][0]
                contains.append((p_lbl, parent, c_lbl, path))
        # Chain directories together
        for i in range(len(chain) - 1):
            if chain[i] in all_nodes and chain[i + 1] in all_nodes:
                p_lbl = all_nodes[chain[i]][0]
                c_lbl = all_nodes[chain[i + 1]][0]
                contains.append((p_lbl, chain[i], c_lbl, chain[i + 1]))

    contains = list(set(contains))

    # ── 6. Report ─────────────────────────────────────────────────────────
    code_nodes = {p: t for p, (l, t) in sorted(all_nodes.items()) if l == "CodeEntity"}
    doc_nodes = {p: t for p, (l, t) in sorted(all_nodes.items()) if l == "Document"}

    logger.info("=== Extraction Results ===")
    logger.info("CodeEntity: %d nodes", len(code_nodes))
    for p, t in sorted(code_nodes.items()):
        logger.info("  [%-10s] %s", t, p)
    logger.info("Document: %d nodes", len(doc_nodes))
    for p, t in sorted(doc_nodes.items()):
        logger.info("  [%-10s] %s", t, p)
    logger.info("Relationships: %d  |  CONTAINS: %d", len(rels), len(contains))

    if args.dry_run:
        summary = {
            "code_entities": code_nodes,
            "documents": doc_nodes,
            "relationship_count": len(rels),
            "contains_count": len(contains),
            "relationships_sample": [
                {
                    "from": f"{r[0]}({r[2]})",
                    "rel": r[3],
                    "to": r[5],
                }
                for r in rels[:20]
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        driver.close()
        logger.info("Dry run complete. No changes written.")
        return

    # ── 7. Write to DB ────────────────────────────────────────────────────
    logger.info("Creating constraints...")
    create_constraints(driver)

    logger.info("Creating %d nodes...", len(all_nodes))
    n_created = batch_create_nodes(driver, all_nodes)
    logger.info("Merged %d nodes", n_created)

    logger.info("Creating %d relationships...", len(rels))
    n_rels = batch_create_relationships(driver, rels)
    logger.info("Merged %d relationships", n_rels)

    logger.info("Creating %d CONTAINS relationships...", len(contains))
    n_contains = batch_create_contains(driver, contains)
    logger.info("Merged %d CONTAINS relationships", n_contains)

    driver.close()
    logger.info("Done!")


if __name__ == "__main__":
    main()
