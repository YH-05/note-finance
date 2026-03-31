"""Tests for scripts/entity_linker.py.

entity_linker.py の --instance パラメータ追加と Neo4jClient 汎用化のユニットテスト。
load_instance_config / Neo4jClient / CLI 引数パース / 後方互換性 /
_NodeResolveConfig / バッチExact / URI マスキング / v3.0 EntityType 統合 /
名前正規化 / Identifier サポートを検証。
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from neo4j.exceptions import ClientError

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary neo4j-instances config directory."""
    cfg_dir = tmp_path / "data" / "config" / "neo4j-instances"
    cfg_dir.mkdir(parents=True)

    # creator.yaml
    creator_yaml = cfg_dir / "creator.yaml"
    creator_yaml.write_text(
        "instance_name: creator\n"
        "connection:\n"
        "  bolt_uri: 'bolt://localhost:7689'\n"
        "  user: neo4j\n"
        "  password: 'creator_pass'\n",
        encoding="utf-8",
    )

    # research.yaml
    research_yaml = cfg_dir / "research.yaml"
    research_yaml.write_text(
        "instance_name: research\n"
        "connection:\n"
        "  bolt_uri: 'bolt://localhost:7688'\n"
        "  user: neo4j\n"
        "  password: 'research_pass'\n",
        encoding="utf-8",
    )

    return cfg_dir


@pytest.fixture
def config_dir_with_envvar(tmp_path: Path) -> Path:
    """Create config with environment variable reference for password."""
    cfg_dir = tmp_path / "data" / "config" / "neo4j-instances"
    cfg_dir.mkdir(parents=True)

    envvar_yaml = cfg_dir / "envtest.yaml"
    envvar_yaml.write_text(
        "instance_name: envtest\n"
        "connection:\n"
        "  bolt_uri: 'bolt://localhost:7690'\n"
        "  user: neo4j\n"
        "  password: '${NEO4J_ENVTEST_PASSWORD}'\n",
        encoding="utf-8",
    )

    return cfg_dir


@pytest.fixture
def config_dir_malformed(tmp_path: Path) -> Path:
    """Create config with missing connection key."""
    cfg_dir = tmp_path / "data" / "config" / "neo4j-instances"
    cfg_dir.mkdir(parents=True)

    malformed_yaml = cfg_dir / "malformed.yaml"
    malformed_yaml.write_text(
        "instance_name: malformed\n# missing connection key\n",
        encoding="utf-8",
    )

    return cfg_dir


# ---------------------------------------------------------------------------
# load_instance_config tests
# ---------------------------------------------------------------------------


class TestLoadInstanceConfig:
    """load_instance_config 関数のテスト。"""

    def test_正常系_creatorインスタンスの設定を読み込む(self, config_dir: Path) -> None:
        """creator.yaml から接続情報を読み込めること。"""
        from entity_linker import load_instance_config

        result = load_instance_config("creator", config_dir=config_dir)

        assert result["bolt_uri"] == "bolt://localhost:7689"
        assert result["user"] == "neo4j"
        assert result["password"] == "creator_pass"

    def test_正常系_researchインスタンスの設定を読み込む(
        self, config_dir: Path
    ) -> None:
        """research.yaml から接続情報を読み込めること。"""
        from entity_linker import load_instance_config

        result = load_instance_config("research", config_dir=config_dir)

        assert result["bolt_uri"] == "bolt://localhost:7688"
        assert result["password"] == "research_pass"

    def test_正常系_環境変数参照のパスワードを解決する(
        self, config_dir_with_envvar: Path
    ) -> None:
        """${ENV_VAR} 形式のパスワードが環境変数から解決されること。"""
        from entity_linker import load_instance_config

        with patch.dict(os.environ, {"NEO4J_ENVTEST_PASSWORD": "secret123"}):
            result = load_instance_config("envtest", config_dir=config_dir_with_envvar)

        assert result["password"] == "secret123"

    def test_異常系_存在しないインスタンスでFileNotFoundError(
        self, config_dir: Path
    ) -> None:
        """存在しないインスタンス名で FileNotFoundError を発生させること。"""
        from entity_linker import load_instance_config

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_instance_config("nonexistent", config_dir=config_dir)

    def test_異常系_環境変数未設定でValueError(
        self, config_dir_with_envvar: Path
    ) -> None:
        """環境変数が未設定の場合に ValueError を発生させること。"""
        from entity_linker import load_instance_config

        env_without_secret = {
            k: v for k, v in os.environ.items() if k != "NEO4J_ENVTEST_PASSWORD"
        }
        with (
            patch.dict(os.environ, env_without_secret, clear=True),
            pytest.raises(ValueError, match="NEO4J_ENVTEST_PASSWORD"),
        ):
            load_instance_config("envtest", config_dir=config_dir_with_envvar)

    def test_異常系_パストラバーサル文字列でValueError(self, config_dir: Path) -> None:
        """パストラバーサルを含むインスタンス名で ValueError を発生させること。"""
        from entity_linker import load_instance_config

        with pytest.raises(ValueError, match="Invalid instance name"):
            load_instance_config("../../etc/passwd", config_dir=config_dir)

    def test_異常系_malformed_YAMLでKeyError(self, config_dir_malformed: Path) -> None:
        """connection キーが欠落した YAML で KeyError を発生させること。"""
        from entity_linker import load_instance_config

        with pytest.raises(KeyError):
            load_instance_config("malformed", config_dir=config_dir_malformed)


# ---------------------------------------------------------------------------
# _mask_uri tests
# ---------------------------------------------------------------------------


class TestMaskUri:
    """_mask_uri ヘルパー関数のテスト。"""

    def test_正常系_パスワードなしURIはそのまま返す(self) -> None:
        """パスワードを含まない bolt URI はそのまま返されること。"""
        from entity_linker import _mask_uri

        assert _mask_uri("bolt://localhost:7689") == "bolt://localhost:7689"

    def test_正常系_パスワード付きURIがマスクされる(self) -> None:
        """認証情報を含む URI でパスワードがマスクされること。"""
        from entity_linker import _mask_uri

        result = _mask_uri("bolt://neo4j:secret@example.com:7687")
        assert "secret" not in result
        assert "example.com" in result


# ---------------------------------------------------------------------------
# _NodeResolveConfig tests
# ---------------------------------------------------------------------------


class TestNodeResolveConfig:
    """_NodeResolveConfig と _build_result のテスト。"""

    def test_正常系_ENTITY_CONFIGが正しく定義されている(self) -> None:
        """_ENTITY_CONFIG の各フィールドが正しいこと。"""
        from entity_linker import _ENTITY_CONFIG

        assert _ENTITY_CONFIG.label == "Entity"
        assert _ENTITY_CONFIG.id_key == "entity_id"
        assert _ENTITY_CONFIG.key_key == "entity_key"

    def test_正常系_CONCEPT_CONFIGが正しく定義されている(self) -> None:
        """_CONCEPT_CONFIG の各フィールドが正しいこと。"""
        from entity_linker import _CONCEPT_CONFIG

        assert _CONCEPT_CONFIG.label == "Concept"
        assert _CONCEPT_CONFIG.id_key == "concept_id"
        assert _CONCEPT_CONFIG.key_key is None

    def test_正常系_build_resultがEntity用dictを構築する(self) -> None:
        """_build_result が entity_key を含む dict を返すこと。"""
        from entity_linker import _ENTITY_CONFIG, _build_result

        row = {"id": "eid1", "key": "Instagram::platform", "name": "Instagram"}
        result = _build_result(row, _ENTITY_CONFIG, "exact")

        assert result["entity_id"] == "eid1"
        assert result["entity_key"] == "Instagram::platform"
        assert result["match_layer"] == "exact"

    def test_正常系_build_resultがConcept用dictを構築する(self) -> None:
        """_build_result が concept_id のみの dict を返すこと。"""
        from entity_linker import _CONCEPT_CONFIG, _build_result

        row = {"id": "cid1", "name": "SNS集客"}
        result = _build_result(row, _CONCEPT_CONFIG, "exact")

        assert result["concept_id"] == "cid1"
        assert "entity_key" not in result


# ---------------------------------------------------------------------------
# Neo4jClient tests
# ---------------------------------------------------------------------------


class TestNeo4jClient:
    """Neo4jClient クラスのテスト。"""

    def test_正常系_Neo4jClientがエクスポートされ旧名が存在しない(self) -> None:
        """CreatorNeo4jClient が Neo4jClient にリネームされていること。"""
        import inspect

        import entity_linker

        assert hasattr(entity_linker, "Neo4jClient")
        assert inspect.isclass(entity_linker.Neo4jClient)
        assert not hasattr(entity_linker, "CreatorNeo4jClient"), "旧名が残存している"

    @patch("entity_linker.GraphDatabase")
    def test_正常系_デフォルト引数でcreatorに接続する(
        self, mock_gdb: MagicMock
    ) -> None:
        """引数なしで Neo4jClient() を作成するとデフォルト値が使用されること。"""
        from entity_linker import Neo4jClient

        client = Neo4jClient()
        mock_gdb.driver.assert_called_once()
        call_args = mock_gdb.driver.call_args
        assert call_args[0][0] == "bolt://localhost:7689"
        client.close()

    @patch("entity_linker.GraphDatabase")
    def test_正常系_カスタム接続情報で初期化できる(self, mock_gdb: MagicMock) -> None:
        """任意の接続情報を指定して Neo4jClient を作成できること。"""
        from entity_linker import Neo4jClient

        client = Neo4jClient(
            uri="bolt://localhost:7688",
            user="testuser",
            password="testpass",
        )
        mock_gdb.driver.assert_called_once_with(
            "bolt://localhost:7688", auth=("testuser", "testpass")
        )
        client.close()

    @patch("entity_linker.GraphDatabase")
    def test_正常系_queryがexecute_readで結果を返す(self, mock_gdb: MagicMock) -> None:
        """query() が session.execute_read 経由でレコードを返すこと。"""
        from entity_linker import Neo4jClient

        mock_session = MagicMock()
        mock_session.execute_read.return_value = [{"key": "value"}]
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value.session.return_value = mock_session

        client = Neo4jClient()
        result = client.query("RETURN 1 AS key")

        assert result == [{"key": "value"}]
        mock_session.execute_read.assert_called_once()
        client.close()

    @patch("entity_linker.GraphDatabase")
    def test_正常系_queryがfulltext_index欠落時に空リストを返す(
        self, mock_gdb: MagicMock
    ) -> None:
        """fulltext schema index が存在しない場合に [] が返ること。"""
        from entity_linker import Neo4jClient

        mock_session = MagicMock()
        mock_session.execute_read.side_effect = ClientError(
            "There is no such fulltext schema index: alias_fulltext"
        )
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value.session.return_value = mock_session

        client = Neo4jClient()
        result = client.query("CALL db.index.fulltext.queryNodes(...)")

        assert result == []
        client.close()

    @patch("entity_linker.GraphDatabase")
    def test_異常系_queryがClientError以外の例外をre_raiseする(
        self, mock_gdb: MagicMock
    ) -> None:
        """fulltext index 以外の ClientError はそのまま re-raise されること。"""
        from entity_linker import Neo4jClient

        mock_session = MagicMock()
        mock_session.execute_read.side_effect = RuntimeError("Connection refused")
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value.session.return_value = mock_session

        client = Neo4jClient()
        with pytest.raises(RuntimeError, match="Connection refused"):
            client.query("RETURN 1")
        client.close()


# ---------------------------------------------------------------------------
# CLI argument tests
# ---------------------------------------------------------------------------


class TestCLIArguments:
    """CLI 引数パースのテスト。"""

    def test_正常系_instanceオプションを受け付ける(self) -> None:
        """--instance オプションがパーサーに追加されていること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json", "--instance", "research"])
        assert args.instance == "research"

    def test_正常系_instanceデフォルト値はcreator(self) -> None:
        """--instance 未指定時のデフォルト値が 'creator' であること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json"])
        assert args.instance == "creator"

    def test_正常系_no_embeddingオプションを受け付ける(self) -> None:
        """--no-embedding オプションがパーサーに追加されていること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json", "--no-embedding"])
        assert args.no_embedding is True

    def test_正常系_output未指定でNone(self) -> None:
        """--output 未指定時にデフォルトが None であること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json"])
        assert args.output is None


# ---------------------------------------------------------------------------
# Integration: main function with --instance
# ---------------------------------------------------------------------------


class TestMainInstanceIntegration:
    """main 関数の --instance オプション統合テスト。"""

    @patch("entity_linker.Neo4jClient")
    def test_正常系_instance指定でload_instance_configが呼ばれる(
        self,
        mock_client_cls: MagicMock,
        tmp_path: Path,
        config_dir: Path,
    ) -> None:
        """--instance research を指定した場合、research.yaml の接続情報が使用されること。"""
        from entity_linker import main

        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps({"entities": [], "concepts": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        mock_instance = MagicMock()
        mock_instance.query.return_value = []
        mock_client_cls.return_value = mock_instance

        output_file = tmp_path / "output.json"

        with patch("entity_linker.load_instance_config") as mock_load_config:
            mock_load_config.return_value = {
                "bolt_uri": "bolt://localhost:7688",
                "user": "neo4j",
                "password": "research_pass",
            }
            with patch(
                "sys.argv",
                [
                    "entity_linker.py",
                    "--input",
                    str(input_file),
                    "--output",
                    str(output_file),
                    "--instance",
                    "research",
                ],
            ):
                main()

        mock_load_config.assert_called_once_with("research")
        mock_client_cls.assert_called_once_with(
            uri="bolt://localhost:7688",
            user="neo4j",
            password="research_pass",
        )

    @patch("entity_linker.Neo4jClient")
    def test_正常系_instance未指定でcreatorフォールバック(
        self,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--instance 未指定時に 'creator' がデフォルトで使用されること。"""
        from entity_linker import main

        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps({"entities": [], "concepts": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        mock_instance = MagicMock()
        mock_instance.query.return_value = []
        mock_client_cls.return_value = mock_instance

        output_file = tmp_path / "output.json"

        with patch("entity_linker.load_instance_config") as mock_load_config:
            mock_load_config.return_value = {
                "bolt_uri": "bolt://localhost:7689",
                "user": "neo4j",
                "password": "test_dummy_pass",
            }
            with patch(
                "sys.argv",
                [
                    "entity_linker.py",
                    "--input",
                    str(input_file),
                    "--output",
                    str(output_file),
                ],
            ):
                main()

        mock_load_config.assert_called_once_with("creator")

    @patch("entity_linker.Neo4jClient")
    def test_正常系_output未指定でresolved_json接尾辞が使われる(
        self,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--output 未指定時に input.resolved.json が出力されること。"""
        from entity_linker import main

        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps({"entities": [], "concepts": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        mock_instance = MagicMock()
        mock_instance.query.return_value = []
        mock_client_cls.return_value = mock_instance

        with patch("entity_linker.load_instance_config") as mock_load_config:
            mock_load_config.return_value = {
                "bolt_uri": "bolt://localhost:7689",
                "user": "neo4j",
                "password": "test_dummy_pass",
            }
            with patch(
                "sys.argv",
                ["entity_linker.py", "--input", str(input_file)],
            ):
                main()

        expected_output = tmp_path / "input.resolved.json"
        assert expected_output.exists()

    @patch("entity_linker.Neo4jClient")
    def test_異常系_存在しない入力ファイルでsys_exit(
        self,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """存在しない入力ファイルを指定した場合に SystemExit(1) が発生すること。"""
        from entity_linker import main

        nonexistent = tmp_path / "does_not_exist.json"

        with patch("entity_linker.load_instance_config") as mock_load_config:
            mock_load_config.return_value = {
                "bolt_uri": "bolt://localhost:7689",
                "user": "neo4j",
                "password": "test_dummy_pass",
            }
            with (
                patch(
                    "sys.argv",
                    ["entity_linker.py", "--input", str(nonexistent)],
                ),
                pytest.raises(SystemExit) as exc_info,
            ):
                main()

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """既存の creator-enrichment スキルとの後方互換性テスト。"""

    def test_正常系_resolve_entity_by_textがNeo4jClientを受け入れる(self) -> None:
        """resolve_entity_by_text が client パラメータを持つこと。"""
        import inspect

        from entity_linker import resolve_entity_by_text

        sig = inspect.signature(resolve_entity_by_text)
        params = list(sig.parameters.keys())
        assert "client" in params

    def test_正常系_resolve_concept_by_textがNeo4jClientを受け入れる(self) -> None:
        """resolve_concept_by_text が client パラメータを持つこと。"""
        import inspect

        from entity_linker import resolve_concept_by_text

        sig = inspect.signature(resolve_concept_by_text)
        params = list(sig.parameters.keys())
        assert "client" in params

    def test_正常系_resolve_allがNeo4jClientを受け入れる(self) -> None:
        """resolve_all が client パラメータを持つこと。"""
        import inspect

        from entity_linker import resolve_all

        sig = inspect.signature(resolve_all)
        params = list(sig.parameters.keys())
        assert "client" in params

    def test_正常系_resolve_by_embeddingがLiteral型を受け入れる(self) -> None:
        """resolve_by_embedding の target_type が Literal 型であること。"""
        import inspect
        from typing import get_type_hints

        from entity_linker import resolve_by_embedding

        hints = get_type_hints(resolve_by_embedding, include_extras=True)
        assert "target_type" in hints


# ---------------------------------------------------------------------------
# _load_embedding_model cache tests
# ---------------------------------------------------------------------------


class TestLoadEmbeddingModelCache:
    """_load_embedding_model の lru_cache テスト。"""

    def test_正常系_lru_cacheが設定されている(self) -> None:
        """_load_embedding_model に lru_cache が適用されていること。"""
        from entity_linker import _load_embedding_model

        assert hasattr(_load_embedding_model, "cache_info")


# ---------------------------------------------------------------------------
# v3.0 EntityType Consolidation tests
# ---------------------------------------------------------------------------


class TestEntityTypeConsolidation:
    """v3.0 EntityType 統合マッピングのテスト (42 -> 14 canonical types)。"""

    def test_正常系_既にcanonicalなタイプはそのまま返す(self) -> None:
        """canonical type は変換されないこと。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("company") == "company"
        assert consolidate_entity_type("person") == "person"
        assert consolidate_entity_type("index") == "index"
        assert consolidate_entity_type("broker") == "broker"

    def test_正常系_fintechがcompanyに統合される(self) -> None:
        """fintech が company に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("fintech") == "company"
        assert consolidate_entity_type("subsidiary") == "company"
        assert consolidate_entity_type("digital_bank") == "company"
        assert consolidate_entity_type("it_services") == "company"
        assert consolidate_entity_type("fintech_holding") == "company"

    def test_正常系_central_bankがorganizationに統合される(self) -> None:
        """central_bank 等が organization に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("central_bank") == "organization"
        assert consolidate_entity_type("government") == "organization"
        assert consolidate_entity_type("government_agency") == "organization"
        assert consolidate_entity_type("institution") == "organization"
        assert consolidate_entity_type("exchange") == "organization"

    def test_正常系_etfがinstrumentに統合される(self) -> None:
        """etf, currency 等が instrument に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("etf") == "instrument"
        assert consolidate_entity_type("currency") == "instrument"
        assert consolidate_entity_type("currency_pair") == "instrument"
        assert consolidate_entity_type("fund") == "instrument"
        assert consolidate_entity_type("bond") == "instrument"
        assert consolidate_entity_type("asset") == "instrument"

    def test_正常系_regionがcountryに統合される(self) -> None:
        """region が country に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("region") == "country"

    def test_正常系_modelがconceptに統合される(self) -> None:
        """model, method, theme 等が concept に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("model") == "concept"
        assert consolidate_entity_type("method") == "concept"
        assert consolidate_entity_type("theme") == "concept"
        assert consolidate_entity_type("article_proposal") == "concept"
        assert consolidate_entity_type("event") == "concept"

    def test_正常系_metricがindicatorに統合される(self) -> None:
        """metric が indicator に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("metric") == "indicator"

    def test_正常系_marketがsectorに統合される(self) -> None:
        """market が sector に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("market") == "sector"

    def test_正常系_datasetがproductに統合される(self) -> None:
        """dataset, data_center が product に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("dataset") == "product"
        assert consolidate_entity_type("data_center") == "product"

    def test_正常系_systemがtechnologyに統合される(self) -> None:
        """system が technology に統合されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("system") == "technology"

    def test_エッジケース_大文字混在タイプが正規化される(self) -> None:
        """大文字を含む entity_type が小文字に正規化されること。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("Company") == "company"
        assert consolidate_entity_type("ETF") == "instrument"

    def test_エッジケース_未知のタイプがそのまま返される(self) -> None:
        """未知の entity_type はそのまま返されること (warning ログ)。"""
        from entity_linker import consolidate_entity_type

        assert consolidate_entity_type("unknown_type") == "unknown_type"

    def test_正常系_VALID_ENTITY_TYPESに14タイプが含まれる(self) -> None:
        """VALID_ENTITY_TYPES が正確に 14 種であること。"""
        from entity_linker import VALID_ENTITY_TYPES

        assert len(VALID_ENTITY_TYPES) == 14
        assert "company" in VALID_ENTITY_TYPES
        assert "broker" in VALID_ENTITY_TYPES
        assert "product" in VALID_ENTITY_TYPES

    def test_正常系_全42マッピングが14タイプに収束する(self) -> None:
        """ENTITY_TYPE_CONSOLIDATION の全バリューが VALID_ENTITY_TYPES に含まれること。"""
        from entity_linker import ENTITY_TYPE_CONSOLIDATION, VALID_ENTITY_TYPES

        for source, target in ENTITY_TYPE_CONSOLIDATION.items():
            assert target in VALID_ENTITY_TYPES, (
                f"{source} -> {target} is not in VALID_ENTITY_TYPES"
            )


# ---------------------------------------------------------------------------
# v3.0 Name Normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeName:
    """v3.0 名前正規化のテスト。"""

    def test_正常系_全角英数字が半角に変換される(self) -> None:
        """全角英数字が半角に統一されること。"""
        from entity_linker import normalize_name

        assert normalize_name("ＡＢＣ１２３") == "ABC123"

    def test_正常系_余分なスペースが除去される(self) -> None:
        """先頭末尾と連続スペースが正規化されること。"""
        from entity_linker import normalize_name

        assert normalize_name("  Apple   Inc.  ") == "Apple Inc."

    def test_正常系_末尾句読点が除去される(self) -> None:
        """末尾の CJK 句読点・カンマ・セミコロンが除去されること。"""
        from entity_linker import normalize_name

        assert normalize_name("トヨタ自動車。") == "トヨタ自動車"
        assert normalize_name("Apple Inc.,") == "Apple Inc."
        assert normalize_name("Goldman Sachs;") == "Goldman Sachs"

    def test_正常系_通常の名前は変化しない(self) -> None:
        """正規化不要の名前はそのまま返されること。"""
        from entity_linker import normalize_name

        assert normalize_name("Apple Inc.") == "Apple Inc."
        assert normalize_name("BOJ") == "BOJ"


# ---------------------------------------------------------------------------
# v3.0 build_entity_key tests
# ---------------------------------------------------------------------------


class TestBuildEntityKey:
    """v3.0 entity_key 生成のテスト。"""

    def test_正常系_entity_keyが正しいフォーマットで生成される(self) -> None:
        """Name::type フォーマットで entity_key が生成されること。"""
        from entity_linker import build_entity_key

        assert build_entity_key("Apple Inc.", "company") == "Apple Inc.::company"
        assert build_entity_key("S&P 500", "index") == "S&P 500::index"
        assert build_entity_key("BOJ", "organization") == "BOJ::organization"


# ---------------------------------------------------------------------------
# v3.0 Identifier Support tests
# ---------------------------------------------------------------------------


class TestIdentifierSupport:
    """v3.0 Identifier ノード参照生成のテスト。"""

    def test_正常系_ticker付きエンティティからIdentifier参照が生成される(self) -> None:
        """ticker フィールドがある場合に Identifier 参照が返されること。"""
        from entity_linker import _build_identifier_ref

        entity = {"name": "Apple Inc.", "entity_type": "company", "ticker": "AAPL"}
        result = _build_identifier_ref(entity)

        assert result is not None
        assert result["type"] == "ticker"
        assert result["value"] == "AAPL"
        assert result["scheme"] == "exchange_ticker"

    def test_正常系_ticker未設定でNoneが返される(self) -> None:
        """ticker フィールドがない場合に None が返されること。"""
        from entity_linker import _build_identifier_ref

        entity = {"name": "Apple Inc.", "entity_type": "company"}
        assert _build_identifier_ref(entity) is None

    def test_エッジケース_空tickerでNoneが返される(self) -> None:
        """空文字列の ticker で None が返されること。"""
        from entity_linker import _build_identifier_ref

        entity = {"name": "Apple Inc.", "entity_type": "company", "ticker": ""}
        assert _build_identifier_ref(entity) is None

    def test_正常系_ticker値の前後空白が除去される(self) -> None:
        """ticker の前後空白が除去されること。"""
        from entity_linker import _build_identifier_ref

        entity = {"name": "Toyota", "entity_type": "company", "ticker": " 7203 "}
        result = _build_identifier_ref(entity)
        assert result is not None
        assert result["value"] == "7203"


# ---------------------------------------------------------------------------
# v3.0 LinkerSearchConfig tests
# ---------------------------------------------------------------------------


class TestLinkerSearchConfig:
    """LinkerSearchConfig の読み込みテスト。"""

    def test_正常系_存在しないファイルでデフォルト値が返る(
        self, tmp_path: Path
    ) -> None:
        """config ファイルが存在しない場合にデフォルト値が返されること。"""
        from entity_linker import LinkerSearchConfig, load_linker_config

        result = load_linker_config(tmp_path / "nonexistent.yaml")

        assert result == LinkerSearchConfig()
        assert result.fulltext_index == "research_entity_fulltext"
        assert result.alias_fulltext_index == "research_alias_fulltext"
        assert result.similarity_threshold == 0.85

    def test_正常系_YAMLファイルから設定を読み込む(self, tmp_path: Path) -> None:
        """YAML ファイルから search 設定が正しく読み込まれること。"""
        from entity_linker import load_linker_config

        config_file = tmp_path / "linker-config.yaml"
        config_file.write_text(
            "search:\n"
            "  fulltext_index: custom_entity_ft\n"
            "  alias_fulltext_index: custom_alias_ft\n"
            "  similarity_threshold: 0.90\n"
            "  max_candidates: 20\n"
            "  fulltext_score_threshold: 0.6\n",
            encoding="utf-8",
        )

        result = load_linker_config(config_file)

        assert result.fulltext_index == "custom_entity_ft"
        assert result.alias_fulltext_index == "custom_alias_ft"
        assert result.similarity_threshold == 0.90
        assert result.max_candidates == 20
        assert result.fulltext_score_threshold == 0.6


# ---------------------------------------------------------------------------
# v3.0 CLI argument tests
# ---------------------------------------------------------------------------


class TestV3CLIArguments:
    """v3.0 CLI 引数のテスト。"""

    def test_正常系_v3フラグを受け付ける(self) -> None:
        """--v3 フラグがパーサーに追加されていること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json", "--v3"])
        assert args.v3 is True

    def test_正常系_v3デフォルトはFalse(self) -> None:
        """--v3 未指定時のデフォルト値が False であること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json"])
        assert args.v3 is False

    def test_正常系_linker_configオプションを受け付ける(self) -> None:
        """--linker-config オプションがパーサーに追加されていること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(
            [
                "--input",
                "test.json",
                "--linker-config",
                "/path/to/config.yaml",
            ]
        )
        assert str(args.linker_config) == "/path/to/config.yaml"


# ---------------------------------------------------------------------------
# v3.0 Backward Compatibility tests
# ---------------------------------------------------------------------------


class TestV3BackwardCompatibility:
    """v3.0 追加パラメータの後方互換性テスト。"""

    def test_正常系_resolve_entity_by_textにuse_v3パラメータがある(self) -> None:
        """resolve_entity_by_text に use_v3 パラメータが存在すること。"""
        import inspect

        from entity_linker import resolve_entity_by_text

        sig = inspect.signature(resolve_entity_by_text)
        params = sig.parameters
        assert "use_v3" in params
        assert params["use_v3"].default is False

    def test_正常系_resolve_entity_by_textにsearch_configパラメータがある(self) -> None:
        """resolve_entity_by_text に search_config パラメータが存在すること。"""
        import inspect

        from entity_linker import resolve_entity_by_text

        sig = inspect.signature(resolve_entity_by_text)
        params = sig.parameters
        assert "search_config" in params
        assert params["search_config"].default is None

    def test_正常系_resolve_allにuse_v3パラメータがある(self) -> None:
        """resolve_all に use_v3 パラメータが存在すること。"""
        import inspect

        from entity_linker import resolve_all

        sig = inspect.signature(resolve_all)
        params = sig.parameters
        assert "use_v3" in params
        assert params["use_v3"].default is False

    def test_正常系_resolve_allにsearch_configパラメータがある(self) -> None:
        """resolve_all に search_config パラメータが存在すること。"""
        import inspect

        from entity_linker import resolve_all

        sig = inspect.signature(resolve_all)
        params = sig.parameters
        assert "search_config" in params
        assert params["search_config"].default is None

    def test_正常系_NORMALIZATION_RULESに14タイプ分のルールがある(self) -> None:
        """NORMALIZATION_RULES が 14 種のエンティティタイプをカバーすること。"""
        from entity_linker import NORMALIZATION_RULES, VALID_ENTITY_TYPES

        assert set(NORMALIZATION_RULES.keys()) == VALID_ENTITY_TYPES


# ---------------------------------------------------------------------------
# v3.0 _make_v3_entity_config tests
# ---------------------------------------------------------------------------


class TestMakeV3EntityConfig:
    """_make_v3_entity_config のテスト。"""

    def test_正常系_v3EntityConfigがsearch_configのインデックスを使用する(self) -> None:
        """v3 entity config が search_config のインデックス名を使用すること。"""
        from entity_linker import LinkerSearchConfig, _make_v3_entity_config

        search_config = LinkerSearchConfig(
            fulltext_index="custom_entity_ft",
            alias_fulltext_index="custom_alias_ft",
        )
        config = _make_v3_entity_config(search_config)

        assert config.label == "Entity"
        assert config.node_index == "custom_entity_ft"
        assert config.alias_index == "custom_alias_ft"
        assert config.id_key == "entity_id"
        assert config.key_key == "entity_key"


# ---------------------------------------------------------------------------
# _load_consolidation_rules tests (YAML SSoT 読み込み)
# ---------------------------------------------------------------------------


class TestLoadConsolidationRules:
    """_load_consolidation_rules 関数のテスト。"""

    def test_正常系_YAMLからconsolidation_rulesを読み込む(self, tmp_path: Path) -> None:
        """YAML の consolidation_rules.entity_type.mapping が読み込まれること。"""
        from entity_linker import _load_consolidation_rules

        schema_yaml = tmp_path / "knowledge-graph-schema.yaml"
        schema_yaml.write_text(
            "consolidation_rules:\n"
            "  entity_type:\n"
            "    mapping:\n"
            "      company: company\n"
            "      fintech: company\n"
            "      person: person\n",
            encoding="utf-8",
        )

        result = _load_consolidation_rules(schema_path=schema_yaml)

        assert result == {
            "company": "company",
            "fintech": "company",
            "person": "person",
        }

    def test_正常系_ENTITY_TYPE_CONSOLIDATIONがYAMLから読み込まれる(self) -> None:
        """ENTITY_TYPE_CONSOLIDATION がハードコードではなく YAML から読み込まれること。"""
        from entity_linker import ENTITY_TYPE_CONSOLIDATION

        # YAML にある全 42 マッピングが含まれていることを確認
        assert len(ENTITY_TYPE_CONSOLIDATION) >= 40
        assert ENTITY_TYPE_CONSOLIDATION.get("fintech") == "company"
        assert ENTITY_TYPE_CONSOLIDATION.get("etf") == "instrument"
        assert ENTITY_TYPE_CONSOLIDATION.get("region") == "country"

    def test_異常系_存在しないYAMLでFileNotFoundError(self, tmp_path: Path) -> None:
        """存在しない YAML ファイルパスで FileNotFoundError が発生すること。"""
        from entity_linker import _load_consolidation_rules

        nonexistent = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError, match=r"knowledge-graph-schema\.yaml"):
            _load_consolidation_rules(schema_path=nonexistent)

    def test_正常系_consolidation_rulesキーなしで空dictを返す(
        self, tmp_path: Path
    ) -> None:
        """consolidation_rules キーが存在しない YAML では空dict が返ること。"""
        from entity_linker import _load_consolidation_rules

        schema_yaml = tmp_path / "knowledge-graph-schema.yaml"
        schema_yaml.write_text(
            "version: 3.0\n",
            encoding="utf-8",
        )

        result = _load_consolidation_rules(schema_path=schema_yaml)

        assert result == {}
