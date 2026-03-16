"""Unit tests for --provider option in pdf-pipeline CLI.

Tests cover:
- _build_pipeline_for_dir() provider_mode branching (auto/claude/gemini)
- _process_one_pdf() passes provider_mode to _build_pipeline_for_dir
- batch command --provider option parsing via Click CliRunner
- process command --provider option parsing via Click CliRunner
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from pdf_pipeline.cli.main import (
    _batch_parallel_async,
    _build_pipeline_for_dir,
    _process_one_pdf,
    batch,
    cli,
    process,
)
from pdf_pipeline.services.provider_chain import ProviderChain

# ---------------------------------------------------------------------------
# _build_pipeline_for_dir — provider_mode branching
# ---------------------------------------------------------------------------


class TestBuildPipelineForDirProviderMode:
    """Tests for provider_mode branching in _build_pipeline_for_dir.

    _build_pipeline_for_dir uses lazy local imports, so we patch at the
    actual module paths (not pdf_pipeline.cli.main.*).
    """

    def _call_build(
        self,
        tmp_path: Path,
        provider_mode: str,
        *,
        omit_provider_mode: bool = False,
    ) -> tuple[list[Any], MagicMock, MagicMock]:
        """Call _build_pipeline_for_dir.

        Returns (captured_providers, mock_gemini_instance, mock_claude_instance).
        """
        captured_providers: list[Any] = []

        mock_config = MagicMock()
        mock_config.model_copy.return_value = mock_config
        mock_config.noise_filter = MagicMock()

        # Use sentinel objects so we can do identity comparison (is)
        mock_gemini_instance = object()
        mock_claude_instance = object()

        def fake_provider_chain(providers: list[Any]) -> MagicMock:
            captured_providers.extend(providers)
            chain = MagicMock()
            chain.providers = providers
            return chain

        with (
            patch("pdf_pipeline.cli.main.load_config", return_value=mock_config),
            patch("pdf_pipeline.services.state_manager.StateManager"),
            patch(
                "pdf_pipeline.services.gemini_provider.GeminiCLIProvider",
                return_value=mock_gemini_instance,
            ),
            patch(
                "pdf_pipeline.services.claude_provider.ClaudeCodeProvider",
                return_value=mock_claude_instance,
            ),
            patch(
                "pdf_pipeline.services.provider_chain.ProviderChain",
                side_effect=fake_provider_chain,
            ),
            patch("pdf_pipeline.core.pipeline.PdfPipeline"),
            patch("pdf_pipeline.core.markdown_converter.MarkdownConverter"),
            patch("pdf_pipeline.core.chunker.MarkdownChunker"),
            patch("pdf_pipeline.core.noise_filter.NoiseFilter"),
            patch("pdf_pipeline.core.table_detector.TableDetector"),
            patch("pdf_pipeline.core.table_reconstructor.TableReconstructor"),
            patch("pdf_pipeline.cli.main.PdfScanner"),
        ):
            if omit_provider_mode:
                _build_pipeline_for_dir(
                    input_dir=tmp_path,
                    output_dir=tmp_path / "out",
                    config_path=tmp_path / "config.yaml",
                )
            else:
                _build_pipeline_for_dir(
                    input_dir=tmp_path,
                    output_dir=tmp_path / "out",
                    config_path=tmp_path / "config.yaml",
                    provider_mode=provider_mode,  # type: ignore[arg-type]
                )

        return captured_providers, mock_gemini_instance, mock_claude_instance

    def test_正常系_autoモードはGeminiとClaudeの2プロバイダー(
        self, tmp_path: Path
    ) -> None:
        providers, _, _ = self._call_build(tmp_path, "auto")
        assert len(providers) == 2

    def test_正常系_autoモードの先頭プロバイダーはGeminiインスタンス(
        self, tmp_path: Path
    ) -> None:
        providers, mock_gemini, _ = self._call_build(tmp_path, "auto")
        assert providers[0] is mock_gemini

    def test_正常系_autoモードの2番目プロバイダーはClaudeインスタンス(
        self, tmp_path: Path
    ) -> None:
        providers, _, mock_claude = self._call_build(tmp_path, "auto")
        assert providers[1] is mock_claude

    def test_正常系_claudeモードはClaudeのみの1プロバイダー(
        self, tmp_path: Path
    ) -> None:
        providers, _, mock_claude = self._call_build(tmp_path, "claude")
        assert len(providers) == 1
        assert providers[0] is mock_claude

    def test_正常系_geminiモードはGeminiのみの1プロバイダー(
        self, tmp_path: Path
    ) -> None:
        providers, mock_gemini, _ = self._call_build(tmp_path, "gemini")
        assert len(providers) == 1
        assert providers[0] is mock_gemini

    def test_正常系_デフォルトはautoモードでプロバイダーが2つ(
        self, tmp_path: Path
    ) -> None:
        providers, _, _ = self._call_build(tmp_path, "auto", omit_provider_mode=True)
        assert len(providers) == 2


# ---------------------------------------------------------------------------
# _process_one_pdf — provider_mode 伝播
# ---------------------------------------------------------------------------


class TestProcessOnePdfProviderMode:
    """Tests that _process_one_pdf passes provider_mode to _build_pipeline_for_dir."""

    def test_正常系_provider_modeが_build_pipeline_for_dirに渡される(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")

        mock_result = {"status": "completed", "chunk_count": 3, "source_hash": "abc"}
        mock_pipeline = MagicMock()
        mock_pipeline.process_pdf.return_value = mock_result

        with (
            patch("pdf_pipeline.cli.main.PdfScanner") as mock_scanner_cls,
            patch(
                "pdf_pipeline.cli.main._build_pipeline_for_dir",
                return_value=mock_pipeline,
            ) as mock_build,
            patch(
                "pdf_pipeline.cli.main._compute_mirror_output_dir",
                return_value=tmp_path / "out",
            ),
        ):
            mock_scanner_cls.return_value.compute_sha256.return_value = (
                "abc" * 21 + "ab"
            )

            _process_one_pdf(
                pdf,
                index=1,
                total=1,
                output_base=tmp_path / "out",
                config_path=tmp_path / "config.yaml",
                extract=False,
                input_dir=tmp_path,
                provider_mode="claude",
            )

        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs["provider_mode"] == "claude"

    def test_正常系_デフォルトのprovider_modeはauto(self, tmp_path: Path) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")

        mock_result = {"status": "skipped", "source_hash": "abc"}
        mock_pipeline = MagicMock()
        mock_pipeline.process_pdf.return_value = mock_result

        with (
            patch("pdf_pipeline.cli.main.PdfScanner") as mock_scanner_cls,
            patch(
                "pdf_pipeline.cli.main._build_pipeline_for_dir",
                return_value=mock_pipeline,
            ) as mock_build,
            patch(
                "pdf_pipeline.cli.main._compute_mirror_output_dir",
                return_value=tmp_path / "out",
            ),
        ):
            mock_scanner_cls.return_value.compute_sha256.return_value = (
                "abc" * 21 + "ab"
            )

            _process_one_pdf(
                pdf,
                index=1,
                total=1,
                output_base=tmp_path / "out",
                config_path=tmp_path / "config.yaml",
                extract=False,
                input_dir=tmp_path,
            )

        _, kwargs = mock_build.call_args
        assert kwargs["provider_mode"] == "auto"


# ---------------------------------------------------------------------------
# batch コマンド — --provider オプション
# ---------------------------------------------------------------------------


class TestBatchCommandProviderOption:
    """Tests for --provider option parsing in the batch command."""

    def _make_runner(self) -> CliRunner:
        return CliRunner()

    def _invoke_batch_dryrun(self, runner: CliRunner, provider: str | None) -> Any:
        """Invoke batch --dry-run with optional --provider."""
        with runner.isolated_filesystem() as td:
            pdf = Path(td) / "test.pdf"
            pdf.write_bytes(b"%PDF-1.4")

            args = ["batch", "--dry-run"]
            if provider is not None:
                args += ["--provider", provider]
            args.append(td)

            with patch("pdf_pipeline.cli.main.get_path", return_value=Path(td)):
                result = runner.invoke(cli, args)

        return result

    def test_正常系_claudeオプションが受け付けられる(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, "claude")
        assert result.exit_code == 0, result.output

    def test_正常系_geminiオプションが受け付けられる(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, "gemini")
        assert result.exit_code == 0, result.output

    def test_正常系_autoオプションが受け付けられる(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, "auto")
        assert result.exit_code == 0, result.output

    def test_正常系_provider省略時はautoがデフォルト(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, None)
        assert result.exit_code == 0, result.output

    def test_異常系_無効なprovider値でエラー(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, "openai")
        assert result.exit_code != 0

    def test_正常系_claudeモード時にProviderメッセージが表示される(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, "claude")
        assert result.exit_code == 0, result.output
        assert "claude" in result.output.lower()

    def test_正常系_autoモード時にProviderメッセージは表示されない(self) -> None:
        runner = self._make_runner()
        result = self._invoke_batch_dryrun(runner, "auto")
        assert result.exit_code == 0, result.output
        # auto の場合は Provider: 行が表示されない
        assert "Provider:" not in result.output


# ---------------------------------------------------------------------------
# process コマンド — --provider オプション
# ---------------------------------------------------------------------------


class TestProcessCommandProviderOption:
    """Tests for --provider option parsing in the process command."""

    def _invoke_process(
        self, runner: CliRunner, pdf: Path, provider: str | None
    ) -> Any:
        args = ["process"]
        if provider is not None:
            args += ["--provider", provider]
        args.append(str(pdf))

        mock_result = {"status": "completed", "chunk_count": 1, "source_hash": "a" * 64}
        mock_pipeline = MagicMock()
        mock_pipeline.process_pdf.return_value = mock_result

        with (
            patch(
                "pdf_pipeline.cli.main._build_pipeline_for_dir",
                return_value=mock_pipeline,
            ),
            patch("pdf_pipeline.cli.main.PdfScanner") as mock_scanner_cls,
            patch(
                "pdf_pipeline.cli.main._compute_mirror_output_dir",
                return_value=pdf.parent,
            ),
        ):
            mock_scanner_cls.return_value.compute_sha256.return_value = "a" * 64
            result = runner.invoke(cli, args)

        return result

    def test_正常系_claudeオプションが受け付けられる(self, tmp_path: Path) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()
        result = self._invoke_process(runner, pdf, "claude")
        assert result.exit_code == 0, result.output

    def test_正常系_geminiオプションが受け付けられる(self, tmp_path: Path) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()
        result = self._invoke_process(runner, pdf, "gemini")
        assert result.exit_code == 0, result.output

    def test_正常系_autoオプションが受け付けられる(self, tmp_path: Path) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()
        result = self._invoke_process(runner, pdf, "auto")
        assert result.exit_code == 0, result.output

    def test_正常系_provider省略時はautoがデフォルト(self, tmp_path: Path) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()
        result = self._invoke_process(runner, pdf, None)
        assert result.exit_code == 0, result.output

    def test_異常系_無効なprovider値でエラー(self, tmp_path: Path) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()

        result = runner.invoke(cli, ["process", "--provider", "openai", str(pdf)])
        assert result.exit_code != 0

    def test_正常系_claudeモード時にprovider_modeが_build_pipeline_for_dirに渡される(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        runner = CliRunner()

        mock_result = {"status": "completed", "chunk_count": 1, "source_hash": "a" * 64}
        mock_pipeline = MagicMock()
        mock_pipeline.process_pdf.return_value = mock_result

        with (
            patch(
                "pdf_pipeline.cli.main._build_pipeline_for_dir",
                return_value=mock_pipeline,
            ) as mock_build,
            patch("pdf_pipeline.cli.main.PdfScanner") as mock_scanner_cls,
            patch(
                "pdf_pipeline.cli.main._compute_mirror_output_dir",
                return_value=pdf.parent,
            ),
        ):
            mock_scanner_cls.return_value.compute_sha256.return_value = "a" * 64
            runner.invoke(cli, ["process", "--provider", "claude", str(pdf)])

        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs["provider_mode"] == "claude"
