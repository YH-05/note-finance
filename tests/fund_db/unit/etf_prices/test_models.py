"""Unit tests for fund_db.etf_prices.models module.

Tests EtfPriceRecord and EtfPerformanceSummary Pydantic models,
including field validation, NaN handling, and NonNull constraints.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from fund_db.etf_prices.models import EtfPerformanceSummary, EtfPriceRecord


class TestEtfPriceRecord:
    """Tests for EtfPriceRecord model."""

    def test_正常系_全フィールドを指定して作成できる(self) -> None:
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            open=2490.0,
            high=2510.0,
            low=2485.0,
            close=2500.0,
            volume=1000000,
        )
        assert record.ticker == "1306.T"
        assert record.date == date(2026, 4, 1)
        assert record.open == 2490.0
        assert record.high == 2510.0
        assert record.low == 2485.0
        assert record.close == 2500.0
        assert record.volume == 1000000

    def test_正常系_closeのみ必須で他はデフォルトNone(self) -> None:
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            close=2500.0,
        )
        assert record.close == 2500.0
        assert record.open is None
        assert record.high is None
        assert record.low is None
        assert record.volume is None

    def test_異常系_closeが欠落するとValidationError(self) -> None:
        with pytest.raises(ValidationError):
            EtfPriceRecord(  # type: ignore[call-arg]
                ticker="1306.T",
                date=date(2026, 4, 1),
                # close is missing
            )

    def test_異常系_closeにNaNを渡すとValidationError(self) -> None:
        with pytest.raises(ValidationError):
            EtfPriceRecord(
                ticker="1306.T",
                date=date(2026, 4, 1),
                close=float("nan"),
            )

    def test_正常系_volumeにNoneを設定できる(self) -> None:
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            close=2500.0,
            volume=None,
        )
        assert record.volume is None

    def test_正常系_openやhighにNoneを設定できる(self) -> None:
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            open=None,
            high=None,
            low=None,
            close=2500.0,
            volume=None,
        )
        assert record.open is None
        assert record.high is None
        assert record.low is None

    def test_正常系_volumeに整数を設定できる(self) -> None:
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            close=2500.0,
            volume=500000,
        )
        assert record.volume == 500000

    def test_正常系_closeにゼロを設定できる(self) -> None:
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            close=0.0,
        )
        assert record.close == 0.0

    def test_正常系_closeに負の値を設定できる(self) -> None:
        """Pydantic does not restrict negative close values by default."""
        record = EtfPriceRecord(
            ticker="1306.T",
            date=date(2026, 4, 1),
            close=-10.0,
        )
        assert record.close == -10.0


class TestEtfPerformanceSummary:
    """Tests for EtfPerformanceSummary model."""

    def test_正常系_全フィールドを指定して作成できる(self) -> None:
        summary = EtfPerformanceSummary(
            ticker="1306.T",
            period_start=date(2023, 4, 1),
            period_end=date(2026, 4, 1),
            total_return=0.45,
            annualized_volatility=0.18,
            max_drawdown=-0.12,
        )
        assert summary.ticker == "1306.T"
        assert summary.period_start == date(2023, 4, 1)
        assert summary.period_end == date(2026, 4, 1)
        assert summary.total_return == pytest.approx(0.45)
        assert summary.annualized_volatility == pytest.approx(0.18)
        assert summary.max_drawdown == pytest.approx(-0.12)

    def test_異常系_必須フィールドが欠けるとValidationError(self) -> None:
        with pytest.raises(ValidationError):
            EtfPerformanceSummary(  # type: ignore[call-arg]
                ticker="1306.T",
                period_start=date(2023, 4, 1),
                # period_end, total_return, etc. are missing
            )
