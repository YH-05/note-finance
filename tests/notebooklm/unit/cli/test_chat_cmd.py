"""Tests for chat CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from notebooklm.cli.main import cli
from notebooklm.types import ChatResponse


class TestChatAskCommand:
    """chat ask コマンドのテスト。"""

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.chat.ChatService")
    def test_正常系_単一質問にJSON回答(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.chat.return_value = ChatResponse(
            notebook_id="abc-123",
            question="テスト質問",
            answer="テスト回答です。",
            citations=["Source 1"],
            suggested_followups=["追加質問"],
        )
        mock_service_cls.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "chat", "ask", "abc-123", "テスト質問"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["answer"] == "テスト回答です。"

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.chat.ChatService")
    def test_正常系_テキスト出力にQAが含まれる(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.chat.return_value = ChatResponse(
            notebook_id="abc-123",
            question="Q1",
            answer="A1",
        )
        mock_service_cls.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(cli, ["chat", "ask", "abc-123", "Q1"])
        assert result.exit_code == 0
        assert "Q: Q1" in result.output
        assert "A: A1" in result.output


class TestChatBatchCommand:
    """chat batch コマンドのテスト。"""

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.chat.ChatService")
    def test_正常系_バッチ処理の成功(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.chat.side_effect = [
            ChatResponse(notebook_id="abc-123", question="Q1", answer="A1"),
            ChatResponse(notebook_id="abc-123", question="Q2", answer="A2"),
        ]
        mock_service_cls.return_value = mock_service

        q_file = tmp_path / "questions.txt"
        q_file.write_text("Q1\nQ2\n")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["chat", "batch", "abc-123", "-f", str(q_file), "--batch-size", "3"],
        )
        assert result.exit_code == 0
        assert "2/2 成功" in result.output

    @patch("notebooklm.browser.manager.NotebookLMBrowserManager")
    @patch("notebooklm.services.chat.ChatService")
    def test_正常系_出力ディレクトリにファイル保存(
        self,
        mock_service_cls: MagicMock,
        mock_manager_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        mock_service = AsyncMock()
        mock_service.chat.return_value = ChatResponse(
            notebook_id="abc-123", question="Q1", answer="A1"
        )
        mock_service_cls.return_value = mock_service

        q_file = tmp_path / "questions.txt"
        q_file.write_text("Q1\n")
        out_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "chat",
                "batch",
                "abc-123",
                "-f",
                str(q_file),
                "-o",
                str(out_dir),
            ],
        )
        assert result.exit_code == 0
        assert out_dir.exists()
        json_files = list(out_dir.glob("batch_results_*.json"))
        assert len(json_files) == 1
        md_files = list(out_dir.glob("batch_results_*.md"))
        assert len(md_files) == 1

    def test_異常系_存在しない質問ファイル(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["chat", "batch", "abc-123", "-f", "/nonexistent/file.txt"],
        )
        assert result.exit_code != 0
