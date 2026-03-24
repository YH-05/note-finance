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
from session_memory.graph import SessionGraphWriter
from session_memory.hook import (
    HookInput,
    parse_hook_input,
    run_session_end_hook,
)
from session_memory.linker import LinkerConfig, LinkResult, NoteLinker
from session_memory.searcher import SearchMode, SearchResult, merge_rrf
from session_memory.types import ChunkRow

__all__ = [
    "ChunkExtraction",
    "ChunkRow",
    "ExtractedDecision",
    "ExtractedEntity",
    "ExtractedTopic",
    "HookInput",
    "LinkResult",
    "LinkerConfig",
    "NoteLinker",
    "SearchMode",
    "SearchResult",
    "SessionGraphWriter",
    "SessionMemoryDB",
    "extract_chunk",
    "extract_chunks_batch",
    "get_embedder",
    "merge_rrf",
    "parse_hook_input",
    "rule_based_predetect",
    "run_session_end_hook",
]
