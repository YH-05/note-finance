"""Unit tests for fund_db.etf_prices.fetcher module.

Uses unittest.mock to mock yfinance.download(), ensuring tests
run without network access. Verifies NaN → None conversion,
ticker suffix normalization, and performance calculations.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

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
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()
        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01", end="2026-04-04")

        assert len(records) == 3
        assert all(isinstance(r, EtfPriceRecord) for r in records)
        assert records[0].ticker == "1306.T"
        assert records[0].date == date(2026, 4, 1)
        assert records[0].close == 2500.0
        assert records[0].volume == 1000000

        # Verify yf.download was called with correct args
        mock_download.assert_called_once_with(
            ["1306.T"],
            start="2026-04-01",
            end="2026-04-04",
            auto_adjust=True,
        )

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_サフィックスなしティッカーにTが付与される(
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()
        fetcher = EtfPriceFetcher()
        fetcher.fetch(["1306"], start="2026-04-01")

        call_args = mock_download.call_args
        assert call_args[0][0] == ["1306.T"]

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_既にサフィックスがあるティッカーはそのまま(
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()
        fetcher = EtfPriceFetcher()
        fetcher.fetch(["1306.T"], start="2026-04-01")

        call_args = mock_download.call_args
        assert call_args[0][0] == ["1306.T"]

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_NaN値がNoneに変換される(self, mock_download: MagicMock) -> None:
        mock_download.return_value = _make_single_ticker_df_with_nan()
        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01")

        # First record: Open=2490.0, Volume=NaN→None
        assert records[0].open == 2490.0
        assert records[0].volume is None

        # Second record: Open=NaN→None, Volume=1200000
        assert records[1].open is None
        assert records[1].volume == 1200000

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_NaN_closeの行はスキップされる(
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_single_ticker_df_with_nan_close()
        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01")

        # Only the second row (with valid close) should be returned
        assert len(records) == 1
        assert records[0].close == 2515.0

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_空のDataFrameで空リストが返る(
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_empty_df()
        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306"], start="2026-04-01")

        assert records == []

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_endがNoneの場合もyf_downloadに渡される(
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_single_ticker_df()
        fetcher = EtfPriceFetcher()
        fetcher.fetch(["1306"], start="2026-04-01")

        mock_download.assert_called_once_with(
            ["1306.T"],
            start="2026-04-01",
            end=None,
            auto_adjust=True,
        )


def _make_multi_ticker_df() -> pd.DataFrame:
    """Create a MultiIndex DataFrame mimicking yf.download for multiple tickers."""
    dates = pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"])
    arrays = [
        [
            "Close",
            "Close",
            "High",
            "High",
            "Low",
            "Low",
            "Open",
            "Open",
            "Volume",
            "Volume",
        ],
        [
            "1306.T",
            "1321.T",
            "1306.T",
            "1321.T",
            "1306.T",
            "1321.T",
            "1306.T",
            "1321.T",
            "1306.T",
            "1321.T",
        ],
    ]
    columns = pd.MultiIndex.from_arrays(arrays)
    data = np.array(
        [
            [
                2500.0,
                30000.0,
                2510.0,
                30100.0,
                2485.0,
                29900.0,
                2490.0,
                29950.0,
                1e6,
                5e5,
            ],
            [
                2515.0,
                30200.0,
                2520.0,
                30300.0,
                2495.0,
                30100.0,
                2500.0,
                30150.0,
                1.2e6,
                6e5,
            ],
            [
                2525.0,
                30400.0,
                2530.0,
                30500.0,
                2505.0,
                30200.0,
                2510.0,
                30300.0,
                9e5,
                4e5,
            ],
        ]
    )
    return pd.DataFrame(data, index=dates, columns=columns)


def _make_multi_ticker_df_partial_error() -> pd.DataFrame:
    """Create a MultiIndex DataFrame with only one ticker present."""
    dates = pd.to_datetime(["2026-04-01", "2026-04-02"])
    arrays = [
        ["Close", "High", "Low", "Open", "Volume"],
        ["1306.T", "1306.T", "1306.T", "1306.T", "1306.T"],
    ]
    columns = pd.MultiIndex.from_arrays(arrays)
    data = np.array(
        [
            [2500.0, 2510.0, 2485.0, 2490.0, 1e6],
            [2515.0, 2520.0, 2495.0, 2500.0, 1.2e6],
        ]
    )
    return pd.DataFrame(data, index=dates, columns=columns)


class TestEtfPriceFetcherFetchMultipleTickers:
    """Tests for EtfPriceFetcher.fetch with multiple tickers."""

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_複数ティッカーでMultiIndex_DataFrameを処理できる(
        self, mock_download: MagicMock
    ) -> None:
        mock_download.return_value = _make_multi_ticker_df()
        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306", "1321"], start="2026-04-01", end="2026-04-04")

        # Should have 3 records per ticker = 6 total
        assert len(records) == 6
        tickers = {r.ticker for r in records}
        assert tickers == {"1306.T", "1321.T"}

        # Verify records for each ticker
        records_1306 = [r for r in records if r.ticker == "1306.T"]
        records_1321 = [r for r in records if r.ticker == "1321.T"]
        assert len(records_1306) == 3
        assert len(records_1321) == 3
        assert records_1306[0].close == 2500.0
        assert records_1321[0].close == 30000.0

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_複数ティッカーで一部KeyErrorの場合スキップする(
        self, mock_download: MagicMock
    ) -> None:
        # Only 1306.T is in the MultiIndex; 1321.T will cause KeyError in xs()
        mock_download.return_value = _make_multi_ticker_df_partial_error()
        fetcher = EtfPriceFetcher()
        records = fetcher.fetch(["1306", "1321"], start="2026-04-01", end="2026-04-03")

        # Only 1306.T records should be present; 1321.T skipped
        assert all(r.ticker == "1306.T" for r in records)
        assert len(records) == 2

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_get_performanceで1件のみの場合スキップする(
        self, mock_download: MagicMock
    ) -> None:
        """When a ticker has only 1 record, it is skipped in performance calculation."""
        dates = pd.to_datetime(["2026-04-01"])
        df = pd.DataFrame(
            {
                "Open": [2490.0],
                "High": [2510.0],
                "Low": [2485.0],
                "Close": [2500.0],
                "Volume": [1000000.0],
            },
            index=dates,
        )
        mock_download.return_value = df
        fetcher = EtfPriceFetcher()
        summaries = fetcher.get_performance(["1306"], years=3)

        # With only 1 record, performance cannot be calculated
        assert summaries == []


class TestEtfPriceFetcherGetPerformance:
    """Tests for EtfPriceFetcher.get_performance method."""

    @patch("fund_db.etf_prices.fetcher.yf.download")
    def test_正常系_パフォーマンスサマリーが計算される(
        self, mock_download: MagicMock
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
        mock_download.return_value = df
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
    def test_正常系_空のデータで空リストが返る(self, mock_download: MagicMock) -> None:
        mock_download.return_value = _make_empty_df()
        fetcher = EtfPriceFetcher()
        summaries = fetcher.get_performance(["1306"], years=3)

        assert summaries == []
