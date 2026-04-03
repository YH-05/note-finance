"""Tests for scripts/backfill_deterministic_research_gaps.py."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from backfill_deterministic_research_gaps import (
    _build_claim_rows,
    _build_domain_rows,
    _build_fact_rows,
    _build_insight_rows,
    _normalize_date_value,
    main,
    parse_args,
)


class TestNormalizeDateValue:
    def test_正常系_iso日時文字列を日付に正規化(self) -> None:
        assert _normalize_date_value("2026-03-26T12:34:56+09:00") == "2026-03-26"

    def test_正常系_date型をそのまま文字列化(self) -> None:
        assert _normalize_date_value(date(2026, 3, 26)) == "2026-03-26"

    def test_異常系_非日付文字列はNone(self) -> None:
        assert _normalize_date_value("not-a-date") is None

    def test_正常系_datetime型を日付に変換(self) -> None:
        value = datetime(2026, 3, 26, 9, 15, 0)
        assert _normalize_date_value(value) == "2026-03-26"


class TestBuildDomainRows:
    def test_正常系_http_urlからdomainとFROM_DOMAIN候補を生成(self) -> None:
        rows, skipped = _build_domain_rows(
            [
                {
                    "source_id": "source-1",
                    "url": "https://www.example.com/path?q=1",
                    "domain": None,
                }
            ]
        )
        assert skipped == 0
        assert rows == [
            {
                "source_id": "source-1",
                "domain_id": "www.example.com",
                "domain_name": "www.example.com",
                "base_url": "https://www.example.com",
                "default_language": "",
            }
        ]

    def test_異常系_domain抽出不能な候補はスキップ(self) -> None:
        rows, skipped = _build_domain_rows(
            [{"source_id": "source-2", "url": "", "domain": None}]
        )
        assert rows == []
        assert skipped == 1


class TestBuildFactRows:
    def test_正常系_単一Sourceからsource_urlとas_of_dateを補完(self) -> None:
        rows, skipped = _build_fact_rows(
            [
                {
                    "fact_id": "fact-1",
                    "source_url": None,
                    "as_of_date": None,
                    "source_count": 1,
                    "sources": [
                        {
                            "source_id": "source-1",
                            "url": "https://example.com/report",
                            "published_at": "2026-03-25T01:02:03+00:00",
                            "published_date": None,
                            "filing_date": None,
                        }
                    ],
                }
            ]
        )
        assert skipped == 0
        assert rows == [
            {
                "fact_id": "fact-1",
                "source_url": "https://example.com/report",
                "as_of_date": "2026-03-25",
            }
        ]

    def test_異常系_複数Sourceに紐づくFactは曖昧としてスキップ(self) -> None:
        rows, skipped = _build_fact_rows(
            [
                {
                    "fact_id": "fact-2",
                    "source_url": None,
                    "as_of_date": None,
                    "source_count": 2,
                    "sources": [
                        {"url": "https://example.com/a"},
                        {"url": "https://example.com/b"},
                    ],
                }
            ]
        )
        assert rows == []
        assert skipped == 1

    def test_正常系_既存値があり新規補完不要なら行を作らない(self) -> None:
        rows, skipped = _build_fact_rows(
            [
                {
                    "fact_id": "fact-3",
                    "source_url": "https://example.com/existing",
                    "as_of_date": "2026-03-01",
                    "source_count": 1,
                    "sources": [
                        {
                            "source_id": "source-3",
                            "url": "https://example.com/existing",
                            "published_at": "2026-03-25T01:02:03+00:00",
                            "published_date": None,
                            "filing_date": None,
                        }
                    ],
                }
            ]
        )
        assert rows == []
        assert skipped == 0


class TestBuildClaimRows:
    def test_正常系_重複なしのABOUT候補を生成(self) -> None:
        rows, skipped = _build_claim_rows(
            [
                {"claim_id": "claim-1", "entity_id": "entity-1"},
                {"claim_id": "claim-1", "entity_id": "entity-1"},
                {"claim_id": "claim-1", "entity_id": "entity-2"},
            ]
        )
        assert skipped == 0
        assert rows == [
            {"claim_id": "claim-1", "entity_id": "entity-1"},
            {"claim_id": "claim-1", "entity_id": "entity-2"},
        ]


class TestBuildInsightRows:
    def test_正常系_導出Entityが1件ならABOUT候補を生成(self) -> None:
        rows, skipped = _build_insight_rows(
            [
                {
                    "insight_id": "insight-1",
                    "derived": [
                        {
                            "labels": ["Fact"],
                            "rel_type": "RELATES_TO",
                            "entity_id": "entity-1",
                        },
                        {
                            "labels": ["Claim"],
                            "rel_type": "ABOUT",
                            "entity_id": "entity-1",
                        },
                    ],
                }
            ]
        )
        assert skipped == 0
        assert rows == [{"insight_id": "insight-1", "entity_id": "entity-1"}]

    def test_異常系_導出EntityがRELATES_TOのみで1件なら行を作成(self) -> None:
        # Wave7 (Issue #312): ABOUT は廃止。Source + ABOUT は無視される
        # Fact + RELATES_TO のみが有効 → entity-1 のみ derivable → row 作成
        rows, skipped = _build_insight_rows(
            [
                {
                    "insight_id": "insight-2",
                    "derived": [
                        {
                            "labels": ["Fact"],
                            "rel_type": "RELATES_TO",
                            "entity_id": "entity-1",
                        },
                        {
                            "labels": ["Source"],
                            "rel_type": "ABOUT",  # 廃止済み → 無視
                            "entity_id": "entity-2",
                        },
                    ],
                }
            ]
        )
        assert rows == [{"insight_id": "insight-2", "entity_id": "entity-1"}]
        assert skipped == 0

    def test_正常系_Source由来でRELATES_TOは有効(self) -> None:
        # Wave7 (Issue #312): Source + RELATES_TO (旧 MENTIONS) は有効
        rows, skipped = _build_insight_rows(
            [
                {
                    "insight_id": "insight-3",
                    "derived": [
                        {
                            "labels": ["Source"],
                            "rel_type": "RELATES_TO",
                            "entity_id": "entity-1",
                        }
                    ],
                }
            ]
        )
        assert rows == [{"insight_id": "insight-3", "entity_id": "entity-1"}]
        assert skipped == 0


class TestCli:
    def test_正常系_stageとdry_runを解釈(self) -> None:
        args = parse_args(["--stage", "facts", "--dry-run", "--limit", "50"])
        assert args.stage == "facts"
        assert args.dry_run is True
        assert args.limit == 50

    def test_正常系_dry_runでは書き込み関数を呼ばない(self, capsys) -> None:
        mock_driver = MagicMock()

        with (
            patch(
                "backfill_deterministic_research_gaps.create_driver",
                return_value=mock_driver,
            ),
            patch(
                "backfill_deterministic_research_gaps._fetch_domain_candidates",
                return_value=[
                    {
                        "source_id": "source-1",
                        "url": "https://example.com/report",
                        "domain": None,
                    }
                ],
            ),
            patch(
                "backfill_deterministic_research_gaps._write_domain_rows",
            ) as write_mock,
        ):
            exit_code = main(["--stage", "domains", "--dry-run"])

        output = capsys.readouterr().out
        assert exit_code == 0
        assert "[domains]" in output
        assert "planned" in output
        write_mock.assert_not_called()
        mock_driver.close.assert_called_once()
