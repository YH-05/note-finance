"""validate_neo4j_schema.py の純粋関数に対するユニットテスト。"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar
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
    check_constraints_and_indices,
    check_cross_contamination,
    check_entity_type_convergence,
    check_enum_source_type,
    check_multilabel_entity,
    check_pascal_case_violations,
    classify_db_labels,
    load_namespaces,
    load_v30_sections,
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
    def test_正常系_ontology_loaderからnamespacesが読み込まれる(self) -> None:
        """ontology_loader 経由で namespaces が返されることを確認。"""
        result = load_namespaces()
        assert "kg_v2" in result
        assert "memory" in result

    def test_正常系_namespacesにconversationが含まれる(self) -> None:
        """ontology_loader 経由で conversation 名前空間が含まれることを確認。"""
        result = load_namespaces()
        assert "conversation" in result

    def test_正常系_namespacesにarchivedが含まれる(self) -> None:
        """ontology_loader 経由で archived 名前空間が含まれることを確認。"""
        result = load_namespaces()
        assert "archived" in result


# ---------------------------------------------------------------------------
# load_v30_sections
# ---------------------------------------------------------------------------


class TestLoadV30Sections:
    def _make_v30_schema(
        self,
        tmp_path: Path,
        sample_namespaces: dict,
        *,
        include_multilabel_types: bool = True,
        include_consolidation_rules: bool = True,
        include_enum_validations: bool = True,
        include_source_type_normalization: bool = True,
    ) -> Path:
        schema: dict = {"version": "3.0", "namespaces": sample_namespaces}
        if include_multilabel_types:
            schema["multilabel_types"] = {
                "entity_labels": {"labels": {"Company": {"name_ja": "企業"}}}
            }
        if include_consolidation_rules:
            schema["consolidation_rules"] = {
                "entity_type": {"mapping": {"company": "company", "fintech": "company"}}
            }
        if include_enum_validations:
            schema["enum_validations"] = {
                "entity_type": {"values": ["company", "technology"]},
                "source_type": {"values": ["web", "news", "pdf", "original", "blog"]},
            }
        if include_source_type_normalization:
            schema["source_type_normalization"] = {
                "mapping": {"web page": "web", "news article": "news"}
            }
        schema_file = tmp_path / "schema_v30.yaml"
        schema_file.write_text(yaml.dump(schema), encoding="utf-8")
        return schema_file

    def test_正常系_全v30セクションが読み込まれる(self) -> None:
        """ontology_loader 経由で全 v3.0 セクションが返されることを確認。"""
        result = load_v30_sections()
        assert result["multilabel_types"] is not None
        assert result["consolidation_rules"] is not None
        assert result["enum_validations"] is not None
        assert result["source_type_normalization"] is not None

    def test_正常系_multilabel_typesの内容が読み込まれる(self) -> None:
        """ontology_loader 経由で multilabel_types の内容が返されることを確認。"""
        result = load_v30_sections()
        assert "entity_labels" in result["multilabel_types"]

    def test_正常系_consolidation_rulesの内容が読み込まれる(self) -> None:
        """ontology_loader 経由で consolidation_rules の内容が返されることを確認。"""
        result = load_v30_sections()
        mapping = result["consolidation_rules"]["entity_type"]["mapping"]
        assert mapping["company"] == "company"
        assert mapping["fintech"] == "company"

    def test_正常系_返却辞書のキーが常に4つ存在する(self) -> None:
        """返却辞書は常に 4 つのキーを持つ。"""
        result = load_v30_sections()
        assert set(result.keys()) == {
            "multilabel_types",
            "consolidation_rules",
            "enum_validations",
            "source_type_normalization",
        }


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


# ---------------------------------------------------------------------------
# check_multilabel_entity (v3.0)
# ---------------------------------------------------------------------------


class TestCheckMultilabelEntity:
    def _make_session(self, count: int) -> MagicMock:
        """count 件のシングルラベル Entity を返すモックセッションを生成。"""
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: count
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = mock_record
        return mock_session

    def test_正常系_シングルラベルなしでpass(self) -> None:
        mock_session = self._make_session(0)
        result = check_multilabel_entity(mock_session)
        assert result["single_label_count"] == 0
        assert result["pass"] is True
        assert result["warning"] is False

    def test_異常系_シングルラベルありでwarning(self) -> None:
        mock_session = self._make_session(42)
        result = check_multilabel_entity(mock_session)
        assert result["single_label_count"] == 42
        assert result["pass"] is False
        assert result["warning"] is True

    def test_エッジケース_single_returnがNoneでも正常動作(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = None
        result = check_multilabel_entity(mock_session)
        assert result["single_label_count"] == 0
        assert result["pass"] is True
        assert result["warning"] is False


# ---------------------------------------------------------------------------
# check_enum_source_type (v3.0)
# ---------------------------------------------------------------------------


class TestCheckEnumSourceType:
    ALLOWED: ClassVar[list[str]] = ["web", "news", "pdf", "original", "blog"]

    def _make_session(self, db_values: list[str]) -> MagicMock:
        mock_session = MagicMock()
        mock_records = []
        for v in db_values:
            r = MagicMock()
            r.__getitem__ = lambda self, key, _v=v: _v
            mock_records.append(r)
        mock_session.run.return_value = mock_records
        return mock_session

    def test_正常系_有効値のみでpass(self) -> None:
        mock_session = self._make_session(["web", "news", "pdf"])
        result = check_enum_source_type(mock_session, self.ALLOWED)
        assert result["pass"] is True
        assert result["invalid_values"] == []
        assert result["db_values"] == ["web", "news", "pdf"]

    def test_異常系_不正値ありでpass_false(self) -> None:
        mock_session = self._make_session(["web", "web_page", "invalid_type"])
        result = check_enum_source_type(mock_session, self.ALLOWED)
        assert result["pass"] is False
        assert "web_page" in result["invalid_values"]
        assert "invalid_type" in result["invalid_values"]

    def test_エッジケース_DB値空でpass(self) -> None:
        mock_session = self._make_session([])
        result = check_enum_source_type(mock_session, self.ALLOWED)
        assert result["pass"] is True
        assert result["db_values"] == []
        assert result["invalid_values"] == []

    def test_エッジケース_全5種の正規値でpass(self) -> None:
        mock_session = self._make_session(["web", "news", "pdf", "original", "blog"])
        result = check_enum_source_type(mock_session, self.ALLOWED)
        assert result["pass"] is True
        assert len(result["invalid_values"]) == 0


# ---------------------------------------------------------------------------
# check_entity_type_convergence (v3.0)
# ---------------------------------------------------------------------------


class TestCheckEntityTypeConvergence:
    ALLOWED: ClassVar[list[str]] = [
        "company",
        "technology",
        "organization",
        "person",
        "index",
        "indicator",
        "instrument",
        "commodity",
        "country",
        "sector",
        "concept",
        "regulation",
        "broker",
        "product",
    ]

    def _make_session(self, db_values: list[str]) -> MagicMock:
        mock_session = MagicMock()
        mock_records = []
        for v in db_values:
            r = MagicMock()
            r.__getitem__ = lambda self, key, _v=v: _v
            mock_records.append(r)
        mock_session.run.return_value = mock_records
        return mock_session

    def test_正常系_14種以内でpass(self) -> None:
        mock_session = self._make_session(["company", "technology", "organization"])
        result = check_entity_type_convergence(mock_session, self.ALLOWED)
        assert result["pass"] is True
        assert result["invalid_values"] == []
        assert result["type_count"] == 3
        assert result["max_allowed"] == 14

    def test_異常系_未マイグレーション値ありでpass_false(self) -> None:
        mock_session = self._make_session(["company", "central_bank", "fintech"])
        result = check_entity_type_convergence(mock_session, self.ALLOWED)
        assert result["pass"] is False
        assert "central_bank" in result["invalid_values"]
        assert "fintech" in result["invalid_values"]

    def test_正常系_全14種揃っていてもpass(self) -> None:
        mock_session = self._make_session(self.ALLOWED)
        result = check_entity_type_convergence(mock_session, self.ALLOWED)
        assert result["pass"] is True
        assert result["type_count"] == 14

    def test_エッジケース_DB値空でpass(self) -> None:
        mock_session = self._make_session([])
        result = check_entity_type_convergence(mock_session, self.ALLOWED)
        assert result["pass"] is True
        assert result["type_count"] == 0


# ---------------------------------------------------------------------------
# check_constraints_and_indices (v3.0)
# ---------------------------------------------------------------------------


class TestCheckConstraintsAndIndices:
    SCHEMA_CONSTRAINTS: ClassVar[list[dict[str, str]]] = [
        {"label": "Source", "property": "source_id", "type": "UNIQUE"},
        {"label": "Entity", "property": "entity_id", "type": "UNIQUE"},
    ]
    SCHEMA_INDICES: ClassVar[list[dict[str, str]]] = [
        {"label": "Entity", "property": "entity_type"},
        {"label": "Source", "property": "source_type"},
    ]

    def _make_session(
        self,
        constraint_rows: list[dict],
        index_rows: list[dict],
    ) -> MagicMock:
        """SHOW CONSTRAINTS / SHOW INDEXES の結果を返すモックセッション。"""

        def run_side_effect(query: str, **kwargs: object) -> list[MagicMock]:
            rows = []
            if "SHOW CONSTRAINTS" in query:
                for row in constraint_rows:
                    r = MagicMock()
                    r.__getitem__ = lambda self, key, _row=row: _row.get(key)
                    rows.append(r)
            elif "SHOW INDEXES" in query:
                for row in index_rows:
                    r = MagicMock()
                    r.__getitem__ = lambda self, key, _row=row: _row.get(key)
                    rows.append(r)
            return rows

        mock_session = MagicMock()
        mock_session.run.side_effect = run_side_effect
        return mock_session

    def test_正常系_全制約インデックスが存在でpass(self) -> None:
        constraint_rows = [
            {
                "labelsOrTypes": ["Source"],
                "properties": ["source_id"],
                "type": "UNIQUENESS",
            },
            {
                "labelsOrTypes": ["Entity"],
                "properties": ["entity_id"],
                "type": "UNIQUENESS",
            },
        ]
        index_rows = [
            {
                "labelsOrTypes": ["Entity"],
                "properties": ["entity_type"],
                "type": "BTREE",
            },
            {
                "labelsOrTypes": ["Source"],
                "properties": ["source_type"],
                "type": "BTREE",
            },
        ]
        mock_session = self._make_session(constraint_rows, index_rows)
        result = check_constraints_and_indices(
            mock_session, self.SCHEMA_CONSTRAINTS, self.SCHEMA_INDICES
        )
        assert result["pass"] is True
        assert result["missing_constraints"] == []
        assert result["missing_indices"] == []

    def test_異常系_制約欠落でpass_false(self) -> None:
        constraint_rows = [
            # Source の constraint のみ
            {
                "labelsOrTypes": ["Source"],
                "properties": ["source_id"],
                "type": "UNIQUENESS",
            },
        ]
        index_rows = [
            {
                "labelsOrTypes": ["Entity"],
                "properties": ["entity_type"],
                "type": "BTREE",
            },
            {
                "labelsOrTypes": ["Source"],
                "properties": ["source_type"],
                "type": "BTREE",
            },
        ]
        mock_session = self._make_session(constraint_rows, index_rows)
        result = check_constraints_and_indices(
            mock_session, self.SCHEMA_CONSTRAINTS, self.SCHEMA_INDICES
        )
        assert result["pass"] is False
        assert any(c["label"] == "Entity" for c in result["missing_constraints"])

    def test_異常系_インデックス欠落でpass_false(self) -> None:
        constraint_rows = [
            {
                "labelsOrTypes": ["Source"],
                "properties": ["source_id"],
                "type": "UNIQUENESS",
            },
            {
                "labelsOrTypes": ["Entity"],
                "properties": ["entity_id"],
                "type": "UNIQUENESS",
            },
        ]
        index_rows = [
            # entity_type インデックスのみ（source_type 欠落）
            {
                "labelsOrTypes": ["Entity"],
                "properties": ["entity_type"],
                "type": "BTREE",
            },
        ]
        mock_session = self._make_session(constraint_rows, index_rows)
        result = check_constraints_and_indices(
            mock_session, self.SCHEMA_CONSTRAINTS, self.SCHEMA_INDICES
        )
        assert result["pass"] is False
        assert any(i["label"] == "Source" for i in result["missing_indices"])

    def test_エッジケース_空のschema定義でpass(self) -> None:
        mock_session = self._make_session([], [])
        result = check_constraints_and_indices(mock_session, [], [])
        assert result["pass"] is True
        assert result["missing_constraints"] == []
        assert result["missing_indices"] == []

    def test_エッジケース_SHOW_CONSTRAINTSが例外でも安全に動作(self) -> None:
        """SHOW CONSTRAINTS が例外を投げても処理が中断しない。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Unsupported operation")
        result = check_constraints_and_indices(
            mock_session, self.SCHEMA_CONSTRAINTS, self.SCHEMA_INDICES
        )
        # 例外時は全制約・インデックスが欠落扱い
        assert result["missing_constraints"] == self.SCHEMA_CONSTRAINTS
        assert result["missing_indices"] == self.SCHEMA_INDICES


# ---------------------------------------------------------------------------
# build_report v3.0 拡張
# ---------------------------------------------------------------------------


class TestBuildReportV30:
    def test_正常系_v30チェック全passでoverall_pass_true(
        self, sample_allowed: dict[str, str]
    ) -> None:
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Source"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Source"]},
            multilabel_check={"single_label_count": 0, "pass": True, "warning": False},
            source_type_check={
                "db_values": ["web"],
                "invalid_values": [],
                "pass": True,
            },
            entity_type_check={
                "db_values": ["company"],
                "invalid_values": [],
                "type_count": 1,
                "max_allowed": 14,
                "pass": True,
            },
            constraints_check={
                "missing_constraints": [],
                "missing_indices": [],
                "db_constraint_count": 5,
                "db_index_count": 10,
                "pass": True,
            },
        )
        assert report["overall_pass"] is True

    def test_異常系_source_type不正値でoverall_pass_false(
        self, sample_allowed: dict[str, str]
    ) -> None:
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Source"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Source"]},
            source_type_check={
                "db_values": ["web", "invalid"],
                "invalid_values": ["invalid"],
                "pass": False,
            },
        )
        assert report["overall_pass"] is False

    def test_異常系_entity_type収束失敗でoverall_pass_false(
        self, sample_allowed: dict[str, str]
    ) -> None:
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Entity"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Entity"]},
            entity_type_check={
                "db_values": ["company", "central_bank"],
                "invalid_values": ["central_bank"],
                "type_count": 2,
                "max_allowed": 14,
                "pass": False,
            },
        )
        assert report["overall_pass"] is False

    def test_正常系_multilabel_warningはoverall_passに影響しない(
        self, sample_allowed: dict[str, str]
    ) -> None:
        """シングルラベル Entity は WARNING のみで overall_pass を False にしない。"""
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Entity"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Entity"]},
            multilabel_check={
                "single_label_count": 100,
                "pass": False,
                "warning": True,
            },
        )
        assert report["overall_pass"] is True

    def test_正常系_constraints_warningはoverall_passに影響しない(
        self, sample_allowed: dict[str, str]
    ) -> None:
        """制約・インデックスの欠落は WARNING のみで overall_pass を False にしない。"""
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Source"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Source"]},
            constraints_check={
                "missing_constraints": [
                    {"label": "Source", "property": "source_id", "type": "UNIQUE"}
                ],
                "missing_indices": [],
                "db_constraint_count": 0,
                "db_index_count": 10,
                "pass": False,
            },
        )
        assert report["overall_pass"] is True

    def test_正常系_v30チェックNoneでも従来動作と同一(
        self, sample_allowed: dict[str, str]
    ) -> None:
        """v3.0 チェックが None の場合は従来の build_report と同一結果。"""
        report = build_report(
            schema_path="test.yaml",
            db_labels=["Source"],
            allowed=sample_allowed,
            unknown_labels=[],
            pascal_violations=[],
            contamination=[],
            classified={"kg_v2": ["Source"]},
        )
        assert report["overall_pass"] is True
        assert report["checks"]["multilabel_entity"] is None
        assert report["checks"]["source_type_enum"] is None
        assert report["checks"]["entity_type_convergence"] is None
        assert report["checks"]["constraints_and_indices"] is None
