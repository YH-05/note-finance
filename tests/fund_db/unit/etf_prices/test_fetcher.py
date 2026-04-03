"""Unit tests for fund_db.etf_prices.fetcher module.

Uses unittest.mock to mock yfinance.download(), ensuring tests
run without network access. Verifies NaN → None conversion,
ticker suffix normalization, and performance calculations.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from fund_db.etf_prices.fetcher import (
    EtfPriceFetcher,
    _ensure_t_suffix,
    _wrap_value,
    _wrap_volume,
)
from fund_db.etf_prices.models import EtfPriceRecord


class TestEnsureTSuffix:
    """Tests for _ensure_t_suffix helper."""

    def test_正常系_サフィックスなしで追加される(self) -> None:
        assert _ensure_t_suffix("1306") == "1306.T"

    def test_正常系_サフィックスありでそのまま(self) -> None:
        assert _ensure_t_suffix("1306.T") == "1306.T"

    def test_正常系_数字以外のティッカーにも対応(self) -> None:
        assert _ensure_t_suffix("MAXIS") == "MAXIS.T"


class TestWrapValue:
    """Tests for _wrap_value NaN conversion helper."""

    def test_正常系_通常の数値をfloatで返す(self) -> None:
        assert _wrap_value(100.5) == 100.5

    def test_正常系_整数をfloatに変換(self) -> None:
        assert _wrap_value(100) == 100.0
        assert isinstance(_wrap_value(100), float)

    def test_正常系_NoneはNoneを返す(self) -> None:
        assert _wrap_value(None) is None

    def test_正常系_NaNはNoneを返す(self) -> None:
        assert _wrap_value(float("nan")) is None

    def test_正常系_numpy_nanはNoneを返す(self) -> None:
        assert _wrap_value(np.nan) is None

    def test_正常系_ゼロはfloatで返す(self) -> None:
        assert _wrap_value(0.0) == 0.0

    def test_正常系_負の値をfloatで返す(self) -> None:
        assert _wrap_value(-5.5) == -5.5


class TestWrapVolume:
    """Tests for _wrap_volume conversion helper."""

    def test_正常系_floatをintに変換(self) -> None:
        assert _wrap_volume(1000000.0) == 1000000
        assert isinstance(_wrap_volume(1000000.0), int)

    def test_正常系_NaNはNoneを返す(self) -> None:
        assert _wrap_volume(float("nan")) is None

    def test_正常系_NoneはNoneを返す(self) -> None:
        assert _wrap_volume(None) is None

    def test_正常系_ゼロはintで返す(self) -> None:
        assert _wrap_volume(0) == 0


def _make_single_ticker_df() -> pd.DataFrame:
    """Create a sample single-ticker DataFrame mimicking yf.download output."""
    dates = pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"])
    return pd.DataFrame(
        {
            "Open": [2490.0, 2500.0, 2510.0],
            "High": [2510.0, 2520.0, 2530.0],
            "Low": [2485.0, 2495.0, 2505.0],
            "Close": [2500.0, 2515.0, 2525.0],
            "Volume": [1000000.0, 1200000.0, 900000.0],
        },
        index=dates,
    )


def _make_single_ticker_df_with_nan() -> pd.DataFrame:
    """Create a DataFrame with NaN values in volume and open."""
    dates = pd.to_datetime(["2026-04-01", "2026-04-02"])
    return pd.DataFrame(
        {
            "Open": [2490.0, float("nan")],
            "High": [2510.0, 2520.0],
            "Low": [2485.0, 2495.0],
            "Close": [2500.0, 2515.0],
            "Volume": [float("nan"), 1200000.0],
        },
        index=dates,
    )


def _make_single_ticker_df_with_nan_close() -> pd.DataFrame:
    """Create a DataFrame with NaN in Close column."""
    dates = pd.to_datetime(["2026-04-01", "2026-04-02"])
    return pd.DataFrame(
        {
            "Open": [2490.0, 2500.0],
            "High": [2510.0, 2520.0],
            "Low": [2485.0, 2495.0],
            "Close": [float("nan"), 2515.0],
            "Volume": [1000000.0, 1200000.0],
        },
        index=dates,
    )


def _make_empty_df() -> pd.DataFrame:
    """Create an empty DataFrame."""
    return pd.DataFrame()


class TestEtfPriceFetcherFetch:
    """Tests for EtfPriceFetcher.fetch method with mocked yfinance."""

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_単一ティッカーで価格を取得できる(
        self, mock_download: object
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01", end="2026-04-04")

        assert len(records) == 3
        assert all(isinstance(r, EtfPriceRecord) for r in records)
        assert records[0].ticker == "1306.T"
        assert records[0].date == date(2026, 4, 1)
        assert records[0].close == 2500.0
        assert records[0].volume == 1000000

        # Verify yf.download was called with correct args
        mock_download.assert_called_once_with(  # type: ignore[union-attr]
            ["1306.T"],
            start="2026-04-01",
            end="2026-04-04",
            auto_adjust=True,
        )

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_サフィックスなしティッカーにTが付与される(
        self, mock_download: object
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        fetcher.fetch(["1306"], start="2026-04-01")

        call_args = mock_download.call_args  # type: ignore[union-attr]
        assert call_args[0][0] == ["1306.T"]

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_既にサフィックスがあるティッカーはそのまま(
        self, mock_download: object
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        fetcher.fetch(["1306.T"], start="2026-04-01")

        call_args = mock_download.call_args  # type: ignore[union-attr]
        assert call_args[0][0] == ["1306.T"]

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_NaN値がNoneに変換される(self, mock_download: object) -> None:
        mock_download.return_value = _make_single_ticker_df_with_nan()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01")

        # First record: Open=2490.0, Volume=NaN→None
        assert records[0].open == 2490.0
        assert records[0].volume is None

        # Second record: Open=NaN→None, Volume=1200000
        assert records[1].open is None
        assert records[1].volume == 1200000

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_NaN_closeの行はスキップされる(self, mock_download: object) -> None:
        mock_download.return_value = _make_single_ticker_df_with_nan_close()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01")

        # Only the second row (with valid close) should be returned
        assert len(records) == 1
        assert records[0].close == 2515.0

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_空のDataFrameで空リストが返る(self, mock_download: object) -> None:
        mock_download.return_value = _make_empty_df()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01")

        assert records == []

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_endがNoneの場合もyf_downloadに渡される(
        self, mock_download: object
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        fetcher.fetch(["1306"], start="2026-04-01")

        mock_download.assert_called_once_with(  # type: ignore[union-attr]
            ["1306.T"],
            start="2026-04-01",
            end=None,
            auto_adjust=True,
        )


class TestEtfPriceFetcherGetPerformance:
    """Tests for EtfPriceFetcher.get_performance method."""

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_パフォーマンスサマリーが計算される(
        self, mock_download: object
    ) -> None:
        # Create a longer DataFrame for performance calculation
        dates = pd.date_range("2023-04-01", periods=100, freq="B")
        prices = 2500.0 + np.cumsum(np.random.default_rng(42).normal(0, 10, 100))
        df = pd.DataFrame(
            {
                "Open": prices - 5,
                "High": prices + 10,
                "Low": prices - 10,
                "Close": prices,
                "Volume": np.full(100, 1000000.0),
            },
            index=dates,
        )
        mock_download.return_value = df  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        summaries = fetcher.get_performance(["1306"], years=3)

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.ticker == "1306.T"
        assert isinstance(summary.total_return, float)
        assert isinstance(summary.annualized_volatility, float)
        assert isinstance(summary.max_drawdown, float)
        assert summary.max_drawdown <= 0.0

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_空のデータで空リストが返る(self, mock_download: object) -> None:
        mock_download.return_value = _make_empty_df()  # type: ignore[union-attr]

        fetcher = EtfPriceFetcher()
        summaries = fetcher.get_performance(["1306"], years=3)

        assert summaries == []
