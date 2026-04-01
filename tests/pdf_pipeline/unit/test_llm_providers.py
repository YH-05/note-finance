"""Unit tests for LLMProvider Protocol, ClaudeCodeProvider, and ProviderChain.

Tests cover:
- LLMProvider Protocol structural checks
- ClaudeCodeProvider lazy import pattern and SDK query
- ProviderChain ordered fallback and error handling
- LLMProviderError raised when all providers fail
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pdf_pipeline.exceptions import LLMProviderError
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider, _strip_code_fences
from pdf_pipeline.services.llm_provider import LLMProvider
from pdf_pipeline.services.provider_chain import ProviderChain

# ---------------------------------------------------------------------------
# LLMProvider Protocol
# ---------------------------------------------------------------------------


class TestLLMProviderProtocol:
    """Tests for LLMProvider Protocol definition."""

    def test_正常系_Protocolが定義されている(self) -> None:
        assert isinstance(LLMProvider, type)

    def test_正常系_runtime_checkable_Protocolである(self) -> None:
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

        provider = IncompleteProvider()
        assert not isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# _strip_code_fences helper
# ---------------------------------------------------------------------------


class TestStripCodeFences:
    """Tests for _strip_code_fences helper."""

    def test_正常系_JSONコードフェンスが除去される(self) -> None:
        raw = '```json\n{"entities": []}\n```'
        result = _strip_code_fences(raw)
        assert result == '{"entities": []}'

    def test_正常系_言語指定なしのコードフェンスが除去される(self) -> None:
        raw = '```\n{"data": true}\n```'
        result = _strip_code_fences(raw)
        assert result == '{"data": true}'

    def test_正常系_コードフェンスなしはそのまま(self) -> None:
        raw = '{"entities": []}'
        result = _strip_code_fences(raw)
        assert result == '{"entities": []}'

    def test_正常系_前後の空白が除去される(self) -> None:
        raw = '  \n{"data": true}\n  '
        result = _strip_code_fences(raw)
        assert result == '{"data": true}'


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
        provider = ClaudeCodeProvider()
        assert provider is not None

    def test_正常系_Protocolに準拠している(self) -> None:
        provider = ClaudeCodeProvider()
        assert hasattr(provider, "convert_pdf_to_markdown")
        assert hasattr(provider, "extract_table_json")
        assert hasattr(provider, "extract_knowledge")
        assert hasattr(provider, "is_available")


class TestClaudeCodeProviderExtractKnowledge:
    """Tests for ClaudeCodeProvider.extract_knowledge()."""

    def test_異常系_SDK利用不可でLLMProviderError(self) -> None:
        provider = ClaudeCodeProvider()
        provider._sdk_available = False
        with pytest.raises(LLMProviderError, match="ClaudeCodeProvider"):
            provider.extract_knowledge("test text")

    def test_正常系_コードフェンスが除去される(self) -> None:
        provider = ClaudeCodeProvider()
        provider._sdk_available = True
        provider._sdk = MagicMock()

        with patch.object(
            ClaudeCodeProvider,
            "_query_sdk",
            return_value='{"entities": []}',
        ):
            result = provider.extract_knowledge("test text")
        assert result == '{"entities": []}'


class TestClaudeCodeProviderConvertPdfToMarkdown:
    """Tests for ClaudeCodeProvider.convert_pdf_to_markdown()."""

    def test_異常系_SDK利用不可でLLMProviderError(self) -> None:
        provider = ClaudeCodeProvider()
        provider._sdk_available = False
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
        error = LLMProviderError("test error", provider="ClaudeCodeProvider")
        assert error.provider == "ClaudeCodeProvider"

    def test_正常系_providerフィールドなしでも動作する(self) -> None:
        error = LLMProviderError("test error")
        assert error.provider is None
