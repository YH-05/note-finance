"""Unit tests for fund_db.exceptions module.

Tests exception instantiation, attribute access, and inheritance hierarchy.
"""

from __future__ import annotations

import pytest

from fund_db.exceptions import (
    ConfigError,
    DownloadError,
    FundDbError,
    ParseError,
    StorageError,
)


class TestFundDbError:
    """Tests for the base FundDbError exception."""

    def test_正常系_メッセージを保持する(self) -> None:
        err = FundDbError("something went wrong")
        assert str(err) == "something went wrong"

    def test_正常系_Exceptionを継承する(self) -> None:
        assert issubclass(FundDbError, Exception)

    def test_正常系_catchできる(self) -> None:
        with pytest.raises(FundDbError):
            raise FundDbError("test error")


class TestDownloadError:
    """Tests for DownloadError exception."""

    def test_正常系_url属性を保持する(self) -> None:
        err = DownloadError(
            "Download failed",
            url="https://example.com/file.xlsx",
        )
        assert err.url == "https://example.com/file.xlsx"
        assert err.status_code is None
        assert str(err) == "Download failed"

    def test_正常系_status_codeを保持する(self) -> None:
        err = DownloadError(
            "Not found",
            url="https://example.com/missing.xlsx",
            status_code=404,
        )
        assert err.status_code == 404
        assert err.url == "https://example.com/missing.xlsx"

    def test_正常系_FundDbErrorを継承する(self) -> None:
        assert issubclass(DownloadError, FundDbError)

    def test_正常系_FundDbErrorとしてcatchできる(self) -> None:
        with pytest.raises(FundDbError):
            raise DownloadError("fail", url="https://example.com")


class TestParseError:
    """Tests for ParseError exception."""

    def test_正常系_source属性を保持する(self) -> None:
        err = ParseError(
            "Invalid format",
            source="file.xlsx",
        )
        assert err.source == "file.xlsx"
        assert err.reason is None
        assert str(err) == "Invalid format"

    def test_正常系_reason属性を保持する(self) -> None:
        err = ParseError(
            "Parse failed",
            source="file.xlsx",
            reason="Missing header row",
        )
        assert err.reason == "Missing header row"

    def test_正常系_FundDbErrorを継承する(self) -> None:
        assert issubclass(ParseError, FundDbError)


class TestStorageError:
    """Tests for StorageError exception."""

    def test_正常系_path属性がNoneのデフォルト(self) -> None:
        err = StorageError("Write failed")
        assert err.path is None
        assert str(err) == "Write failed"

    def test_正常系_path属性を保持する(self) -> None:
        err = StorageError(
            "Permission denied",
            path="/data/fund_db/records.json",
        )
        assert err.path == "/data/fund_db/records.json"

    def test_正常系_FundDbErrorを継承する(self) -> None:
        assert issubclass(StorageError, FundDbError)


class TestConfigError:
    """Tests for ConfigError exception."""

    def test_正常系_field属性がNoneのデフォルト(self) -> None:
        err = ConfigError("Invalid config")
        assert err.field is None
        assert str(err) == "Invalid config"

    def test_正常系_field属性を保持する(self) -> None:
        err = ConfigError(
            "Missing required field",
            field="data_dir",
        )
        assert err.field == "data_dir"

    def test_正常系_FundDbErrorを継承する(self) -> None:
        assert issubclass(ConfigError, FundDbError)


class TestExceptionHierarchy:
    """Tests for the exception inheritance hierarchy."""

    def test_正常系_全例外がFundDbErrorの子クラスである(self) -> None:
        assert issubclass(DownloadError, FundDbError)
        assert issubclass(ParseError, FundDbError)
        assert issubclass(StorageError, FundDbError)
        assert issubclass(ConfigError, FundDbError)

    def test_正常系_全例外がExceptionの子クラスである(self) -> None:
        assert issubclass(DownloadError, Exception)
        assert issubclass(ParseError, Exception)
        assert issubclass(StorageError, Exception)
        assert issubclass(ConfigError, Exception)

    def test_正常系_各例外は互いに独立している(self) -> None:
        """Each exception class should not be a subclass of another sibling."""
        assert not issubclass(DownloadError, ParseError)
        assert not issubclass(ParseError, StorageError)
        assert not issubclass(StorageError, ConfigError)
        assert not issubclass(ConfigError, DownloadError)
