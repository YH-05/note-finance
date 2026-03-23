"""Tests for scripts/entity_linker.py.

entity_linker.py の --instance パラメータ追加と Neo4jClient 汎用化のユニットテスト。
load_instance_config / Neo4jClient / CLI 引数パース / 後方互換性 /
_NodeResolveConfig / バッチExact / URI マスキングを検証。
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
