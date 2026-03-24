"""session_memory パッケージ.

会話セッションのチャンク管理・ベクトル検索・Neo4j連携を担う
SQLiteベースのローカルストレージ基盤。
"""

from session_memory.db import SessionMemoryDB
from session_memory.embedder import get_embedder
from session_memory.extractor import (
    ChunkExtraction,
    ExtractedDecision,
    ExtractedEntity,
    ExtractedTopic,
    extract_chunk,
    extract_chunks_batch,
    rule_based_predetect,
)
from session_memory.searcher import SearchMode, SearchResult, merge_rrf
from session_memory.types import ChunkRow

__all__ = [
    "ChunkExtraction",
    "ChunkRow",
    "ExtractedDecision",
    "ExtractedEntity",
    "ExtractedTopic",
    "SearchMode",
    "SearchResult",
    "SessionMemoryDB",
    "extract_chunk",
    "extract_chunks_batch",
    "get_embedder",
    "merge_rrf",
    "rule_based_predetect",
]
