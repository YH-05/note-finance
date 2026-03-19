"""kg_accuracy_judge.py のユニットテスト。

Anthropic API はモックで代替し、API不要でテスト実行可能。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from kg_accuracy_judge import (
    AccuracyEvaluation,
    _content_hash,
    _is_cache_valid,
    _load_cache,
    _save_cache,
    evaluate_batch,
    evaluate_single,
    sample_facts,
)


# ---------------------------------------------------------------------------
# _content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_正常系_同じ入力で同じハッシュ(self) -> None:
        h1 = _content_hash("test content")
        h2 = _content_hash("test content")
        assert h1 == h2

    def test_正常系_異なる入力で異なるハッシュ(self) -> None:
        h1 = _content_hash("content A")
        h2 = _content_hash("content B")
        assert h1 != h2

    def test_正常系_16文字のハッシュを返す(self) -> None:
        h = _content_hash("test")
        assert len(h) == 16


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_正常系_キャッシュの保存と読み込み(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        data = {"key1": {"value": 42}}
        _save_cache(cache_path, data)
        loaded = _load_cache(cache_path)
        assert loaded == data

    def test_エッジケース_存在しないファイルで空辞書(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "nonexistent.json"
        loaded = _load_cache(cache_path)
        assert loaded == {}

    def test_正常系_有効期限内はTrue(self) -> None:
        entry = {
            "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        assert _is_cache_valid(entry, ttl_days=30) is True

    def test_正常系_期限切れはFalse(self) -> None:
        entry = {
            "evaluated_at": "2020-01-01T00:00:00+00:00",
        }
        assert _is_cache_valid(entry, ttl_days=30) is False

    def test_エッジケース_evaluated_at未設定はFalse(self) -> None:
        assert _is_cache_valid({}, ttl_days=30) is False


# ---------------------------------------------------------------------------
# sample_facts
# ---------------------------------------------------------------------------


class TestSampleFacts:
    def test_正常系_サンプリングされる(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = [
            {
                "fact_id": f"fact_{i}",
                "content": f"Content {i}",
                "node_labels": ["Fact"],
                "source_title": "Test Source",
                "source_url": "https://example.com",
                "source_fetched_at": "2026-03-01",
            }
            for i in range(50)
        ]

        result = sample_facts(mock_session, sample_size=10)

        assert len(result) == 10

    def test_エッジケース_空の場合(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = []

        result = sample_facts(mock_session, sample_size=10)

        assert result == []

    def test_正常系_sample_sizeが全件より大きい場合(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = [
            {
                "fact_id": f"fact_{i}",
                "content": f"Content {i}",
                "node_labels": ["Fact"],
                "source_title": None,
                "source_url": None,
                "source_fetched_at": None,
            }
            for i in range(5)
        ]

        result = sample_facts(mock_session, sample_size=100)

        assert len(result) == 5


# ---------------------------------------------------------------------------
# evaluate_single
# ---------------------------------------------------------------------------


class TestEvaluateSingle:
    def test_正常系_LLM応答を正しくパースする(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='```json\n{"factual_correctness": 0.9, "source_grounding": 0.8, "temporal_validity": 0.7, "reasoning": "Good"}\n```'
            )
        ]
        mock_client.messages.create.return_value = mock_response

        fact = {
            "fact_id": "test_1",
            "content": "Apple revenue grew 10%",
            "source_title": "CNBC",
            "source_url": "https://cnbc.com/article",
            "source_fetched_at": "2026-03-01",
        }

        result = evaluate_single(fact, mock_client)

        assert result.factual_correctness == 0.9
        assert result.source_grounding == 0.8
        assert result.temporal_validity == 0.7
        assert result.overall == pytest.approx(0.9 * 0.4 + 0.8 * 0.3 + 0.7 * 0.3, abs=0.001)

    def test_異常系_パース失敗でデフォルト値(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="invalid response without json")]
        mock_client.messages.create.return_value = mock_response

        fact = {"fact_id": "test_2", "content": "test"}

        result = evaluate_single(fact, mock_client)

        assert result.factual_correctness == 0.5
        assert result.source_grounding == 0.5
        assert result.temporal_validity == 0.5


# ---------------------------------------------------------------------------
# evaluate_batch
# ---------------------------------------------------------------------------


class TestEvaluateBatch:
    def test_正常系_バッチ評価が動作する(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"factual_correctness": 0.8, "source_grounding": 0.7, "temporal_validity": 0.9, "reasoning": "ok"}'
            )
        ]
        mock_client.messages.create.return_value = mock_response

        facts = [
            {"fact_id": "f1", "content": "Fact 1"},
            {"fact_id": "f2", "content": "Fact 2"},
        ]

        cache_path = tmp_path / "cache.json"
        results = evaluate_batch(facts, mock_client, cache_path=cache_path)

        assert len(results) == 2
        assert all(r.factual_correctness == 0.8 for r in results)

    def test_正常系_キャッシュヒットでAPI呼び出しスキップ(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        content = "Cached fact content"
        cache_key = _content_hash(content)
        cache_data = {
            cache_key: {
                "fact_id": "cached_1",
                "factual_correctness": 0.95,
                "source_grounding": 0.9,
                "temporal_validity": 0.85,
                "overall": 0.9,
                "reasoning": "cached",
                "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
            }
        }
        _save_cache(cache_path, cache_data)

        mock_client = MagicMock()
        facts = [{"fact_id": "f1", "content": content}]

        results = evaluate_batch(facts, mock_client, cache_path=cache_path)

        assert len(results) == 1
        assert results[0].factual_correctness == 0.95
        mock_client.messages.create.assert_not_called()

    def test_異常系_API例外でフォールバック値(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        facts = [{"fact_id": "f1", "content": "test"}]
        cache_path = tmp_path / "cache.json"

        results = evaluate_batch(facts, mock_client, cache_path=cache_path)

        assert len(results) == 1
        assert results[0].overall == 0.5
