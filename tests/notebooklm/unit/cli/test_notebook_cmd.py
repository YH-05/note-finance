"""Tests for notebook CLI subcommands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from notebooklm.cli.main import cli
from notebooklm.types import NotebookInfo


class TestNotebookListCommand:
    """notebook list コマンドのテスト。"""

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.notebook.NotebookService")
    def test_正常系_一覧をJSON出力(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.list_notebooks.return_value = [
            NotebookInfo(
                notebook_id="abc-123",
                title="Test Notebook",
                source_count=3,
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        mock_service_cls.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "notebook", "list"])
        assert result.exit_code == 0
        assert "abc-123" in result.output
        assert "Test Notebook" in result.output

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.notebook.NotebookService")
    def test_正常系_空一覧のメッセージ(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.list_notebooks.return_value = []
        mock_service_cls.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["notebook", "list"])
        assert result.exit_code == 0
        assert "ノートブックはありません" in result.output


class TestNotebookCreateCommand:
    """notebook create コマンドのテスト。"""

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.notebook.NotebookService")
    def test_正常系_ノートブック作成(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.create_notebook.return_value = NotebookInfo(
            notebook_id="new-123",
            title="New Notebook",
        )
        mock_service_cls.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["notebook", "create", "New Notebook"])
        assert result.exit_code == 0
        assert "作成完了" in result.output
