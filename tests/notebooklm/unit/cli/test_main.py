"""Tests for the nlm CLI main entry point."""

from __future__ import annotations

from click.testing import CliRunner

from notebooklm.cli.main import cli


class TestCLIMainGroup:
    """CLI メイングループのテスト。"""

    def test_正常系_ヘルプメッセージが表示される(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "nlm" in result.output
        assert "notebook" in result.output
        assert "chat" in result.output
        assert "source" in result.output

    def test_正常系_サブグループ一覧が含まれる(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        for cmd in [
            "notebook",
            "source",
            "chat",
            "note",
            "audio",
            "studio",
            "session",
            "workflow",
        ]:
            assert cmd in result.output, f"'{cmd}' not found in help output"

    def test_正常系_notebookサブグループのヘルプ(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["notebook", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "summary" in result.output
        assert "delete" in result.output

    def test_正常系_chatサブグループのヘルプ(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["chat", "--help"])
        assert result.exit_code == 0
        assert "ask" in result.output
        assert "batch" in result.output
        assert "history" in result.output
        assert "clear" in result.output
        assert "configure" in result.output

    def test_正常系_sourceサブグループのヘルプ(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["source", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "add-text" in result.output
        assert "add-url" in result.output
        assert "add-file" in result.output

    def test_正常系_グローバルオプションが認識される(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "--no-headless", "--help"])
        assert result.exit_code == 0

    def test_異常系_存在しないコマンドでエラー(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent"])
        assert result.exit_code != 0
