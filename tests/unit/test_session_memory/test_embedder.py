"""session_memory.embedder のユニットテスト.

get_embedder() の遅延ロード・キャッシュ・フォールバック動作を検証する。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    import types

# ---------------------------------------------------------------------------
# ヘルパー: テスト毎にモジュールを再読み込みして lru_cache をリセット
# ---------------------------------------------------------------------------


def _reload_embedder() -> types.ModuleType:
    """embedder モジュールを再読み込みして lru_cache をリセットする.

    Returns
    -------
    types.ModuleType
        再読み込みされた embedder モジュール
    """
    import session_memory.embedder as mod

    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestGetEmbedder:
    """get_embedder() の基本動作テスト."""

    def test_正常系_sentence_transformers未インストールでNone返却(self) -> None:
        """sentence-transformers が未インストールの場合は None を返す."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            mod = _reload_embedder()
            result = mod.get_embedder()
            assert result is None

    def test_正常系_lru_cacheで同一オブジェクトを返す(self) -> None:
        """2回呼び出しても同一オブジェクト（キャッシュ済み）を返す."""
        mock_model = MagicMock()
        mock_st = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            mod = _reload_embedder()
            first = mod.get_embedder()
            second = mod.get_embedder()
            assert first is second
            # SentenceTransformer は1回だけ呼ばれる
            assert mock_st.SentenceTransformer.call_count == 1

    def test_正常系_デフォルトモデルはRuri(self) -> None:
        """デフォルトでは cl-nagoya/ruri-v3-310m を使用する."""
        mock_model = MagicMock()
        mock_st = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            mod = _reload_embedder()
            mod.get_embedder()
            call_args = mock_st.SentenceTransformer.call_args
            assert "ruri" in call_args[0][0].lower() or "ruri" in str(call_args).lower()

    def test_正常系_SESSION_MEMORY_MODEL環境変数でオーバーライド(self) -> None:
        """SESSION_MEMORY_MODEL 環境変数でモデル名を上書きできる."""
        mock_model = MagicMock()
        mock_st = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with (
            patch.dict("sys.modules", {"sentence_transformers": mock_st}),
            patch.dict("os.environ", {"SESSION_MEMORY_MODEL": "custom/my-model"}),
        ):
            mod = _reload_embedder()
            mod.get_embedder()
            call_args = mock_st.SentenceTransformer.call_args
            assert call_args[0][0] == "custom/my-model"

    def test_正常系_Ruri失敗時にe5_smallフォールバック(self) -> None:
        """Ruri モデルのロードに失敗した場合、multilingual-e5-small にフォールバック."""
        mock_fallback = MagicMock()
        mock_st = MagicMock()

        # 1回目（Ruri）は例外、2回目（e5-small）は成功
        mock_st.SentenceTransformer.side_effect = [
            OSError("Model not found"),
            mock_fallback,
        ]

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            mod = _reload_embedder()
            result = mod.get_embedder()
            assert result is mock_fallback
            assert mock_st.SentenceTransformer.call_count == 2

    def test_正常系_両モデル失敗でNone返却(self) -> None:
        """Ruri と e5-small の両方が失敗した場合は None を返す."""
        mock_st = MagicMock()
        mock_st.SentenceTransformer.side_effect = OSError("All models failed")

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            mod = _reload_embedder()
            result = mod.get_embedder()
            assert result is None

    def test_正常系_環境変数モデル失敗時はフォールバックしない(self) -> None:
        """SESSION_MEMORY_MODEL で指定されたモデルが失敗した場合は None を返す.

        ユーザーが明示的にモデルを指定した場合、自動フォールバックは行わない。
        """
        mock_st = MagicMock()
        mock_st.SentenceTransformer.side_effect = OSError("Custom model not found")

        with (
            patch.dict("sys.modules", {"sentence_transformers": mock_st}),
            patch.dict("os.environ", {"SESSION_MEMORY_MODEL": "custom/broken-model"}),
        ):
            mod = _reload_embedder()
            result = mod.get_embedder()
            assert result is None
            # 環境変数指定時はフォールバックなし（1回だけ呼ばれる）
            assert mock_st.SentenceTransformer.call_count == 1


class TestDefaultModelName:
    """デフォルトモデル名の定数テスト."""

    def test_正常系_DEFAULT_MODELが定義されている(self) -> None:
        """DEFAULT_MODEL 定数が定義されていること."""
        mod = _reload_embedder()
        assert hasattr(mod, "DEFAULT_MODEL")
        assert isinstance(mod.DEFAULT_MODEL, str)
        assert len(mod.DEFAULT_MODEL) > 0

    def test_正常系_FALLBACK_MODELが定義されている(self) -> None:
        """FALLBACK_MODEL 定数が定義されていること."""
        mod = _reload_embedder()
        assert hasattr(mod, "FALLBACK_MODEL")
        assert isinstance(mod.FALLBACK_MODEL, str)
        assert "e5" in mod.FALLBACK_MODEL.lower()
