"""Ruri v3-310m 遅延ロードラッパー.

sentence-transformers の SentenceTransformer モデルを遅延ロードし、
``@functools.lru_cache`` で初回呼び出し時にのみモデルをロードする。

主な機能:
- デフォルトモデル: ``cl-nagoya/ruri-v3-310m``
- フォールバック: ``intfloat/multilingual-e5-small``
- ``SESSION_MEMORY_MODEL`` 環境変数によるモデルオーバーライド
- sentence-transformers 未インストール時は ``None`` を返す

参照パターン: ``scripts/entity_linker.py:827-839``
"""

from __future__ import annotations

import functools
import os
from typing import Any

from session_memory._logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "cl-nagoya/ruri-v3-310m"
"""デフォルトの埋め込みモデル名."""

FALLBACK_MODEL = "intfloat/multilingual-e5-small"
"""Ruri ロード失敗時のフォールバックモデル名."""

_ENV_MODEL_KEY = "SESSION_MEMORY_MODEL"
"""モデル名をオーバーライドする環境変数キー."""


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def get_embedder() -> Any:
    """SentenceTransformer モデルを遅延ロードして返す.

    初回呼び出し時にモデルをロードし、以降はキャッシュから返す。
    ``sentence-transformers`` が未インストールの場合は ``None`` を返す。

    環境変数 ``SESSION_MEMORY_MODEL`` が設定されている場合、
    そのモデル名を使用する（フォールバックなし）。

    Returns
    -------
    Any
        SentenceTransformer モデルインスタンス。
        ロードできなかった場合は ``None``。

    Examples
    --------
    >>> model = get_embedder()
    >>> if model is not None:
    ...     embeddings = model.encode(["テスト文"])
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning(
            "sentence-transformers not installed, embedding disabled. "
            "Install with: uv sync --extra memory"
        )
        return None

    # 環境変数によるモデルオーバーライド
    env_model = os.environ.get(_ENV_MODEL_KEY)
    if env_model:
        return _load_model(SentenceTransformer, env_model, fallback=False)

    # デフォルト: Ruri -> e5-small フォールバック
    return _load_model(SentenceTransformer, DEFAULT_MODEL, fallback=True)


# ---------------------------------------------------------------------------
# 内部関数
# ---------------------------------------------------------------------------


def _load_model(
    cls: type,
    model_name: str,
    *,
    fallback: bool,
) -> Any:
    """SentenceTransformer モデルをロードする.

    Parameters
    ----------
    cls : type
        SentenceTransformer クラス
    model_name : str
        ロードするモデル名
    fallback : bool
        True の場合、ロード失敗時に FALLBACK_MODEL を試行する

    Returns
    -------
    Any
        モデルインスタンス。全てのロードに失敗した場合は ``None``。
    """
    try:
        logger.info("Loading embedding model", model=model_name)
        model = cls(model_name, device="cpu")
        logger.info("Embedding model loaded", model=model_name)
        return model
    except Exception:
        logger.warning(
            "Failed to load embedding model",
            model=model_name,
            exc_info=True,
        )

    if fallback:
        try:
            logger.info(
                "Falling back to alternative model",
                model=FALLBACK_MODEL,
            )
            model = cls(FALLBACK_MODEL, device="cpu")
            logger.info("Fallback model loaded", model=FALLBACK_MODEL)
            return model
        except Exception:
            logger.warning(
                "Failed to load fallback model",
                model=FALLBACK_MODEL,
                exc_info=True,
            )

    logger.error("All embedding models failed to load, embedding disabled")
    return None


__all__ = [
    "DEFAULT_MODEL",
    "FALLBACK_MODEL",
    "get_embedder",
]
