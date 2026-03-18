"""E2E integration tests for the nlm CLI.

These tests require a valid NotebookLM session and network access.
They are skipped in CI by default.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from notebooklm.cli.main import cli

pytestmark = pytest.mark.skipif(
    True,  # Always skip unless explicitly enabled
    reason="E2E tests require NotebookLM session (run with --run-e2e)",
)


class TestCLIE2E:
    """CLI の E2E テスト。"""

    def test_session_status(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0

    def test_notebook_list(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "notebook", "list"])
        assert result.exit_code == 0
