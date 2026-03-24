"""session_memory.linker のユニットテスト.

4層照合戦略・Decision連携・fulltext index 検証を網羅する。
Neo4j 接続はモックで代替し、純粋にロジックをテストする。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from session_memory.linker import (
    LinkerConfig,
    LinkResult,
    NoteLinker,
    normalize_name,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_driver() -> MagicMock:
    """Neo4j ドライバーのモック."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver


@pytest.fixture
def default_config() -> LinkerConfig:
    """デフォルトのリンカー設定."""
    return LinkerConfig()


@pytest.fixture
def linker(mock_driver: MagicMock, default_config: LinkerConfig) -> NoteLinker:
    """NoteLinker のインスタンス（モックドライバー使用）."""
    return NoteLinker(driver=mock_driver, config=default_config)


# ---------------------------------------------------------------------------
# normalize_name テスト
# ---------------------------------------------------------------------------


class TestNormalizeName:
    """normalize_name() のテスト."""

    def test_正常系_全角を半角に変換(self) -> None:
        """NFKC正規化で全角英数字を半角に変換する."""
        assert normalize_name("Ｐｙｔｈｏｎ") == "Python"

    def test_正常系_前後空白の除去(self) -> None:
        """前後の空白を除去する."""
        assert normalize_name("  Neo4j  ") == "Neo4j"

    def test_正常系_内部空白の圧縮(self) -> None:
        """連続する空白を1つに圧縮する."""
        assert (
            normalize_name("Natural   Language   Processing")
            == "Natural Language Processing"
        )

    def test_正常系_末尾句読点の除去(self) -> None:
        """末尾のCJK句読点を除去する."""
        assert normalize_name("データ分析。") == "データ分析"
        assert normalize_name("機械学習、") == "機械学習"

    def test_正常系_空文字列(self) -> None:
        """空文字列はそのまま返す."""
        assert normalize_name("") == ""

    def test_正常系_変換不要な文字列(self) -> None:
        """変換不要な文字列はそのまま返す."""
        assert normalize_name("Python") == "Python"


# ---------------------------------------------------------------------------
# LinkerConfig テスト
# ---------------------------------------------------------------------------


class TestLinkerConfig:
    """LinkerConfig のデフォルト値テスト."""

    def test_正常系_デフォルト値が設定される(self) -> None:
        """デフォルト値が正しく設定されること."""
        config = LinkerConfig()
        assert config.entity_fulltext_index == "note_entity_fulltext"
        assert config.alias_fulltext_index == "note_alias_fulltext"
        assert config.levenshtein_threshold == 0.8
        assert config.embedding_threshold == 0.8

    def test_正常系_カスタム値を設定できる(self) -> None:
        """カスタム値で上書きできること."""
        config = LinkerConfig(
            entity_fulltext_index="custom_entity_idx",
            levenshtein_threshold=0.9,
        )
        assert config.entity_fulltext_index == "custom_entity_idx"
        assert config.levenshtein_threshold == 0.9


# ---------------------------------------------------------------------------
# LinkResult テスト
# ---------------------------------------------------------------------------


class TestLinkResult:
    """LinkResult のテスト."""

    def test_正常系_resolvedがTrue(self) -> None:
        """resolved=True のとき match_layer と matched_name が必須."""
        result = LinkResult(
            name="Python",
            resolved=True,
            match_layer="exact",
            matched_name="Python",
            node_id="abc123",
        )
        assert result.resolved is True
        assert result.match_layer == "exact"

    def test_正常系_resolvedがFalse(self) -> None:
        """resolved=False のとき match_layer は 'new'."""
        result = LinkResult(
            name="UnknownEntity",
            resolved=False,
            match_layer="new",
        )
        assert result.resolved is False
        assert result.match_layer == "new"


# ---------------------------------------------------------------------------
# Layer 1: entity_key exact match
# ---------------------------------------------------------------------------


class TestLayer1ExactMatch:
    """Layer 1: entity_key 完全一致テスト."""

    def test_正常系_entity_keyで完全一致(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """entity_key の完全一致でノードが見つかる."""
        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_read.return_value = [
            {
                "id": "node-1",
                "name": "Python",
                "entity_key": "Python::language",
            }
        ]

        result = linker.link_entity("Python", "language")
        assert result.resolved is True
        assert result.match_layer == "exact"
        assert result.node_id == "node-1"

    def test_正常系_entity_key不一致で次の層へ(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """entity_key が一致しない場合、Layer 2 以降にフォールスルー."""
        mock_session = mock_driver.session.return_value.__enter__.return_value
        # Layer 1: 不一致, Layer 2: 不一致, Layer 3: 不一致, Layer 4: 不一致
        mock_session.execute_read.return_value = []

        result = linker.link_entity("UnknownEntity", "unknown")
        assert result.resolved is False
        assert result.match_layer == "new"


# ---------------------------------------------------------------------------
# Layer 2: fulltext + Levenshtein
# ---------------------------------------------------------------------------


class TestLayer2FulltextLevenshtein:
    """Layer 2: fulltext + Levenshtein 類似度テスト."""

    def test_正常系_fulltextマッチでLevenshtein閾値超え(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """fulltext検索でヒットし、Levenshtein類似度が閾値を超える."""
        mock_session = mock_driver.session.return_value.__enter__.return_value

        # Layer 1: 不一致
        # Layer 2: fulltext + levenshtein で一致
        mock_session.execute_read.side_effect = [
            [],  # Layer 1: entity_key exact match → 不一致
            [
                {
                    "id": "node-2",
                    "name": "Pydantic",
                    "entity_key": "Pydantic::library",
                    "similarity": 0.95,
                }
            ],  # Layer 2: fulltext + levenshtein → 一致
        ]

        result = linker.link_entity("pydantic", "library")
        assert result.resolved is True
        assert result.match_layer == "fulltext"

    def test_正常系_Levenshtein閾値未満で次の層へ(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """fulltext検索でヒットしてもLevenshtein類似度が閾値未満なら次の層."""
        mock_session = mock_driver.session.return_value.__enter__.return_value

        # Layer 1: 不一致, Layer 2: 不一致, Layer 3: 不一致, Layer 4: スキップ
        mock_session.execute_read.side_effect = [
            [],  # Layer 1
            [],  # Layer 2 (閾値未満のため空)
            [],  # Layer 3
        ]

        with patch.object(linker, "_resolve_by_embedding", return_value=None):
            result = linker.link_entity("veryDifferentName", "library")
            assert result.resolved is False


# ---------------------------------------------------------------------------
# Layer 3: alias fulltext + ALIAS_OF
# ---------------------------------------------------------------------------


class TestLayer3AliasFulltext:
    """Layer 3: alias fulltext + ALIAS_OF テスト."""

    def test_正常系_aliasマッチでALIAS_OF辿り(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """alias fulltext検索で見つかり、ALIAS_OFリレーション経由で解決."""
        mock_session = mock_driver.session.return_value.__enter__.return_value

        mock_session.execute_read.side_effect = [
            [],  # Layer 1: 不一致
            [],  # Layer 2: 不一致
            [
                {
                    "id": "node-3",
                    "name": "インスタグラム",
                    "entity_key": "Instagram::platform",
                    "matched_alias": "インスタ",
                    "similarity": 0.85,
                }
            ],  # Layer 3: alias → 一致
        ]

        with patch.object(linker, "_resolve_by_embedding", return_value=None):
            result = linker.link_entity("インスタ", "platform")
            assert result.resolved is True
            assert result.match_layer == "alias"


# ---------------------------------------------------------------------------
# Layer 4: embedding cosine similarity
# ---------------------------------------------------------------------------


class TestLayer4EmbeddingCosine:
    """Layer 4: embedding cosine 類似度テスト."""

    def test_正常系_embedding類似度が閾値超えで解決(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """embedding cosine類似度が閾値を超える場合に解決."""
        mock_session = mock_driver.session.return_value.__enter__.return_value

        mock_session.execute_read.side_effect = [
            [],  # Layer 1
            [],  # Layer 2
            [],  # Layer 3
        ]

        mock_emb_result = LinkResult(
            name="機械学習",
            resolved=True,
            match_layer="embedding",
            matched_name="Machine Learning",
            node_id="node-4",
            similarity=0.88,
        )

        with patch.object(
            linker, "_resolve_by_embedding", return_value=mock_emb_result
        ):
            result = linker.link_entity("機械学習", "concept")
            assert result.resolved is True
            assert result.match_layer == "embedding"

    def test_正常系_embedderがNoneの場合はスキップ(
        self, mock_driver: MagicMock
    ) -> None:
        """embedder が None の場合、Layer 4 はスキップされる."""
        config = LinkerConfig()
        link = NoteLinker(driver=mock_driver, config=config, embedder=None)

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_read.side_effect = [
            [],  # Layer 1
            [],  # Layer 2
            [],  # Layer 3
        ]

        result = link.link_entity("SomeEntity", "unknown")
        assert result.resolved is False
        assert result.match_layer == "new"


# ---------------------------------------------------------------------------
# Decision ノードリンク
# ---------------------------------------------------------------------------


class TestDecisionLinking:
    """Decision ノードへのリンク試行テスト."""

    def test_正常系_Decisionノードにリンクできる(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """Decision ノードへのリンクが成功する."""
        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_read.return_value = [
            {
                "id": "decision-1",
                "summary": "Pydantic v2 を採用",
            }
        ]

        result = linker.link_decision("Pydantic v2 を採用")
        assert result.resolved is True
        assert result.node_id == "decision-1"

    def test_正常系_Decision不一致でresolvedがFalse(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """Decision が見つからない場合は resolved=False."""
        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_read.return_value = []

        result = linker.link_decision("存在しない決定事項")
        assert result.resolved is False


# ---------------------------------------------------------------------------
# fulltext index 未作成時の RuntimeError
# ---------------------------------------------------------------------------


class TestFulltextIndexValidation:
    """fulltext index 未作成時の RuntimeError テスト."""

    def test_異常系_entity_fulltext_index未作成でRuntimeError(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """entity fulltext index が存在しない場合に RuntimeError."""
        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_read.return_value = []  # index一覧に該当なし

        with pytest.raises(RuntimeError, match="fulltext index"):
            linker.verify_indexes()

    def test_正常系_fulltext_index存在時はエラーなし(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """fulltext index が存在する場合はエラーなし."""
        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_read.return_value = [
            {"name": "note_entity_fulltext"},
            {"name": "note_alias_fulltext"},
        ]

        # エラーが発生しないことを確認
        linker.verify_indexes()


# ---------------------------------------------------------------------------
# バッチリンク
# ---------------------------------------------------------------------------


class TestBatchLink:
    """バッチリンクのテスト."""

    def test_正常系_複数エンティティを一括リンク(
        self, linker: NoteLinker, mock_driver: MagicMock
    ) -> None:
        """複数のエンティティを一括でリンクできる."""
        mock_session = mock_driver.session.return_value.__enter__.return_value

        # 各エンティティの Layer 1 クエリ結果
        mock_session.execute_read.side_effect = [
            [{"id": "n1", "name": "Python", "entity_key": "Python::language"}],
            [{"id": "n2", "name": "Neo4j", "entity_key": "Neo4j::database"}],
        ]

        entities = [
            {"name": "Python", "entity_type": "language"},
            {"name": "Neo4j", "entity_type": "database"},
        ]

        results = linker.link_entities_batch(entities)
        assert len(results) == 2
        assert all(r.resolved for r in results)

    def test_エッジケース_空リストで空結果(self, linker: NoteLinker) -> None:
        """空のリストを渡すと空のリストが返る."""
        results = linker.link_entities_batch([])
        assert results == []
