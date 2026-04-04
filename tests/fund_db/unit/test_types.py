"""Unit tests for fund_db.types module.

Tests frozen dataclass immutability, field access, and generic type parameter.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fund_db.types import DownloadResult, ParseResult


class TestDownloadResult:
    """Tests for the DownloadResult frozen dataclass."""

    def test_正常系_フィールドにアクセスできる(self) -> None:
        dt = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = DownloadResult(
            path=Path("data/fund_db/nisa/file.xlsx"),
            url="https://example.com/file.xlsx",
            size_bytes=2048,
            downloaded_at=dt,
        )
        assert result.path == Path("data/fund_db/nisa/file.xlsx")
        assert result.url == "https://example.com/file.xlsx"
        assert result.size_bytes == 2048
        assert result.downloaded_at == dt

    def test_異常系_frozenのためフィールドを変更できない(self) -> None:
        result = DownloadResult(
            path=Path("data/file.xlsx"),
            url="https://example.com/file.xlsx",
            size_bytes=1024,
            downloaded_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(FrozenInstanceError):
            result.size_bytes = 9999  # type: ignore[misc]

    def test_正常系_同一フィールド値で等価判定できる(self) -> None:
        dt = datetime(2026, 4, 1, tzinfo=timezone.utc)
        a = DownloadResult(
            path=Path("f.xlsx"),
            url="https://x.com",
            size_bytes=100,
            downloaded_at=dt,
        )
        b = DownloadResult(
            path=Path("f.xlsx"),
            url="https://x.com",
            size_bytes=100,
            downloaded_at=dt,
        )
        assert a == b


class TestParseResult:
    """Tests for the ParseResult frozen dataclass."""

    def test_正常系_文字列レコードで使用できる(self) -> None:
        dt = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = ParseResult[str](
            records=["record_a", "record_b"],
            source_path=Path("data/file.xlsx"),
            record_count=2,
            parsed_at=dt,
        )
        assert result.records == ["record_a", "record_b"]
        assert result.source_path == Path("data/file.xlsx")
        assert result.record_count == 2
        assert result.parsed_at == dt

    def test_正常系_辞書レコードで使用できる(self) -> None:
        dt = datetime(2026, 4, 1, tzinfo=timezone.utc)
        records: list[dict[str, str]] = [
            {"fund_name": "Fund A"},
            {"fund_name": "Fund B"},
        ]
        result = ParseResult[dict[str, str]](
            records=records,
            source_path=Path("data/raw.xlsx"),
            record_count=2,
            parsed_at=dt,
        )
        assert len(result.records) == 2
        assert result.records[0]["fund_name"] == "Fund A"

    def test_異常系_frozenのためフィールドを変更できない(self) -> None:
        result = ParseResult[str](
            records=["a"],
            source_path=Path("data/file.xlsx"),
            record_count=1,
            parsed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(FrozenInstanceError):
            result.record_count = 999  # type: ignore[misc]

    def test_エッジケース_空リストで使用できる(self) -> None:
        result = ParseResult[str](
            records=[],
            source_path=Path("data/empty.xlsx"),
            record_count=0,
            parsed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        assert result.records == []
        assert result.record_count == 0
