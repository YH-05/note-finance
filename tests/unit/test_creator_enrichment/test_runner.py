"""creator_enrichment_runner.py のテスト.

main() の全パスを検証する:
- 正常終了（bootstrap + orchestrator 正常完了）
- ValueError → sys.exit(1)
- FileNotFoundError → sys.exit(1)
- Bootstrap 失敗 → sys.exit(1)
- FatalError → sys.exit(1)
- KeyboardInterrupt → sys.exit(0)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_bootstrap() -> tuple[MagicMock, MagicMock, MagicMock]:
    """_bootstrap() のモック戻り値を生成する."""
    driver = MagicMock()
    neo4j_client = MagicMock()
    anthropic_client = MagicMock()
    return driver, neo4j_client, anthropic_client


class TestMainNormalExit:
    """main() 正常終了のテスト."""

    @patch("scripts.creator_enrichment_runner._bootstrap", return_value=_mock_bootstrap())
    @patch("creator_enrichment.orchestrator.CreatorEnrichmentOrchestrator")
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_正常系_orchestratorが正常に完了する(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_orch_cls: MagicMock,
        mock_bootstrap: MagicMock,
    ) -> None:
        """正常系: orchestrator.run() が正常終了する."""
        from scripts.creator_enrichment_runner import main

        mock_config = MagicMock()
        mock_config.until_time = "23:30"
        mock_config.genre = None
        mock_config.dry_run = False
        mock_load.return_value = mock_config
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        main()

        mock_parse.assert_called_once()
        mock_load.assert_called_once()
        mock_bootstrap.assert_called_once()
        mock_orch.run.assert_called_once()


class TestMainConfigError:
    """main() 設定エラーのテスト."""

    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_異常系_ValueErrorでsys_exit_1(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """ValueError で sys.exit(1) が呼ばれる."""
        from scripts.creator_enrichment_runner import main

        mock_load.side_effect = ValueError("Invalid genre")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_異常系_FileNotFoundErrorでsys_exit_1(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """FileNotFoundError で sys.exit(1) が呼ばれる."""
        from scripts.creator_enrichment_runner import main

        mock_load.side_effect = FileNotFoundError("Config not found")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1


class TestMainBootstrapError:
    """main() ブートストラップ失敗のテスト."""

    @patch(
        "scripts.creator_enrichment_runner._bootstrap",
        side_effect=ConnectionError("Neo4j not available"),
    )
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_異常系_Bootstrap失敗でsys_exit_1(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_bootstrap: MagicMock,
    ) -> None:
        """Bootstrap 失敗で sys.exit(1) が呼ばれる."""
        from scripts.creator_enrichment_runner import main

        mock_config = MagicMock()
        mock_config.until_time = "23:30"
        mock_config.genre = None
        mock_config.dry_run = False
        mock_load.return_value = mock_config

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1


class TestMainFatalError:
    """main() FatalError のテスト."""

    @patch("scripts.creator_enrichment_runner._bootstrap", return_value=_mock_bootstrap())
    @patch("creator_enrichment.orchestrator.CreatorEnrichmentOrchestrator")
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_異常系_FatalErrorでsys_exit_1(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_orch_cls: MagicMock,
        mock_bootstrap: MagicMock,
    ) -> None:
        """FatalError で sys.exit(1) が呼ばれる."""
        from creator_enrichment.orchestrator import FatalError
        from scripts.creator_enrichment_runner import main

        mock_config = MagicMock()
        mock_config.until_time = "23:30"
        mock_config.genre = None
        mock_config.dry_run = False
        mock_load.return_value = mock_config
        mock_orch = MagicMock()
        mock_orch.run.side_effect = FatalError("5 consecutive errors")
        mock_orch_cls.return_value = mock_orch

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1


class TestMainKeyboardInterrupt:
    """main() KeyboardInterrupt のテスト."""

    @patch("scripts.creator_enrichment_runner._bootstrap", return_value=_mock_bootstrap())
    @patch("creator_enrichment.orchestrator.CreatorEnrichmentOrchestrator")
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_正常系_KeyboardInterruptでsys_exit_0(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_orch_cls: MagicMock,
        mock_bootstrap: MagicMock,
    ) -> None:
        """KeyboardInterrupt で sys.exit(0) が呼ばれる."""
        from scripts.creator_enrichment_runner import main

        mock_config = MagicMock()
        mock_config.until_time = "23:30"
        mock_config.genre = None
        mock_config.dry_run = False
        mock_load.return_value = mock_config
        mock_orch = MagicMock()
        mock_orch.run.side_effect = KeyboardInterrupt()
        mock_orch_cls.return_value = mock_orch

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0


class TestNeo4jClientAdapter:
    """_Neo4jClientAdapter のテスト."""

    def test_正常系_paramsなしでqueryが呼ばれる(self) -> None:
        """params=None 時に **params なしで query が呼ばれる."""
        from scripts.creator_enrichment_runner import _Neo4jClientAdapter

        mock_client = MagicMock()
        mock_client.query.return_value = [{"genre": "career", "content_count": 10}]

        adapter = _Neo4jClientAdapter(mock_client)
        result = adapter.execute_query("MATCH (n) RETURN n")

        mock_client.query.assert_called_once_with("MATCH (n) RETURN n")
        assert result == [{"genre": "career", "content_count": 10}]

    def test_正常系_paramsありでqueryが呼ばれる(self) -> None:
        """params 指定時に **params で query が呼ばれる."""
        from scripts.creator_enrichment_runner import _Neo4jClientAdapter

        mock_client = MagicMock()
        mock_client.query.return_value = [{"name": "test"}]

        adapter = _Neo4jClientAdapter(mock_client)
        result = adapter.execute_query("MATCH (n {id: $id}) RETURN n", {"id": "abc"})

        mock_client.query.assert_called_once_with("MATCH (n {id: $id}) RETURN n", id="abc")
        assert result == [{"name": "test"}]
