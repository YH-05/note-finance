"""session_memory パッケージ.

会話セッションのチャンク管理・ベクトル検索・Neo4j連携を担う
SQLiteベースのローカルストレージ基盤。
"""

from session_memory.db import SessionMemoryDB
from session_memory.embedder import get_embedder
from session_memory.searcher import SearchMode, SearchResult, merge_rrf
from session_memory.types import ChunkRow

__all__ = [
    "ChunkRow",
    "SearchMode",
    "SearchResult",
    "SessionMemoryDB",
    "get_embedder",
    "merge_rrf",
]
