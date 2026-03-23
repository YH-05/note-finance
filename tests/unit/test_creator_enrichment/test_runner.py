"""creator_enrichment_runner.py のテスト.

main() の全パスを検証する:
- 正常終了
- ValueError → sys.exit(1)
- FileNotFoundError → sys.exit(1)
- FatalError → sys.exit(1)
- KeyboardInterrupt → sys.exit(0)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestMainNormalExit:
    """main() 正常終了のテスト."""

    @patch("creator_enrichment.orchestrator.CreatorEnrichmentOrchestrator")
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_正常系_orchestratorが正常に完了する(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_orch_cls: MagicMock,
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


class TestMainFatalError:
    """main() FatalError のテスト."""

    @patch("creator_enrichment.orchestrator.CreatorEnrichmentOrchestrator")
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_異常系_FatalErrorでsys_exit_1(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_orch_cls: MagicMock,
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

    @patch("creator_enrichment.orchestrator.CreatorEnrichmentOrchestrator")
    @patch("creator_enrichment.config.load_config")
    @patch("creator_enrichment.config.parse_args")
    def test_正常系_KeyboardInterruptでsys_exit_0(
        self,
        mock_parse: MagicMock,
        mock_load: MagicMock,
        mock_orch_cls: MagicMock,
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
