"""validate_neo4j_schema.py の純粋関数に対するユニットテスト。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

# scripts/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from validate_neo4j_schema import (
    build_allowed_labels,
    check_cross_contamination,
    check_pascal_case_violations,
    check_unknown_labels,
    classify_db_labels,
    load_namespaces,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_namespaces() -> dict:
    return {
        "kg_v2": {
            "labels": ["Source", "Claim", "Entity"],
            "naming": "PascalCase",
        },
        "conversation": {
            "labels": ["ConversationSession", "Project"],
            "naming": "PascalCase",
        },
        "memory": {
            "root_label": "Memory",
            "sub_labels": ["Decision", "Theme"],
            "naming": "PascalCase",
        },
        "archived": {
            "labels": ["Archived"],
            "naming": "PascalCase",
        },
    }


@pytest.fixture()
def sample_allowed(sample_namespaces: dict) -> dict[str, str]:
    return build_allowed_labels(sample_namespaces)


# ---------------------------------------------------------------------------
# build_allowed_labels
# ---------------------------------------------------------------------------


class TestBuildAllowedLabels:
    def test_正常系_labels_keyが正しくマッピングされる(
        self, sample_namespaces: dict
    ) -> None:
        result = build_allowed_labels(sample_namespaces)
        assert result["Source"] == "kg_v2"
        assert result["Claim"] == "kg_v2"
        assert result["Entity"] == "kg_v2"

    def test_正常系_root_labelが正しくマッピングされる(
        self, sample_namespaces: dict
    ) -> None:
        result = build_allowed_labels(sample_namespaces)
        assert result["Memory"] == "memory"

    def test_正常系_sub_labelsが正しくマッピングされる(
        self, sample_namespaces: dict
    ) -> None:
        result = build_allowed_labels(sample_namespaces)
        assert result["Decision"] == "memory"
        assert result["Theme"] == "memory"

    def test_エッジケース_空の名前空間定義で空辞書(self) -> None:
        result = build_allowed_labels({})
        assert result == {}

    def test_エッジケース_キーなし名前空間でスキップ(self) -> None:
        result = build_allowed_labels({"empty": {"naming": "PascalCase"}})
        assert result == {}


# ---------------------------------------------------------------------------
# check_unknown_labels
# ---------------------------------------------------------------------------


class TestCheckUnknownLabels:
    def test_正常系_全ラベルが許可済みなら空リスト(
        self, sample_allowed: dict[str, str]
    ) -> None:
        db_labels = ["Source", "Claim", "Memory"]
        result = check_unknown_labels(db_labels, sample_allowed)
        assert result == []

    def test_異常系_未知ラベルが検出される(
        self, sample_allowed: dict[str, str]
    ) -> None:
        db_labels = ["Source", "UnknownLabel"]
        result = check_unknown_labels(db_labels, sample_allowed)
        assert len(result) == 1
        assert result[0]["label"] == "UnknownLabel"
        assert result[0]["namespace"] == "UNKNOWN"

    def test_エッジケース_空リストで空結果(
        self, sample_allowed: dict[str, str]
    ) -> None:
        assert check_unknown_labels([], sample_allowed) == []


# ---------------------------------------------------------------------------
# check_pascal_case_violations
# ---------------------------------------------------------------------------


class TestCheckPascalCaseViolations:
    def test_正常系_PascalCaseラベルは違反なし(self) -> None:
        result = check_pascal_case_violations(["Source", "Memory", "Archived"])
        assert result == []

    def test_異常系_小文字始まりラベルが検出される(self) -> None:
        result = check_pascal_case_violations(["Source", "content_theme", "decision"])
        assert len(result) == 2
        assert result[0]["label"] == "content_theme"
        assert result[1]["label"] == "decision"

    def test_エッジケース_空リストで空結果(self) -> None:
        assert check_pascal_case_violations([]) == []

    def test_エッジケース_空文字列ラベルでIndexError発生しない(self) -> None:
        result = check_pascal_case_violations(["", "Source"])
        assert result == []


# ---------------------------------------------------------------------------
# classify_db_labels
# ---------------------------------------------------------------------------


class TestClassifyDbLabels:
    def test_正常系_名前空間ごとに分類される(
        self, sample_allowed: dict[str, str]
    ) -> None:
        db_labels = ["Source", "Memory", "Decision"]
        result = classify_db_labels(db_labels, sample_allowed)
        assert "kg_v2" in result
        assert "Source" in result["kg_v2"]
        assert "memory" in result
        assert "Memory" in result["memory"]
        assert "Decision" in result["memory"]

    def test_異常系_未知ラベルはUNKNOWNに分類される(
        self, sample_allowed: dict[str, str]
    ) -> None:
        db_labels = ["Source", "LegacyNode"]
        result = classify_db_labels(db_labels, sample_allowed)
        assert "UNKNOWN" in result
        assert "LegacyNode" in result["UNKNOWN"]

    def test_エッジケース_空リストで空辞書(
        self, sample_allowed: dict[str, str]
    ) -> None:
        assert classify_db_labels([], sample_allowed) == {}


# ---------------------------------------------------------------------------
# load_namespaces
# ---------------------------------------------------------------------------


class TestLoadNamespaces:
    def test_正常系_namespacesセクションが読み込まれる(
        self, tmp_path: Path, sample_namespaces: dict
    ) -> None:
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text(
            yaml.dump({"namespaces": sample_namespaces}), encoding="utf-8"
        )
        result = load_namespaces(schema_file)
        assert "kg_v2" in result
        assert "memory" in result

    def test_異常系_namespacesなしでValueError(self, tmp_path: Path) -> None:
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text(yaml.dump({"nodes": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="namespaces section not found"):
            load_namespaces(schema_file)


# ---------------------------------------------------------------------------
# check_cross_contamination
# ---------------------------------------------------------------------------


class TestCheckCrossContamination:
    def test_正常系_汚染なしで空リスト(
        self, sample_allowed: dict[str, str]
    ) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []
        result = check_cross_contamination(mock_session, sample_allowed)
        assert result == []
        mock_session.run.assert_called_once()

    def test_異常系_汚染ありでリスト返却(
        self, sample_allowed: dict[str, str]
    ) -> None:
        mock_record = MagicMock()
        mock_record.__iter__ = lambda self: iter(
            [("labels", ["Memory", "Source"]), ("name", "bad_node")]
        )
        mock_record.keys.return_value = ["labels", "name"]
        mock_record.__getitem__ = lambda self, key: {
            "labels": ["Memory", "Source"],
            "name": "bad_node",
        }[key]

        mock_session = MagicMock()
        mock_session.run.return_value = [mock_record]
        result = check_cross_contamination(mock_session, sample_allowed)
        assert len(result) == 1
