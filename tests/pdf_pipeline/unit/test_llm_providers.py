"""Unit tests for LLMProvider Protocol, GeminiCLIProvider, ClaudeCodeProvider, and ProviderChain.

Tests cover:
- LLMProvider Protocol structural checks
- GeminiCLIProvider availability check, CLI invocation, output sanitization, and validation
- ClaudeCodeProvider lazy import pattern
- ProviderChain ordered fallback and error handling
- LLMProviderError raised when all providers fail
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from pdf_pipeline.exceptions import LLMProviderError
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
from pdf_pipeline.services.gemini_provider import (
    GeminiCLIProvider,
    _sanitize_output,
)
from pdf_pipeline.services.llm_provider import LLMProvider
from pdf_pipeline.services.provider_chain import ProviderChain

# ---------------------------------------------------------------------------
# LLMProvider Protocol
# ---------------------------------------------------------------------------


class TestLLMProviderProtocol:
    """Tests for LLMProvider Protocol definition."""

    def test_正常系_Protocolが定義されている(self) -> None:
        from typing import runtime_checkable

        assert isinstance(LLMProvider, type)

    def test_正常系_runtime_checkable_Protocolである(self) -> None:
        # runtime_checkable Protocolはisinstance()チェックが可能
        class MockProvider:
            def convert_pdf_to_markdown(self, pdf_path: str) -> str:
                return ""

            def extract_table_json(self, text: str) -> str:
                return "{}"

            def extract_knowledge(self, text: str) -> str:
                return "{}"

            def is_available(self) -> bool:
                return True

        provider = MockProvider()
        assert isinstance(provider, LLMProvider)

    def test_異常系_is_available未実装はProtocol違反(self) -> None:
        class IncompleteProvider:
            def convert_pdf_to_markdown(self, pdf_path: str) -> str:
                return ""

            def extract_table_json(self, text: str) -> str:
                return "{}"

            def extract_knowledge(self, text: str) -> str:
                return "{}"

            # is_available() が未実装

        provider = IncompleteProvider()
        assert not isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# GeminiCLIProvider
# ---------------------------------------------------------------------------


class TestGeminiCLIProviderIsAvailable:
    """Tests for GeminiCLIProvider.is_available()."""

    def test_正常系_geminiコマンドが存在する場合True(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/gemini"):
            provider = GeminiCLIProvider()
            assert provider.is_available() is True

    def test_正常系_geminiコマンドが存在しない場合False(self) -> None:
        with patch("shutil.which", return_value=None):
            provider = GeminiCLIProvider()
            assert provider.is_available() is False


class TestGeminiCLIProviderConvertPdfToMarkdown:
    """Tests for GeminiCLIProvider.convert_pdf_to_markdown()."""

    def test_正常系_PDF変換成功(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "# Converted Markdown Content\n\n## Section 1\n\nText."

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider = GeminiCLIProvider()
            result = provider.convert_pdf_to_markdown("/path/to/report.pdf")

        assert "# Converted Markdown Content" in result
        # Verify -p flag and -y (auto-approve) are used
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-p" in cmd
        assert "-y" in cmd

    def test_正常系_ノイズが除去される(self) -> None:
        noisy_output = (
            "MCP issues detected. Run /mcp list for status.\n"
            "I will read the PDF file to extract its content.\n"
            "# Report Title\n\n## Section 1\n\nActual content."
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = noisy_output

        with patch("subprocess.run", return_value=mock_result):
            provider = GeminiCLIProvider()
            result = provider.convert_pdf_to_markdown("/path/to/report.pdf")

        assert "MCP issues detected" not in result
        assert "I will read the PDF" not in result
        assert "# Report Title" in result
        assert "Actual content" in result

    def test_異常系_見出しなしの出力でLLMProviderError(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "This output has no markdown headings at all."

        with patch("subprocess.run", return_value=mock_result):
            provider = GeminiCLIProvider()
            with pytest.raises(LLMProviderError, match="no Markdown headings"):
                provider.convert_pdf_to_markdown("/path/to/report.pdf")

    def test_異常系_geminiコマンド失敗でLLMProviderError(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "gemini: command failed"

        with patch("subprocess.run", return_value=mock_result):
            provider = GeminiCLIProvider()
            with pytest.raises(LLMProviderError, match="GeminiCLIProvider"):
                provider.convert_pdf_to_markdown("/path/to/report.pdf")

    def test_異常系_subprocess例外でLLMProviderError(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("gemini not found"),
        ):
            provider = GeminiCLIProvider()
            with pytest.raises(LLMProviderError, match="GeminiCLIProvider"):
                provider.convert_pdf_to_markdown("/path/to/report.pdf")

    def test_異常系_pdf拡張子なしでLLMProviderError(self) -> None:
        provider = GeminiCLIProvider()
        with pytest.raises(LLMProviderError, match="pdf extension"):
            provider.convert_pdf_to_markdown("/path/to/report.txt")


class TestGeminiCLIProviderExtractTableJson:
    """Tests for GeminiCLIProvider.extract_table_json()."""

    def test_正常系_テーブル抽出成功(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"tables": []}'

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider = GeminiCLIProvider()
            result = provider.extract_table_json("table text content")

        assert result == '{"tables": []}'
        # Verify -p flag is used
        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd

    def test_異常系_コマンド失敗でLLMProviderError(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            provider = GeminiCLIProvider()
            with pytest.raises(LLMProviderError):
                provider.extract_table_json("text")


class TestGeminiCLIProviderExtractKnowledge:
    """Tests for GeminiCLIProvider.extract_knowledge()."""

    def test_正常系_ナレッジ抽出成功(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"entities": [], "relations": []}'

        with patch("subprocess.run", return_value=mock_result):
            provider = GeminiCLIProvider()
            result = provider.extract_knowledge("knowledge text")

        assert result == '{"entities": [], "relations": []}'


# ---------------------------------------------------------------------------
# Output sanitization
# ---------------------------------------------------------------------------


class TestSanitizeOutput:
    """Tests for _sanitize_output helper."""

    def test_正常系_MCPノイズが除去される(self) -> None:
        raw = "MCP issues detected. Run /mcp list for status.\n# Title\n\nContent."
        result = _sanitize_output(raw)
        assert "MCP issues" not in result
        assert "# Title" in result

    def test_正常系_思考ログが除去される(self) -> None:
        raw = (
            "I will read the PDF file.\n"
            "I'll extract the tables.\n"
            "Let me process this.\n"
            "First, I will scan the document.\n"
            "# Actual Content\n\nReal text."
        )
        result = _sanitize_output(raw)
        assert "I will" not in result
        assert "I'll" not in result
        assert "Let me" not in result
        assert "# Actual Content" in result

    def test_正常系_コードフェンスが除去される(self) -> None:
        raw = "```markdown\n# Title\n\nContent.\n```"
        result = _sanitize_output(raw)
        assert "```" not in result
        assert "# Title" in result

    def test_正常系_連続空行が圧縮される(self) -> None:
        raw = "# Title\n\n\n\n\n\nContent."
        result = _sanitize_output(raw)
        assert "\n\n\n" not in result
        assert "# Title" in result
        assert "Content." in result

    def test_正常系_クリーンな出力はそのまま(self) -> None:
        raw = "# Title\n\n## Section\n\nClean content."
        result = _sanitize_output(raw)
        assert result == raw

    def test_正常系_Hereisプリアンブルが除去される(self) -> None:
        raw = "Here is the converted markdown:\n# Title\n\nContent."
        result = _sanitize_output(raw)
        assert "Here is" not in result
        assert "# Title" in result


# ---------------------------------------------------------------------------
# ClaudeCodeProvider
# ---------------------------------------------------------------------------


class TestClaudeCodeProviderIsAvailable:
    """Tests for ClaudeCodeProvider.is_available()."""

    def test_正常系_claude_agent_sdkが利用可能な場合True(self) -> None:
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"claude_agent_sdk": mock_module}):
            provider = ClaudeCodeProvider()
            assert provider.is_available() is True

    def test_正常系_claude_agent_sdkが利用不可の場合False(self) -> None:
        # importlib.import_module をパッチして ImportError を発生させる
        with patch(
            "importlib.import_module",
            side_effect=ImportError("No module named 'claude_agent_sdk'"),
        ):
            provider = ClaudeCodeProvider()
            result = provider.is_available()
        assert result is False


class TestClaudeCodeProviderLazyImport:
    """Tests for ClaudeCodeProvider lazy import pattern."""

    def test_正常系_インスタンス化時にimportしない(self) -> None:
        # ClaudeCodeProvider() のインスタンス化自体は ImportError を起こさない
        # lazy import のためインスタンス化はSDKなしでも成功する
        provider = ClaudeCodeProvider()
        # インスタンス化は成功する（lazy import のため）
        assert provider is not None

    def test_正常系_convert_pdf_to_markdownがProtocol準拠(self) -> None:
        provider = ClaudeCodeProvider()
        assert hasattr(provider, "convert_pdf_to_markdown")
        assert hasattr(provider, "extract_table_json")
        assert hasattr(provider, "extract_knowledge")
        assert hasattr(provider, "is_available")


class TestClaudeCodeProviderConvertPdfToMarkdown:
    """Tests for ClaudeCodeProvider.convert_pdf_to_markdown()."""

    def test_正常系_SDK利用可能時にPDF変換成功(self) -> None:
        mock_sdk = MagicMock()
        mock_sdk.convert_pdf_to_markdown.return_value = "# Claude Converted"

        with patch.dict("sys.modules", {"claude_agent_sdk": mock_sdk}):
            provider = ClaudeCodeProvider()
            result = provider.convert_pdf_to_markdown("/path/to/report.pdf")

        assert result == "# Claude Converted"

    def test_異常系_SDK利用不可でLLMProviderError(self) -> None:
        provider = ClaudeCodeProvider()
        provider._sdk_available = False  # force unavailable
        with pytest.raises(LLMProviderError, match="ClaudeCodeProvider"):
            provider.convert_pdf_to_markdown("/path/to/report.pdf")

    def test_異常系_SDK呼び出し失敗でLLMProviderError(self) -> None:
        mock_sdk = MagicMock()
        mock_sdk.convert_pdf_to_markdown.side_effect = RuntimeError("SDK error")

        with patch.dict("sys.modules", {"claude_agent_sdk": mock_sdk}):
            provider = ClaudeCodeProvider()
            with pytest.raises(LLMProviderError, match="ClaudeCodeProvider"):
                provider.convert_pdf_to_markdown("/path/to/report.pdf")


# ---------------------------------------------------------------------------
# ProviderChain
# ---------------------------------------------------------------------------


class TestProviderChainInit:
    """Tests for ProviderChain initialization."""

    def test_正常系_プロバイダーリストで初期化できる(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p2 = MagicMock(spec=LLMProvider)
        chain = ProviderChain([p1, p2])
        assert len(chain.providers) == 2

    def test_異常系_空のプロバイダーリストでValueError(self) -> None:
        with pytest.raises(ValueError, match="providers"):
            ProviderChain([])


class TestProviderChainConvertPdfToMarkdown:
    """Tests for ProviderChain.convert_pdf_to_markdown()."""

    def test_正常系_最初の利用可能なプロバイダーを使用(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.convert_pdf_to_markdown.return_value = "# P1 Result"

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True
        p2.convert_pdf_to_markdown.return_value = "# P2 Result"

        chain = ProviderChain([p1, p2])
        result = chain.convert_pdf_to_markdown("/path/to/report.pdf")

        assert result == "# P1 Result"
        p2.convert_pdf_to_markdown.assert_not_called()

    def test_正常系_最初のプロバイダー失敗時にフォールバック(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.convert_pdf_to_markdown.side_effect = LLMProviderError("p1 failed")

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True
        p2.convert_pdf_to_markdown.return_value = "# P2 Fallback"

        chain = ProviderChain([p1, p2])
        result = chain.convert_pdf_to_markdown("/path/to/report.pdf")

        assert result == "# P2 Fallback"

    def test_正常系_利用不可のプロバイダーをスキップ(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = False

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True
        p2.convert_pdf_to_markdown.return_value = "# P2 Result"

        chain = ProviderChain([p1, p2])
        result = chain.convert_pdf_to_markdown("/path/to/report.pdf")

        assert result == "# P2 Result"
        p1.convert_pdf_to_markdown.assert_not_called()

    def test_異常系_全プロバイダー失敗時にLLMProviderError(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.convert_pdf_to_markdown.side_effect = LLMProviderError("p1 failed")

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True
        p2.convert_pdf_to_markdown.side_effect = LLMProviderError("p2 failed")

        chain = ProviderChain([p1, p2])
        with pytest.raises(LLMProviderError, match="All providers failed"):
            chain.convert_pdf_to_markdown("/path/to/report.pdf")

    def test_異常系_全プロバイダー利用不可でLLMProviderError(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = False

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = False

        chain = ProviderChain([p1, p2])
        with pytest.raises(LLMProviderError, match="All providers failed"):
            chain.convert_pdf_to_markdown("/path/to/report.pdf")


class TestProviderChainExtractTableJson:
    """Tests for ProviderChain.extract_table_json()."""

    def test_正常系_フォールバック動作(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.extract_table_json.side_effect = LLMProviderError("failed")

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True
        p2.extract_table_json.return_value = '{"tables": [{"cols": 3}]}'

        chain = ProviderChain([p1, p2])
        result = chain.extract_table_json("table text")

        assert result == '{"tables": [{"cols": 3}]}'

    def test_異常系_全プロバイダー失敗でLLMProviderError(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.extract_table_json.side_effect = LLMProviderError("failed")

        chain = ProviderChain([p1])
        with pytest.raises(LLMProviderError):
            chain.extract_table_json("text")


class TestProviderChainExtractKnowledge:
    """Tests for ProviderChain.extract_knowledge()."""

    def test_正常系_フォールバック動作(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.extract_knowledge.side_effect = LLMProviderError("failed")

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True
        p2.extract_knowledge.return_value = '{"entities": []}'

        chain = ProviderChain([p1, p2])
        result = chain.extract_knowledge("knowledge text")

        assert result == '{"entities": []}'

    def test_異常系_全プロバイダー失敗でLLMProviderError(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = True
        p1.extract_knowledge.side_effect = LLMProviderError("failed")

        chain = ProviderChain([p1])
        with pytest.raises(LLMProviderError):
            chain.extract_knowledge("text")


class TestProviderChainIsAvailable:
    """Tests for ProviderChain.is_available()."""

    def test_正常系_少なくとも1つ利用可能ならTrue(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = False

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = True

        chain = ProviderChain([p1, p2])
        assert chain.is_available() is True

    def test_正常系_全プロバイダー利用不可ならFalse(self) -> None:
        p1 = MagicMock(spec=LLMProvider)
        p1.is_available.return_value = False

        p2 = MagicMock(spec=LLMProvider)
        p2.is_available.return_value = False

        chain = ProviderChain([p1, p2])
        assert chain.is_available() is False


# ---------------------------------------------------------------------------
# LLMProviderError
# ---------------------------------------------------------------------------


class TestLLMProviderError:
    """Tests for LLMProviderError exception."""

    def test_正常系_例外が発生できる(self) -> None:
        with pytest.raises(LLMProviderError, match="test error"):
            raise LLMProviderError("test error")

    def test_正常系_PdfPipelineErrorを継承する(self) -> None:
        from pdf_pipeline.exceptions import PdfPipelineError

        error = LLMProviderError("test")
        assert isinstance(error, PdfPipelineError)

    def test_正常系_providerフィールドが設定できる(self) -> None:
        error = LLMProviderError("test error", provider="GeminiCLIProvider")
        assert error.provider == "GeminiCLIProvider"

    def test_正常系_providerフィールドなしでも動作する(self) -> None:
        error = LLMProviderError("test error")
        assert error.provider is None
