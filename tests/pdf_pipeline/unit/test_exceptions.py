"""Unit tests for pdf_pipeline.exceptions module."""

from __future__ import annotations

import pytest

from pdf_pipeline.exceptions import (
    ConfigError,
    ConversionError,
    LLMProviderError,
    PathTraversalError,
    PdfPipelineError,
    ScanError,
    StateError,
)


class TestPdfPipelineError:
    def test_正常系_基底例外をraiseできる(self) -> None:
        with pytest.raises(PdfPipelineError, match="base error"):
            raise PdfPipelineError("base error")

    def test_正常系_全サブクラスがPdfPipelineErrorを継承している(self) -> None:
        assert issubclass(LLMProviderError, PdfPipelineError)
        assert issubclass(ConversionError, PdfPipelineError)
        assert issubclass(ConfigError, PdfPipelineError)
        assert issubclass(ScanError, PdfPipelineError)
        assert issubclass(StateError, PdfPipelineError)
        assert issubclass(PathTraversalError, PdfPipelineError)


class TestConfigError:
    def test_正常系_メッセージのみで作成できる(self) -> None:
        err = ConfigError("invalid config")
        assert str(err) == "invalid config"
        assert err.field is None

    def test_正常系_フィールド名を設定できる(self) -> None:
        err = ConfigError("missing field", field="api_key")
        assert err.field == "api_key"

    def test_正常系_PdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise ConfigError("error")

    def test_正常系_フィールド付きPdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise ConfigError("error", field="path")


class TestConversionError:
    def test_正常系_パスとメッセージが設定される(self) -> None:
        err = ConversionError("conversion failed", path="/tmp/file.pdf")
        assert str(err) == "conversion failed"
        assert err.path == "/tmp/file.pdf"
        assert err.step is None

    def test_正常系_ステップ情報を設定できる(self) -> None:
        err = ConversionError("failed", path="/tmp/file.pdf", step="text_extraction")
        assert err.step == "text_extraction"

    def test_正常系_PdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise ConversionError("error", path="/tmp/file.pdf")


class TestScanError:
    def test_正常系_パスとメッセージが設定される(self) -> None:
        err = ScanError("Directory not found", path="/data/pdfs")
        assert str(err) == "Directory not found"
        assert err.path == "/data/pdfs"

    def test_正常系_PdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise ScanError("scan failed", path="/data")


class TestStateError:
    def test_正常系_ステートファイルとメッセージが設定される(self) -> None:
        err = StateError("Cannot write state", state_file=".tmp/state.json")
        assert str(err) == "Cannot write state"
        assert err.state_file == ".tmp/state.json"

    def test_正常系_PdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise StateError("state error", state_file=".tmp/state.json")


class TestLLMProviderError:
    def test_正常系_メッセージのみで作成できる(self) -> None:
        err = LLMProviderError("LLM failed")
        assert str(err) == "LLM failed"
        assert err.provider is None

    def test_正常系_プロバイダ名を設定できる(self) -> None:
        err = LLMProviderError("API quota exceeded", provider="GeminiCLIProvider")
        assert err.provider == "GeminiCLIProvider"

    def test_正常系_PdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise LLMProviderError("error", provider="openai")


class TestPathTraversalError:
    def test_正常系_パスとベースディレクトリが設定される(self) -> None:
        err = PathTraversalError(
            "Path traversal detected",
            path="../../../etc/passwd",
            base_dir="/data/pdfs",
        )
        assert str(err) == "Path traversal detected"
        assert err.path == "../../../etc/passwd"
        assert err.base_dir == "/data/pdfs"

    def test_正常系_PdfPipelineErrorとしてcatchできる(self) -> None:
        with pytest.raises(PdfPipelineError):
            raise PathTraversalError(
                "traversal detected",
                path="../secret",
                base_dir="/data",
            )
