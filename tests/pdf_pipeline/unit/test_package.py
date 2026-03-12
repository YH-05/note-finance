"""Unit tests for pdf_pipeline package public API."""

from __future__ import annotations


class TestPackageImports:
    def test_正常系_パッケージから例外クラスをimportできる(self) -> None:
        from pdf_pipeline import (
            ConfigError,
            ConversionError,
            LLMProviderError,
            PdfPipelineError,
        )

        assert PdfPipelineError is not None
        assert LLMProviderError is not None
        assert ConversionError is not None
        assert ConfigError is not None

    def test_正常系_all_に全公開クラスが含まれている(self) -> None:
        import pdf_pipeline

        expected = {
            "PdfPipelineError",
            "LLMProviderError",
            "ConversionError",
            "ConfigError",
        }
        assert expected == set(pdf_pipeline.__all__)

    def test_正常系_サブパッケージをimportできる(self) -> None:
        import pdf_pipeline.config
        import pdf_pipeline.core
        import pdf_pipeline.services

        assert pdf_pipeline.core is not None
        assert pdf_pipeline.services is not None
        assert pdf_pipeline.config is not None

    def test_正常系_exceptionsモジュールからimportできる(self) -> None:
        from pdf_pipeline.exceptions import (
            ConversionError,
            LLMProviderError,
            PathTraversalError,
            PdfPipelineError,
            ScanError,
            StateError,
        )

        assert PdfPipelineError is not None
        assert LLMProviderError is not None
        assert ConversionError is not None
        assert ScanError is not None
        assert StateError is not None
        assert PathTraversalError is not None
