"""session_memory パッケージの型定義.

チャンク行、インポートログ、抽出ログの構造化型を提供する。
"""

from dataclasses import dataclass
from typing import Literal, TypedDict

# ---------------------------------------------------------------------------
# チャンク行
# ---------------------------------------------------------------------------

type ChunkRole = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class ChunkRow:
    """chunks テーブルの1行を表す不変データクラス.

    Parameters
    ----------
    chunk_key : str
        チャンクの一意識別子（例: "session-001::0"）
    session_id : str
        所属するセッションID
    content : str
        チャンク本文
    role : ChunkRole
        発話者ロール（user / assistant / system）
    token_count : int | None
        トークン数（未計算の場合 None）
    created_at : str | None
        作成日時（ISO 8601 形式、DBデフォルトで自動設定）
    """

    chunk_key: str
    session_id: str
    content: str
    role: ChunkRole
    token_count: int | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# ログ辞書型
# ---------------------------------------------------------------------------


class ImportLogDict(TypedDict):
    """import_log テーブルの1行を表す辞書型."""

    id: int
    session_id: str
    chunk_count: int
    status: str
    created_at: str


class ExtractionLogDict(TypedDict):
    """extraction_log テーブルの1行を表す辞書型."""

    id: int
    session_id: str
    entity_count: int
    relation_count: int
    status: str
    created_at: str


__all__ = [
    "ChunkRole",
    "ChunkRow",
    "ExtractionLogDict",
    "ImportLogDict",
]
