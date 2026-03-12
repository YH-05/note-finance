#!/usr/bin/env python3
"""Parse Claude Code conversation history and save to Neo4j.

Reads JSONL conversation files from ~/.claude/projects/, extracts metadata
and topic classification, then saves ConversationSession and ConversationTopic
nodes to Neo4j via MERGEベースの冪等クエリ.

Usage
-----
::

    # Dry run (parse only, no Neo4j write)
    python3 scripts/save_conversations_to_neo4j.py --dry-run

    # Save to Neo4j
    python3 scripts/save_conversations_to_neo4j.py

    # Save specific session
    python3 scripts/save_conversations_to_neo4j.py --session-id <uuid>
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Neo4j driver
try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Topic classification rules
# ---------------------------------------------------------------------------

TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("Neo4j/DB設計", ["neo4j", "cypher", "graph db", "グラフdb", "データベース"]),
    ("MCP設定", ["mcp", "mcpサーバー"]),
    ("Reddit調査", ["reddit", "subreddit"]),
    ("Obsidian統合", ["obsidian", "vault"]),
    ("記事執筆", ["記事", "finance-edit", "finance-full", "初稿", "批評", "修正", "note記事"]),
    ("PDFパイプライン", ["pdf", "レポート", "マークダウン変換", "docling"]),
    ("プロジェクト方針", ["project-discuss", "方向性", "収益化", "副業", "ニッチ", "戦略"]),
    ("スキル/エージェント開発", ["スキル", "skill", "エージェント", "agent", "コマンド"]),
    ("インフラ/Docker", ["docker", "compose", "container"]),
    ("Git/PR操作", ["git", "pr", "push", "merge", "ブランチ"]),
    ("体験談DB", ["体験談", "匿名化", "合成パターン", "婚活", "experience"]),
    ("週次レポート", ["週次", "weekly", "マーケットレポート"]),
    ("KGスキーマ", ["kg", "knowledge graph", "claim", "fact", "スキーマ"]),
    ("RSS/ニュース収集", ["rss", "ニュース", "news", "収集"]),
]


def classify_topics(text: str) -> list[str]:
    """Classify conversation text into topics based on keyword matching."""
    text_lower = text.lower()
    topics = []
    for topic_name, keywords in TOPIC_RULES:
        for kw in keywords:
            if kw.lower() in text_lower:
                topics.append(topic_name)
                break
    return topics if topics else ["その他"]


# ---------------------------------------------------------------------------
# JSONL Parser
# ---------------------------------------------------------------------------

@dataclass
class ConversationSession:
    """Parsed conversation session metadata."""

    session_id: str
    slug: str | None
    started_at: str | None
    ended_at: str | None
    topic: str
    user_messages: list[str] = field(default_factory=list)
    message_count: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0
    file_size_kb: int = 0
    git_branch: str | None = None
    version: str | None = None
    topics: list[str] = field(default_factory=list)
    is_continuation: bool = False
    continued_from: str | None = None


def parse_jsonl(filepath: str) -> ConversationSession:
    """Parse a single JSONL conversation file."""
    session_id = Path(filepath).stem
    file_size_kb = os.path.getsize(filepath) // 1024

    slug = None
    first_ts = None
    last_ts = None
    git_branch = None
    version = None
    user_messages: list[str] = []
    msg_count = 0
    user_count = 0
    assistant_count = 0
    is_continuation = False

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = data.get("timestamp")
            if ts:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts

            if not slug and data.get("slug"):
                slug = data["slug"]
            if not git_branch and data.get("gitBranch"):
                git_branch = data["gitBranch"]
            if not version and data.get("version"):
                version = data["version"]

            msg_type = data.get("type")
            if msg_type in ("user", "assistant"):
                msg_count += 1

            if msg_type == "user" and not data.get("isMeta"):
                user_count += 1
                content = data.get("message", {}).get("content", "")
                if isinstance(content, str) and len(content) > 10:
                    # Check for continuation sessions
                    if "continued from a previous conversation" in content:
                        is_continuation = True
                    # Filter out XML tags and system messages
                    if "<" not in content[:5]:
                        user_messages.append(content)

            if msg_type == "assistant":
                assistant_count += 1

    # Extract topic from first meaningful user message
    topic = ""
    for msg in user_messages:
        cleaned = msg.strip()
        if len(cleaned) > 10:
            topic = cleaned[:200]
            break

    # Classify topics from all user messages
    all_text = " ".join(user_messages[:10])  # Use first 10 messages for classification
    topics = classify_topics(all_text + " " + topic)

    return ConversationSession(
        session_id=session_id,
        slug=slug,
        started_at=first_ts,
        ended_at=last_ts,
        topic=topic,
        user_messages=user_messages[:5],  # Keep first 5 for summary
        message_count=msg_count,
        user_message_count=user_count,
        assistant_message_count=assistant_count,
        file_size_kb=file_size_kb,
        git_branch=git_branch,
        version=version,
        topics=topics,
        is_continuation=is_continuation,
    )


def parse_all_conversations(base_dir: str) -> list[ConversationSession]:
    """Parse all JSONL conversation files in the directory."""
    files = sorted(
        glob.glob(os.path.join(base_dir, "*.jsonl")),
        key=os.path.getmtime,
    )
    sessions = []
    for fpath in files:
        try:
            session = parse_jsonl(fpath)
            sessions.append(session)
        except Exception as e:
            print(f"  Error parsing {fpath}: {e}", file=sys.stderr)
    return sessions


# ---------------------------------------------------------------------------
# Neo4j Loader
# ---------------------------------------------------------------------------

# Cypher queries
CREATE_CONSTRAINTS = """
CREATE CONSTRAINT conversation_session_id IF NOT EXISTS
FOR (s:ConversationSession) REQUIRE s.session_id IS UNIQUE
"""

CREATE_TOPIC_CONSTRAINT = """
CREATE CONSTRAINT conversation_topic_name IF NOT EXISTS
FOR (t:ConversationTopic) REQUIRE t.name IS UNIQUE
"""

MERGE_SESSION = """
MERGE (s:ConversationSession {session_id: $session_id})
SET s.slug = $slug,
    s.started_at = CASE WHEN $started_at IS NOT NULL THEN datetime($started_at) ELSE null END,
    s.ended_at = CASE WHEN $ended_at IS NOT NULL THEN datetime($ended_at) ELSE null END,
    s.topic = $topic,
    s.summary = $summary,
    s.message_count = $message_count,
    s.user_message_count = $user_message_count,
    s.assistant_message_count = $assistant_message_count,
    s.file_size_kb = $file_size_kb,
    s.git_branch = $git_branch,
    s.version = $version,
    s.is_continuation = $is_continuation,
    s.updated_at = datetime()
RETURN s.session_id AS id
"""

MERGE_TOPIC = """
MERGE (t:ConversationTopic {name: $name})
SET t.updated_at = datetime()
RETURN t.name AS name
"""

LINK_SESSION_TOPIC = """
MATCH (s:ConversationSession {session_id: $session_id})
MATCH (t:ConversationTopic {name: $topic_name})
MERGE (s)-[:DISCUSSES]->(t)
"""

LINK_PROJECT_SESSION = """
MATCH (p:Project {name: $project_name})
MATCH (s:ConversationSession {session_id: $session_id})
MERGE (p)-[:HAS_CONVERSATION]->(s)
"""

LINK_CONTINUATION = """
MATCH (s1:ConversationSession {session_id: $from_session})
MATCH (s2:ConversationSession {session_id: $to_session})
MERGE (s1)-[:CONTINUED_AS]->(s2)
"""


def save_to_neo4j(
    sessions: list[ConversationSession],
    uri: str = "bolt://localhost:7687",
    user: str = "neo4j",
    password: str = "password",
    project_name: str = "note-finance SideBusiness Project",
) -> dict:
    """Save parsed sessions to Neo4j."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    stats = {"sessions": 0, "topics": 0, "links": 0}

    try:
        with driver.session() as session:
            # Create constraints
            try:
                session.run(CREATE_CONSTRAINTS)
                session.run(CREATE_TOPIC_CONSTRAINT)
            except Exception:
                pass  # Constraints may already exist

            # Collect unique topics
            all_topics = set()
            for s in sessions:
                all_topics.update(s.topics)

            # Create topic nodes
            for topic_name in all_topics:
                session.run(MERGE_TOPIC, name=topic_name)
                stats["topics"] += 1

            # Create session nodes and links
            for s in sessions:
                # Build summary from user messages
                summary = " | ".join(
                    msg[:100] for msg in s.user_messages[:3]
                )
                if len(summary) > 500:
                    summary = summary[:500] + "..."

                session.run(
                    MERGE_SESSION,
                    session_id=s.session_id,
                    slug=s.slug,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    topic=s.topic,
                    summary=summary,
                    message_count=s.message_count,
                    user_message_count=s.user_message_count,
                    assistant_message_count=s.assistant_message_count,
                    file_size_kb=s.file_size_kb,
                    git_branch=s.git_branch,
                    version=s.version,
                    is_continuation=s.is_continuation,
                )
                stats["sessions"] += 1

                # Link to topics
                for topic_name in s.topics:
                    session.run(
                        LINK_SESSION_TOPIC,
                        session_id=s.session_id,
                        topic_name=topic_name,
                    )
                    stats["links"] += 1

                # Link to project
                session.run(
                    LINK_PROJECT_SESSION,
                    project_name=project_name,
                    session_id=s.session_id,
                )

    finally:
        driver.close()

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save Claude Code conversation history to Neo4j",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only, do not write to Neo4j",
    )
    parser.add_argument(
        "--session-id",
        help="Process a specific session only",
    )
    parser.add_argument(
        "--base-dir",
        default=os.path.expanduser(
            "~/.claude/projects/-Users-yuki-Desktop-note-finance"
        ),
        help="Base directory for conversation files",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7687",
        help="Neo4j connection URI",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.environ.get("NEO4J_PASSWORD", "password"),
        help="Neo4j password (default: $NEO4J_PASSWORD or 'password')",
    )
    parser.add_argument(
        "--project-name",
        default="SideBusiness",
        help="Project node name in Neo4j",
    )
    args = parser.parse_args()

    print(f"Scanning: {args.base_dir}")

    if args.session_id:
        filepath = os.path.join(args.base_dir, f"{args.session_id}.jsonl")
        if not os.path.exists(filepath):
            print(f"Session file not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        sessions = [parse_jsonl(filepath)]
    else:
        sessions = parse_all_conversations(args.base_dir)

    print(f"Parsed {len(sessions)} sessions\n")

    # Print summary
    for s in sessions:
        date = s.started_at[:10] if s.started_at else "?"
        name = s.slug or s.session_id[:8]
        cont = " (continuation)" if s.is_continuation else ""
        print(f"[{date}] {name}{cont}")
        print(f"  Messages: {s.user_message_count}u/{s.assistant_message_count}a, Size: {s.file_size_kb}KB")
        print(f"  Topics: {', '.join(s.topics)}")
        if s.topic:
            print(f"  First msg: {s.topic[:80]}")
        print()

    if args.dry_run:
        print("=== DRY RUN — no data written to Neo4j ===")
        topic_counts: dict[str, int] = {}
        for s in sessions:
            for t in s.topics:
                topic_counts[t] = topic_counts.get(t, 0) + 1
        print("\nTopic distribution:")
        for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
            print(f"  {topic}: {count}")
        return

    print("Saving to Neo4j...")
    stats = save_to_neo4j(
        sessions,
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
        project_name=args.project_name,
    )
    print(f"\nDone! Sessions: {stats['sessions']}, Topics: {stats['topics']}, Links: {stats['links']}")


if __name__ == "__main__":
    main()
