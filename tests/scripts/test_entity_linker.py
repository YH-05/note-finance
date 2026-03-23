"""Tests for scripts/entity_linker.py.

entity_linker.py の --instance パラメータ追加と Neo4jClient 汎用化のユニットテスト。
load_instance_config / Neo4jClient / CLI 引数パース / 後方互換性を検証。
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
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
        assert result["user"] == "neo4j"
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

        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if it exists
            os.environ.pop("NEO4J_ENVTEST_PASSWORD", None)
            with pytest.raises(ValueError, match="NEO4J_ENVTEST_PASSWORD"):
                load_instance_config("envtest", config_dir=config_dir_with_envvar)


# ---------------------------------------------------------------------------
# Neo4jClient rename tests
# ---------------------------------------------------------------------------


class TestNeo4jClient:
    """Neo4jClient クラスのテスト（CreatorNeo4jClient からのリネーム）。"""

    def test_正常系_Neo4jClientクラスが存在する(self) -> None:
        """CreatorNeo4jClient が Neo4jClient にリネームされていること。"""
        from entity_linker import Neo4jClient

        assert Neo4jClient is not None

    @patch("entity_linker.GraphDatabase")
    def test_正常系_デフォルト引数でcreatorに接続する(
        self, mock_gdb: MagicMock
    ) -> None:
        """引数なしで Neo4jClient() を作成すると creator のデフォルト値が使用されること。"""
        from entity_linker import Neo4jClient

        client = Neo4jClient()
        mock_gdb.driver.assert_called_once()
        call_args = mock_gdb.driver.call_args
        # Default URI should be creator's bolt://localhost:7689
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
        from entity_linker import load_instance_config, main

        # Create input file
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps({"entities": [], "concepts": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        # Mock the client
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
                "password": "gomasuke",
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


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """既存の creator-enrichment スキルとの後方互換性テスト。"""

    def test_正常系_resolve_entity_by_textがNeo4jClientを受け入れる(self) -> None:
        """resolve_entity_by_text が Neo4jClient 型を受け入れること。"""
        # Type signature should accept Neo4jClient
        import inspect

        from entity_linker import Neo4jClient, resolve_entity_by_text

        sig = inspect.signature(resolve_entity_by_text)
        params = list(sig.parameters.keys())
        assert "client" in params

    def test_正常系_resolve_concept_by_textがNeo4jClientを受け入れる(self) -> None:
        """resolve_concept_by_text が Neo4jClient 型を受け入れること。"""
        import inspect

        from entity_linker import Neo4jClient, resolve_concept_by_text

        sig = inspect.signature(resolve_concept_by_text)
        params = list(sig.parameters.keys())
        assert "client" in params

    def test_正常系_resolve_allがNeo4jClientを受け入れる(self) -> None:
        """resolve_all が Neo4jClient 型を受け入れること。"""
        import inspect

        from entity_linker import Neo4jClient, resolve_all

        sig = inspect.signature(resolve_all)
        params = list(sig.parameters.keys())
        assert "client" in params
