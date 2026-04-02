"""Unit tests for scripts/migrate_entity_properties_to_nodes.py."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from scripts.migrate_entity_properties_to_nodes import (
    COUNTRY_NORMALIZATION,
    GICS_SECTOR_NORMALIZATION,
    GICS_SECTORS,
    MigrationStats,
    apply_sector_normalization,
    build_sector_normalization_ops,
    count_industry_nodes,
    count_industry_relationships,
    create_country_nodes,
    create_ticker_nodes,
    fetch_all_sectors,
    fetch_entities_with_country,
    fetch_entities_with_ticker,
    fetch_ticker_identifiers,
    migrate_identifiers_to_ticker,
    normalize_country,
    normalize_sector,
    run_phase_country,
    run_phase_identifier,
    run_phase_sector,
    run_phase_ticker,
)

# ---------------------------------------------------------------------------
# GICS_SECTORS 定数
# ---------------------------------------------------------------------------


class TestGicsSectors:
    """GICS_SECTORS 定数の検証。"""

    def test_正常系_11種のGICSセクターが定義されている(self) -> None:
        """GICS 11種が定義されていることを確認。"""
        assert len(GICS_SECTORS) == 11

    def test_正常系_Information_Technologyが含まれる(self) -> None:
        assert "Information Technology" in GICS_SECTORS

    def test_正常系_Communication_Servicesが含まれる(self) -> None:
        assert "Communication Services" in GICS_SECTORS

    def test_正常系_全セクターが英語PascalCase(self) -> None:
        """全GICS正規名が英語（先頭大文字）であることを確認。"""
        for sector in GICS_SECTORS:
            assert sector[0].isupper(), f"{sector} does not start with uppercase"


# ---------------------------------------------------------------------------
# GICS_SECTOR_NORMALIZATION 定数
# ---------------------------------------------------------------------------


class TestGicsSectorNormalization:
    """GICS_SECTOR_NORMALIZATION 定数の検証。"""

    def test_正常系_technologyがInformationTechnologyにマップされる(self) -> None:
        assert GICS_SECTOR_NORMALIZATION["technology"] == "Information Technology"

    def test_正常系_telecomがCommunicationServicesにマップされる(self) -> None:
        assert GICS_SECTOR_NORMALIZATION["telecom"] == "Communication Services"

    def test_正常系_全マッピング先がGICS正規名(self) -> None:
        """全マッピング先値がGICS_SECTORSに含まれることを確認。"""
        for raw, canonical in GICS_SECTOR_NORMALIZATION.items():
            assert canonical in GICS_SECTORS, (
                f"'{raw}' maps to '{canonical}' which is not a GICS sector"
            )

    def test_正常系_Identity_mappingが存在する(self) -> None:
        """GICS正規名自体もマッピングキーに含まれることを確認（冪等性）。"""
        for sector in GICS_SECTORS:
            assert sector in GICS_SECTOR_NORMALIZATION, (
                f"GICS sector '{sector}' not in GICS_SECTOR_NORMALIZATION"
            )


# ---------------------------------------------------------------------------
# COUNTRY_NORMALIZATION 定数
# ---------------------------------------------------------------------------


class TestCountryNormalization:
    """COUNTRY_NORMALIZATION 定数の検証。"""

    def test_正常系_japanが正規化される(self) -> None:
        assert COUNTRY_NORMALIZATION["japan"] == ("Japan", "日本")

    def test_正常系_usが正規化される(self) -> None:
        assert COUNTRY_NORMALIZATION["us"] == ("United States", "米国")

    def test_正常系_日本語キーで正規化できる(self) -> None:
        assert COUNTRY_NORMALIZATION["日本"] == ("Japan", "日本")

    def test_正常系_全マッピング先タプルが正しい形式(self) -> None:
        """全マッピング先が (str, str) のタプルであることを確認。"""
        for key, value in COUNTRY_NORMALIZATION.items():
            assert isinstance(value, tuple), f"'{key}' does not map to a tuple"
            assert len(value) == 2, f"'{key}' tuple length is not 2"
            assert isinstance(value[0], str), f"'{key}' first element is not str"
            assert isinstance(value[1], str), f"'{key}' second element is not str"


# ---------------------------------------------------------------------------
# normalize_country
# ---------------------------------------------------------------------------


class TestNormalizeCountry:
    """normalize_country 関数のテスト。"""

    def test_正常系_大文字小文字を無視してマッピング(self) -> None:
        result = normalize_country("Japan")
        assert result == ("Japan", "日本")

    def test_正常系_小文字でマッピング(self) -> None:
        result = normalize_country("japan")
        assert result == ("Japan", "日本")

    def test_正常系_USAが正規化される(self) -> None:
        result = normalize_country("USA")
        assert result == ("United States", "米国")

    def test_正常系_日本語で正規化できる(self) -> None:
        result = normalize_country("日本")
        assert result == ("Japan", "日本")

    def test_正常系_indonesia(self) -> None:
        result = normalize_country("indonesia")
        assert result == ("Indonesia", "インドネシア")

    def test_エッジケース_未定義の国名はNone(self) -> None:
        result = normalize_country("unknowncountry123")
        assert result is None

    def test_エッジケース_前後のスペースを除去して処理(self) -> None:
        result = normalize_country("  japan  ")
        assert result == ("Japan", "日本")

    def test_エッジケース_空文字列はNone(self) -> None:
        result = normalize_country("")
        assert result is None


# ---------------------------------------------------------------------------
# normalize_sector
# ---------------------------------------------------------------------------


class TestNormalizeSector:
    """normalize_sector 関数のテスト。"""

    def test_正常系_technologyがInformationTechnologyに変換される(self) -> None:
        result = normalize_sector("technology")
        assert result == "Information Technology"

    def test_正常系_telecomがCommunicationServicesに変換される(self) -> None:
        result = normalize_sector("telecom")
        assert result == "Communication Services"

    def test_正常系_既にGICS正規名はそのまま返る(self) -> None:
        result = normalize_sector("Information Technology")
        assert result == "Information Technology"

    def test_正常系_大文字小文字を無視してマッピング(self) -> None:
        result = normalize_sector("TECHNOLOGY")
        assert result == "Information Technology"

    def test_エッジケース_未定義のセクター名はNone(self) -> None:
        result = normalize_sector("unknown_sector_xyz")
        assert result is None

    def test_正常系_全GICS正規名がそのまま返る(self) -> None:
        """GICS正規名を入力すると変更なく返ることを確認（冪等性）。"""
        for sector in GICS_SECTORS:
            result = normalize_sector(sector)
            assert result == sector, (
                f"normalize_sector('{sector}') should return '{sector}'"
            )


# ---------------------------------------------------------------------------
# MigrationStats
# ---------------------------------------------------------------------------


class TestMigrationStats:
    """MigrationStats データクラスのテスト。"""

    def test_正常系_デフォルト値が全て0(self) -> None:
        stats = MigrationStats()
        assert stats.ticker_nodes_created == 0
        assert stats.ticker_rels_created == 0
        assert stats.country_nodes_created == 0
        assert stats.sector_normalized == 0
        assert stats.identifier_migrated == 0

    def test_正常系_値を設定できる(self) -> None:
        stats = MigrationStats(ticker_nodes_created=5, country_nodes_created=3)
        assert stats.ticker_nodes_created == 5
        assert stats.country_nodes_created == 3


# ---------------------------------------------------------------------------
# fetch_entities_with_ticker
# ---------------------------------------------------------------------------


class TestFetchEntitiesWithTicker:
    """fetch_entities_with_ticker のテスト。"""

    def test_正常系_tickerプロパティを持つEntityが返る(self) -> None:
        mock_session = MagicMock()
        mock_record1 = MagicMock()
        mock_record1.__getitem__ = lambda self, key: {
            "entity_key": "apple::company",
            "name": "Apple Inc",
            "ticker": "AAPL",
        }[key]
        mock_record2 = MagicMock()
        mock_record2.__getitem__ = lambda self, key: {
            "entity_key": "google::company",
            "name": "Alphabet Inc",
            "ticker": "GOOGL",
        }[key]
        mock_session.run.return_value = [mock_record1, mock_record2]

        result = fetch_entities_with_ticker(mock_session)

        assert len(result) == 2
        assert result[0]["entity_key"] == "apple::company"
        assert result[0]["ticker"] == "AAPL"

    def test_正常系_結果が空の場合は空リスト(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []

        result = fetch_entities_with_ticker(mock_session)

        assert result == []


# ---------------------------------------------------------------------------
# fetch_entities_with_country
# ---------------------------------------------------------------------------


class TestFetchEntitiesWithCountry:
    """fetch_entities_with_country のテスト。"""

    def test_正常系_countryプロパティを持つEntityが返る(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {
            "entity_key": "toyota::company",
            "name": "Toyota Motor",
            "country": "Japan",
        }[key]
        mock_session.run.return_value = [mock_record]

        result = fetch_entities_with_country(mock_session)

        assert len(result) == 1
        assert result[0]["country"] == "Japan"


# ---------------------------------------------------------------------------
# create_ticker_nodes
# ---------------------------------------------------------------------------


class TestCreateTickerNodes:
    """create_ticker_nodes のテスト。"""

    def test_正常系_Tickerノードを作成しリレーションを付与する(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"tid": "ticker_aapl"}[key]
        mock_session.run.return_value.single.return_value = mock_record

        entities = [
            {"entity_key": "apple::company", "name": "Apple Inc", "ticker": "AAPL"}
        ]
        nodes, rels, failed = create_ticker_nodes(mock_session, entities)

        assert nodes == 1
        assert rels == 1
        assert failed == 0
        mock_session.run.assert_called_once()

    def test_正常系_dry_runでは書き込みなし(self) -> None:
        mock_session = MagicMock()

        entities = [
            {"entity_key": "apple::company", "name": "Apple Inc", "ticker": "AAPL"}
        ]
        nodes, rels, failed = create_ticker_nodes(mock_session, entities, dry_run=True)

        assert nodes == 1
        assert rels == 1
        assert failed == 0
        mock_session.run.assert_not_called()

    def test_正常系_空のEntityリストで0件(self) -> None:
        mock_session = MagicMock()
        nodes, rels, failed = create_ticker_nodes(mock_session, [])

        assert nodes == 0
        assert rels == 0
        assert failed == 0

    def test_異常系_Neo4j例外でfailedが増加(self) -> None:
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j connection error")

        entities = [
            {"entity_key": "apple::company", "name": "Apple Inc", "ticker": "AAPL"}
        ]
        nodes, _rels, failed = create_ticker_nodes(mock_session, entities)

        assert nodes == 0
        assert failed == 1

    def test_正常系_Entityが見つからない場合はノード作成しない(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = None

        entities = [
            {
                "entity_key": "nonexistent::company",
                "name": "Ghost Corp",
                "ticker": "GHOST",
            }
        ]
        nodes, rels, failed = create_ticker_nodes(mock_session, entities)

        assert nodes == 0
        assert rels == 0
        assert failed == 0


# ---------------------------------------------------------------------------
# create_country_nodes
# ---------------------------------------------------------------------------


class TestCreateCountryNodes:
    """create_country_nodes のテスト。"""

    def test_正常系_Countryノードを作成しリレーションを付与する(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"cid": "country_japan"}[key]
        mock_session.run.return_value.single.return_value = mock_record

        entities = [
            {"entity_key": "toyota::company", "name": "Toyota", "country": "Japan"}
        ]
        nodes, rels, skipped, failed = create_country_nodes(mock_session, entities)

        assert nodes == 1
        assert rels == 1
        assert skipped == 0
        assert failed == 0

    def test_正常系_dry_runでは書き込みなし(self) -> None:
        mock_session = MagicMock()

        entities = [
            {"entity_key": "toyota::company", "name": "Toyota", "country": "Japan"}
        ]
        nodes, rels, _skipped, _failed = create_country_nodes(
            mock_session, entities, dry_run=True
        )

        assert nodes == 1
        assert rels == 1
        mock_session.run.assert_not_called()

    def test_正常系_日本語country値も正規化できる(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"cid": "country_japan"}[key]
        mock_session.run.return_value.single.return_value = mock_record

        entities = [
            {"entity_key": "toyota::company", "name": "Toyota", "country": "日本"}
        ]
        nodes, _rels, _skipped, failed = create_country_nodes(mock_session, entities)

        assert nodes == 1
        assert failed == 0

    def test_正常系_未知のcountry値は生値で登録(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"cid": "country_unknownland"}[key]
        mock_session.run.return_value.single.return_value = mock_record

        entities = [
            {
                "entity_key": "xyz::company",
                "name": "XYZ Corp",
                "country": "Unknownland",
            }
        ]
        _nodes, _rels, _skipped, failed = create_country_nodes(mock_session, entities)

        # 未知でも登録を試みる（スキップしない）
        assert failed == 0


# ---------------------------------------------------------------------------
# fetch_all_sectors
# ---------------------------------------------------------------------------


class TestFetchAllSectors:
    """fetch_all_sectors のテスト。"""

    def test_正常系_全Sectorノードが返る(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {
            "sector_id": "sector_1",
            "name": "technology",
        }[key]
        mock_session.run.return_value = [mock_record]

        result = fetch_all_sectors(mock_session)

        assert len(result) == 1
        assert result[0]["name"] == "technology"


# ---------------------------------------------------------------------------
# build_sector_normalization_ops
# ---------------------------------------------------------------------------


class TestBuildSectorNormalizationOps:
    """build_sector_normalization_ops のテスト。"""

    def test_正常系_未知のセクター名はスキップ(self) -> None:
        sectors = [
            {"sector_id": "s1", "name": "unknown_xyz"},
        ]
        ops = build_sector_normalization_ops(sectors)
        assert len(ops) == 0

    def test_正常系_正規化対象セクターが含まれる(self) -> None:
        sectors = [
            {"sector_id": "s1", "name": "technology"},
            {"sector_id": "s2", "name": "telecom"},
        ]
        ops = build_sector_normalization_ops(sectors)
        assert len(ops) == 2
        assert ops[0]["canonical_name"] == "Information Technology"
        assert ops[1]["canonical_name"] == "Communication Services"

    def test_正常系_既に正規名のセクターも含まれる(self) -> None:
        """既にGICS正規名のセクターもopsに含まれる（冪等のため）。"""
        sectors = [
            {"sector_id": "s1", "name": "Information Technology"},
        ]
        ops = build_sector_normalization_ops(sectors)
        assert len(ops) == 1
        assert ops[0]["raw_name"] == "Information Technology"
        assert ops[0]["canonical_name"] == "Information Technology"

    def test_エッジケース_空のセクターリストで空のops(self) -> None:
        ops = build_sector_normalization_ops([])
        assert ops == []


# ---------------------------------------------------------------------------
# apply_sector_normalization
# ---------------------------------------------------------------------------


class TestApplySectorNormalization:
    """apply_sector_normalization のテスト。"""

    def test_正常系_セクター名が正規化される(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"sid": "sector_1"}[key]
        mock_session.run.return_value.single.return_value = mock_record

        ops = [
            {
                "sector_id": "s1",
                "raw_name": "technology",
                "canonical_name": "Information Technology",
            },
        ]
        normalized, failed = apply_sector_normalization(mock_session, ops)

        assert normalized == 1
        assert failed == 0

    def test_正常系_既に正規名のセクターはSETせずスキップ(self) -> None:
        """raw_name == canonical_name のセクターは SET 不要でスキップされる。"""
        mock_session = MagicMock()

        ops = [
            {
                "sector_id": "s1",
                "raw_name": "Information Technology",
                "canonical_name": "Information Technology",
            },
        ]
        normalized, failed = apply_sector_normalization(mock_session, ops)

        assert normalized == 1
        assert failed == 0
        mock_session.run.assert_not_called()

    def test_正常系_dry_runでは書き込みなし(self) -> None:
        mock_session = MagicMock()

        ops = [
            {
                "sector_id": "s1",
                "raw_name": "technology",
                "canonical_name": "Information Technology",
            },
        ]
        normalized, _failed = apply_sector_normalization(
            mock_session, ops, dry_run=True
        )

        assert normalized == 1
        mock_session.run.assert_not_called()

    def test_異常系_Neo4j例外でfailedが増加(self) -> None:
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")

        ops = [
            {
                "sector_id": "s1",
                "raw_name": "technology",
                "canonical_name": "Information Technology",
            },
        ]
        normalized, failed = apply_sector_normalization(mock_session, ops)

        assert normalized == 0
        assert failed == 1

    def test_エッジケース_空のopsで0件(self) -> None:
        mock_session = MagicMock()
        normalized, failed = apply_sector_normalization(mock_session, [])

        assert normalized == 0
        assert failed == 0


# ---------------------------------------------------------------------------
# count_industry_relationships / count_industry_nodes
# ---------------------------------------------------------------------------


class TestCountIndustry:
    """Industry 集計関数のテスト。"""

    def test_正常系_IN_INDUSTRYリレーション件数を返す(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"cnt": 91}[key]
        mock_session.run.return_value.single.return_value = mock_record

        result = count_industry_relationships(mock_session)

        assert result == 91

    def test_正常系_Industryノード件数を返す(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"cnt": 48}[key]
        mock_session.run.return_value.single.return_value = mock_record

        result = count_industry_nodes(mock_session)

        assert result == 48

    def test_エッジケース_結果がない場合は0を返す(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = None

        result_rels = count_industry_relationships(mock_session)
        result_nodes = count_industry_nodes(mock_session)

        assert result_rels == 0
        assert result_nodes == 0


# ---------------------------------------------------------------------------
# fetch_ticker_identifiers
# ---------------------------------------------------------------------------


class TestFetchTickerIdentifiers:
    """fetch_ticker_identifiers のテスト。"""

    def test_正常系_ticker種別のIdentifierが返る(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {
            "identifier_id": "id_1",
            "value": "TLKM IJ",
            "scheme": "exchange_ticker",
            "entity_key": "telkom::company",
        }[key]
        mock_session.run.return_value = [mock_record]

        result = fetch_ticker_identifiers(mock_session)

        assert len(result) == 1
        assert result[0]["value"] == "TLKM IJ"

    def test_正常系_結果が空の場合は空リスト(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []

        result = fetch_ticker_identifiers(mock_session)

        assert result == []


# ---------------------------------------------------------------------------
# migrate_identifiers_to_ticker
# ---------------------------------------------------------------------------


class TestMigrateIdentifiersToTicker:
    """migrate_identifiers_to_ticker のテスト。"""

    def test_正常系_IdentifierをTickerに統合する(self) -> None:
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"tid": "ticker_tlkm_ij"}[key]
        mock_session.run.return_value.single.return_value = mock_record

        identifiers = [
            {
                "identifier_id": "id_1",
                "value": "TLKM IJ",
                "scheme": "exchange_ticker",
                "entity_key": "telkom::company",
            }
        ]
        migrated, skipped, failed = migrate_identifiers_to_ticker(
            mock_session, identifiers
        )

        assert migrated == 1
        assert skipped == 0
        assert failed == 0

    def test_正常系_dry_runでは書き込みなし(self) -> None:
        mock_session = MagicMock()

        identifiers = [
            {
                "identifier_id": "id_1",
                "value": "TLKM IJ",
                "scheme": "exchange_ticker",
                "entity_key": "telkom::company",
            }
        ]
        migrated, _skipped, _failed = migrate_identifiers_to_ticker(
            mock_session, identifiers, dry_run=True
        )

        assert migrated == 1
        mock_session.run.assert_not_called()

    def test_正常系_valueが空の場合はスキップ(self) -> None:
        mock_session = MagicMock()

        identifiers = [
            {
                "identifier_id": "id_empty",
                "value": "",
                "scheme": "exchange_ticker",
                "entity_key": "ghost::company",
            }
        ]
        migrated, skipped, failed = migrate_identifiers_to_ticker(
            mock_session, identifiers
        )

        assert migrated == 0
        assert skipped == 1
        assert failed == 0

    def test_異常系_Neo4j例外でfailedが増加(self) -> None:
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")

        identifiers = [
            {
                "identifier_id": "id_1",
                "value": "AAPL",
                "scheme": "exchange_ticker",
                "entity_key": "apple::company",
            }
        ]
        migrated, _skipped, failed = migrate_identifiers_to_ticker(
            mock_session, identifiers
        )

        assert failed == 1
        assert migrated == 0

    def test_エッジケース_空のリストで0件(self) -> None:
        mock_session = MagicMock()
        migrated, skipped, failed = migrate_identifiers_to_ticker(mock_session, [])

        assert migrated == 0
        assert skipped == 0
        assert failed == 0


# ---------------------------------------------------------------------------
# Phase runner functions
# ---------------------------------------------------------------------------


class TestPhaseRunners:
    """フェーズ実行関数のテスト。"""

    def test_正常系_run_phase_tickerが統計を返す(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []  # fetch returns empty list

        stats = run_phase_ticker(mock_session, dry_run=True)

        assert isinstance(stats, MigrationStats)
        assert stats.ticker_nodes_created == 0

    def test_正常系_run_phase_countryが統計を返す(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []

        stats = run_phase_country(mock_session, dry_run=True)

        assert isinstance(stats, MigrationStats)
        assert stats.country_nodes_created == 0

    def test_正常系_run_phase_sectorが統計を返す(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []

        stats = run_phase_sector(mock_session, dry_run=True)

        assert isinstance(stats, MigrationStats)

    def test_正常系_run_phase_identifierが統計を返す(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = []

        stats = run_phase_identifier(mock_session, dry_run=True)

        assert isinstance(stats, MigrationStats)
        assert stats.identifier_migrated == 0
