"""validate_neo4j_schema.py の純粋関数に対するユニットテスト。"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

# scripts/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from validate_neo4j_schema import (
    _validate_output_path,
    _validate_uri_scheme,
    build_allowed_labels,
    build_report,
    check_cross_contamination,
    check_pascal_case_violations,
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

    def test_エッジケース_重複ラベルは後勝ち(self) -> None:
        namespaces = {
            "ns_a": {"labels": ["Foo"]},
            "ns_b": {"labels": ["Foo"]},
        }
        result = build_allowed_labels(namespaces)
        assert result["Foo"] == "ns_b"


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

    def test_正常系_unknown派生がclassifyと一致する(
        self, sample_allowed: dict[str, str]
    ) -> None:
        """classify_db_labels のUNKNOWNバケットからunknown_labelsを派生できる。"""
        db_labels = ["Source", "LegacyA", "LegacyB"]
        classified = classify_db_labels(db_labels, sample_allowed)
        unknown_labels = [
            {"label": label, "namespace": "UNKNOWN"}
            for label in classified.get("UNKNOWN", [])
        ]
        assert len(unknown_labels) == 2
        assert unknown_labels[0]["label"] == "LegacyA"


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
    def test_正常系_汚染なしで空リスト(self, sample_allowed: dict[str, str]) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []
        result = check_cross_contamination(mock_session, sample_allowed)
        assert result == []
        mock_session.run.assert_called_once()

    def test_異常系_汚染ありでリスト返却(self, sample_allowed: dict[str, str]) -> None:
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


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_正常系_固定datetimeでレポート生成(
        self, sample_allowed: dict[str, str]
    ) -> None:
        fixed_now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Source"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Source"]},
            now=fixed_now,
        )
        assert report["validation_date"] == "2026-03-15T12:00:00+00:00"
        assert report["overall_pass"] is True

    def test_異常系_unknownありでoverall_pass_false(
        self, sample_allowed: dict[str, str]
    ) -> None:
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Source", "Bad"],
            allowed=sample_allowed,
            unknown_labels=[{"label": "Bad", "namespace": "UNKNOWN"}],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Source"], "UNKNOWN": ["Bad"]},
        )
        assert report["overall_pass"] is False


# ---------------------------------------------------------------------------
# _validate_uri_scheme
# ---------------------------------------------------------------------------


class TestValidateUriScheme:
    def test_正常系_bolt_scheme(self) -> None:
        _validate_uri_scheme("bolt://localhost:7687")

    def test_正常系_neo4j_scheme(self) -> None:
        _validate_uri_scheme("neo4j://localhost:7687")

    def test_正常系_bolt_plus_s_scheme(self) -> None:
        _validate_uri_scheme("bolt+s://localhost:7687")

    def test_異常系_http_scheme(self) -> None:
        with pytest.raises(ValueError, match="Unsupported URI scheme"):
            _validate_uri_scheme("http://localhost:7687")

    def test_異常系_ftp_scheme(self) -> None:
        with pytest.raises(ValueError, match="Unsupported URI scheme"):
            _validate_uri_scheme("ftp://localhost:7687")


# ---------------------------------------------------------------------------
# _validate_output_path
# ---------------------------------------------------------------------------


class TestValidateOutputPath:
    def test_正常系_プロジェクト内パス(self) -> None:
        result = _validate_output_path("data/processed/test.json")
        assert result.is_absolute()

    def test_異常系_プロジェクト外パス(self) -> None:
        with pytest.raises(ValueError, match="Output path must be under"):
            _validate_output_path("/tmp/evil/output.json")
