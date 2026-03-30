"""scripts/mappers パッケージ。

BaseMapper 抽象クラスと COMMAND_MAPPERS ディスパッチテーブルを提供する。

COMMAND_MAPPERS は emit_research_queue.py の11マッパー関数への
ディスパッチテーブルであり、外部コンシューマーに対してエクスポートされる。

Usage
-----
::

    from mappers import COMMAND_MAPPERS, BaseMapper

    mapper_fn = COMMAND_MAPPERS.get("web-research")
    result = mapper_fn(data)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mappers.base import BaseMapper, ChunkProcessingContext

__all__ = [
    "COMMAND_MAPPERS",
    "BaseMapper",
    "ChunkProcessingContext",
]

# ---------------------------------------------------------------------------
# COMMAND_MAPPERS ディスパッチテーブル
# ---------------------------------------------------------------------------
# emit_research_queue.py の11マッパー関数をここでインポートして再エクスポートする。
# 将来的に各マッパーが BaseMapper サブクラスに移行した際も、
# このディスパッチテーブルは維持される。
# ---------------------------------------------------------------------------

type _MapperFn = Callable[[dict[str, Any]], dict[str, Any]]


def _build_command_mappers() -> dict[str, _MapperFn]:
    """emit_research_queue.py から COMMAND_MAPPERS をインポートして返す。

    循環インポートを避けるため遅延インポートを使用する。

    Returns
    -------
    dict[str, _MapperFn]
        コマンド名 → マッパー関数のディスパッチテーブル。
    """
    from emit_research_queue import COMMAND_MAPPERS as _raw  # type: ignore[import]

    return dict(_raw)


# ディスパッチテーブルの公開エクスポート
# emit_research_queue.py が scripts/ の pythonpath に含まれていることを前提とする。
COMMAND_MAPPERS: dict[str, _MapperFn] = _build_command_mappers()
"""11コマンドのマッパー関数ディスパッチテーブル。

Keys
----
- ``finance-news-workflow``
- ``ai-research-collect``
- ``generate-market-report``
- ``asset-management``
- ``reddit-finance-topics``
- ``finance-full``
- ``pdf-extraction``
- ``wealth-scrape``
- ``topic-discovery``
- ``web-research``
- ``academic-fetch``
"""
