"""Unit tests for pdf_pipeline.types module.

Tests cover:
- Pydantic model validation (required fields, type constraints, defaults)
- Frozen dataclass immutability
- Type alias correctness
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_paths import get_path
from pdf_pipeline.types import (
    BatchManifest,
    LLMConfig,
    NoiseFilterConfig,
    PdfMetadata,
    PipelineConfig,
    ProcessingState,
)

# ---------------------------------------------------------------------------
# LLMConfig (Pydantic)
# ---------------------------------------------------------------------------


class TestLLMConfig:
    """Tests for LLMConfig Pydantic model."""

    def test_正常系_デフォルト値で生成できる(self) -> None:
        config = LLMConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-opus-4-5"
        assert config.max_tokens == 4096
        assert config.temperature == 0.0

    def test_正常系_カスタム値で生成できる(self) -> None:
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            max_tokens=2048,
            temperature=0.5,
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.max_tokens == 2048
        assert config.temperature == 0.5

    def test_異常系_max_tokensが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(max_tokens=0)

    def test_異常系_temperatureが負でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)

    def test_異常系_temperatureが2超でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(temperature=2.1)


# ---------------------------------------------------------------------------
# NoiseFilterConfig (Pydantic)
# ---------------------------------------------------------------------------


class TestNoiseFilterConfig:
    """Tests for NoiseFilterConfig Pydantic model."""

    def test_正常系_デフォルト値で生成できる(self) -> None:
        config = NoiseFilterConfig()
        assert config.min_chunk_chars > 0
        assert isinstance(config.skip_patterns, list)

    def test_正常系_カスタム値で生成できる(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=100,
            skip_patterns=["^\\s*$", "^page \\d+"],
        )
        assert config.min_chunk_chars == 100
        assert len(config.skip_patterns) == 2

    def test_異常系_min_chunk_charsが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            NoiseFilterConfig(min_chunk_chars=0)


# ---------------------------------------------------------------------------
# PipelineConfig (Pydantic)
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    """Tests for PipelineConfig Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        config = PipelineConfig(
            input_dirs=[Path("data/raw/pdfs")],
        )
        assert config.input_dirs == [Path("data/raw/pdfs")]
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.noise_filter, NoiseFilterConfig)

    def test_正常系_デフォルト値が設定される(self) -> None:
        config = PipelineConfig(input_dirs=[Path("data/raw")])
        assert config.output_dir == get_path("processed")
        assert config.batch_size > 0

    def test_正常系_全フィールドで生成できる(self) -> None:
        config = PipelineConfig(
            input_dirs=[Path("data/raw"), Path("data/extra")],
            output_dir=Path("data/out"),
            batch_size=5,
            llm=LLMConfig(provider="openai", model="gpt-4o"),
            noise_filter=NoiseFilterConfig(min_chunk_chars=200),
        )
        assert len(config.input_dirs) == 2
        assert config.output_dir == Path("data/out")
        assert config.batch_size == 5
        assert config.llm.provider == "openai"
        assert config.noise_filter.min_chunk_chars == 200

    def test_異常系_input_dirsが空リストでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            PipelineConfig(input_dirs=[])

    def test_正常系_page_chunk_sizeのデフォルト値が30(self) -> None:
        config = PipelineConfig(input_dirs=[Path("data/raw")])
        assert config.page_chunk_size == 30

    def test_正常系_page_chunk_sizeをカスタム値で設定できる(self) -> None:
        config = PipelineConfig(input_dirs=[Path("data/raw")], page_chunk_size=50)
        assert config.page_chunk_size == 50

    def test_正常系_page_chunk_sizeの最小値1を設定できる(self) -> None:
        config = PipelineConfig(input_dirs=[Path("data/raw")], page_chunk_size=1)
        assert config.page_chunk_size == 1

    def test_正常系_page_chunk_sizeの最大値200を設定できる(self) -> None:
        config = PipelineConfig(input_dirs=[Path("data/raw")], page_chunk_size=200)
        assert config.page_chunk_size == 200

    def test_異常系_page_chunk_sizeが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            PipelineConfig(input_dirs=[Path("data/raw")], page_chunk_size=0)

    def test_異常系_page_chunk_sizeが201以上でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            PipelineConfig(input_dirs=[Path("data/raw")], page_chunk_size=201)

    def test_異常系_batch_sizeが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            PipelineConfig(input_dirs=[Path("data/raw")], batch_size=0)


# ---------------------------------------------------------------------------
# ProcessingState (frozen dataclass)
# ---------------------------------------------------------------------------


class TestProcessingState:
    """Tests for ProcessingState frozen dataclass."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        state = ProcessingState(
            pdf_path=Path("data/raw/report.pdf"),
            status="pending",
        )
        assert state.pdf_path == Path("data/raw/report.pdf")
        assert state.status == "pending"

    def test_正常系_オプションフィールドのデフォルト値(self) -> None:
        state = ProcessingState(
            pdf_path=Path("data/raw/report.pdf"),
            status="pending",
        )
        assert state.error is None
        assert state.chunk_count == 0

    def test_正常系_全フィールドで生成できる(self) -> None:
        state = ProcessingState(
            pdf_path=Path("data/raw/report.pdf"),
            status="completed",
            error=None,
            chunk_count=42,
        )
        assert state.status == "completed"
        assert state.chunk_count == 42

    def test_正常系_エラー状態を表現できる(self) -> None:
        state = ProcessingState(
            pdf_path=Path("data/raw/report.pdf"),
            status="failed",
            error="Extraction timeout",
        )
        assert state.status == "failed"
        assert state.error == "Extraction timeout"

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        state = ProcessingState(
            pdf_path=Path("data/raw/report.pdf"),
            status="pending",
        )
        with pytest.raises(FrozenInstanceError):
            state.status = "completed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PdfMetadata (frozen dataclass)
# ---------------------------------------------------------------------------


class TestPdfMetadata:
    """Tests for PdfMetadata frozen dataclass."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        meta = PdfMetadata(
            pdf_path=Path("data/raw/report.pdf"),
            title="Q4 2025 Market Report",
            page_count=30,
        )
        assert meta.pdf_path == Path("data/raw/report.pdf")
        assert meta.title == "Q4 2025 Market Report"
        assert meta.page_count == 30

    def test_正常系_オプションフィールドのデフォルト値(self) -> None:
        meta = PdfMetadata(
            pdf_path=Path("data/raw/report.pdf"),
            title="Report",
            page_count=10,
        )
        assert meta.author is None
        assert meta.publisher is None
        assert meta.language == "en"

    def test_正常系_全フィールドで生成できる(self) -> None:
        meta = PdfMetadata(
            pdf_path=Path("data/raw/report.pdf"),
            title="Annual Report 2025",
            page_count=50,
            author="John Doe",
            publisher="Goldman Sachs",
            language="ja",
        )
        assert meta.author == "John Doe"
        assert meta.publisher == "Goldman Sachs"
        assert meta.language == "ja"

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        meta = PdfMetadata(
            pdf_path=Path("data/raw/report.pdf"),
            title="Report",
            page_count=10,
        )
        with pytest.raises(FrozenInstanceError):
            meta.title = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BatchManifest (frozen dataclass)
# ---------------------------------------------------------------------------


class TestBatchManifest:
    """Tests for BatchManifest frozen dataclass."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        manifest = BatchManifest(
            batch_id="batch-001",
            pdf_paths=(Path("data/raw/a.pdf"), Path("data/raw/b.pdf")),
        )
        assert manifest.batch_id == "batch-001"
        assert len(manifest.pdf_paths) == 2

    def test_正常系_オプションフィールドのデフォルト値(self) -> None:
        manifest = BatchManifest(
            batch_id="batch-001",
            pdf_paths=(Path("data/raw/a.pdf"),),
        )
        assert manifest.total_pages == 0
        assert manifest.output_dir is None

    def test_正常系_全フィールドで生成できる(self) -> None:
        manifest = BatchManifest(
            batch_id="batch-002",
            pdf_paths=(Path("data/raw/a.pdf"),),
            total_pages=120,
            output_dir=Path("data/processed/batch-002"),
        )
        assert manifest.total_pages == 120
        assert manifest.output_dir == Path("data/processed/batch-002")

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        manifest = BatchManifest(
            batch_id="batch-001",
            pdf_paths=(Path("data/raw/a.pdf"),),
        )
        with pytest.raises(FrozenInstanceError):
            manifest.batch_id = "changed"  # type: ignore[misc]
