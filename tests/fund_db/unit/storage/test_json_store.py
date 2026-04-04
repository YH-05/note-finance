"""Unit tests for fund_db.storage.json_store module.

Tests FundDbStore with tmp_path for isolated filesystem operations.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from fund_db.exceptions import StorageError
from fund_db.storage.json_store import FundDbStore


class TestFundDbStoreInit:
    """Tests for FundDbStore initialization."""

    def test_正常系_デフォルトdata_dirが設定される(self) -> None:
        store = FundDbStore()
        assert store.data_dir == Path("data/fund_db")

    def test_正常系_カスタムdata_dirが設定される(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "custom_db"
        store = FundDbStore(data_dir)
        assert store.data_dir == data_dir
        assert data_dir.exists()

    def test_正常系_ディレクトリが自動作成される(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "nested" / "fund_db"
        store = FundDbStore(data_dir)
        assert store.data_dir.exists()
        assert store.data_dir.is_dir()


class TestSaveRecords:
    """Tests for FundDbStore.save_records."""

    def test_正常系_レコードをJSONで保存できる(self, tmp_path: Path) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        records = [
            {"fund_name": "Fund A", "expense_ratio": 0.1},
            {"fund_name": "Fund B", "expense_ratio": 0.2},
        ]
        partition = date(2026, 4, 1)

        path = store.save_records(records, "nisa_unlisted", partition)

        assert path.exists()
        assert path.name == "records.json"

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        assert data["category"] == "nisa_unlisted"
        assert data["partition_date"] == "2026-04-01"
        assert data["record_count"] == 2
        assert len(data["records"]) == 2
        assert data["records"][0]["fund_name"] == "Fund A"

    def test_正常系_partition_dateがNoneの場合今日の日付を使う(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        records = [{"name": "test"}]

        path = store.save_records(records, "test_category")

        assert path.exists()
        # The partition directory should be named with today's date
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["partition_date"] is not None

    def test_正常系_パーティションディレクトリが自動作成される(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        partition = date(2026, 3, 15)

        store.save_records([{"a": 1}], "jpx_listed", partition)

        partition_dir = tmp_path / "fund_db" / "jpx_listed" / "2026-03-15"
        assert partition_dir.exists()
        assert partition_dir.is_dir()

    def test_エッジケース_空リストを保存できる(self, tmp_path: Path) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        partition = date(2026, 4, 1)

        path = store.save_records([], "empty_category", partition)

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        assert data["record_count"] == 0
        assert data["records"] == []


class TestSaveRawExcel:
    """Tests for FundDbStore.save_raw_excel."""

    def test_正常系_バイナリコンテンツを保存できる(self, tmp_path: Path) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        content = b"\x50\x4b\x03\x04" + b"\x00" * 100  # Fake xlsx header
        partition = date(2026, 4, 1)

        path = store.save_raw_excel(
            content, "nisa_unlisted", "tsumitate_target.xlsx", partition
        )

        assert path.exists()
        assert path.name == "tsumitate_target.xlsx"
        assert path.read_bytes() == content
        # raw subdirectory should exist
        assert path.parent.name == "raw"

    def test_正常系_partition_dateがNoneの場合今日の日付を使う(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        content = b"test content"

        path = store.save_raw_excel(content, "test_cat", "file.xlsx")

        assert path.exists()
        assert path.read_bytes() == content


class TestLoadLatest:
    """Tests for FundDbStore.load_latest."""

    def test_正常系_最新パーティションのレコードを読み込む(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")

        # Save records for two different dates
        store.save_records([{"name": "old"}], "nisa_unlisted", date(2026, 3, 1))
        store.save_records([{"name": "new"}], "nisa_unlisted", date(2026, 4, 1))

        result = store.load_latest("nisa_unlisted")

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "new"

    def test_正常系_パーティションが存在しない場合Noneを返す(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")

        result = store.load_latest("nonexistent_category")

        assert result is None

    def test_異常系_records_jsonが壊れている場合Noneを返す(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        partition_dir = tmp_path / "fund_db" / "broken" / "2026-04-01"
        partition_dir.mkdir(parents=True)
        (partition_dir / "records.json").write_text("not valid json")

        result = store.load_latest("broken")

        assert result is None


class TestListPartitions:
    """Tests for FundDbStore.list_partitions."""

    def test_正常系_パーティション日付のリストを返す(self, tmp_path: Path) -> None:
        store = FundDbStore(tmp_path / "fund_db")

        store.save_records([{"a": 1}], "nisa_unlisted", date(2026, 3, 1))
        store.save_records([{"b": 2}], "nisa_unlisted", date(2026, 4, 1))
        store.save_records([{"c": 3}], "nisa_unlisted", date(2026, 3, 15))

        partitions = store.list_partitions("nisa_unlisted")

        assert len(partitions) == 3
        assert partitions == [date(2026, 3, 1), date(2026, 3, 15), date(2026, 4, 1)]

    def test_正常系_カテゴリが存在しない場合空リストを返す(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")

        partitions = store.list_partitions("nonexistent")

        assert partitions == []

    def test_正常系_日付以外のディレクトリをスキップする(self, tmp_path: Path) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        category_dir = tmp_path / "fund_db" / "test_cat"
        category_dir.mkdir(parents=True)

        # Create a valid date partition
        (category_dir / "2026-04-01").mkdir()
        # Create a non-date directory (should be skipped)
        (category_dir / "not-a-date").mkdir()
        (category_dir / "metadata").mkdir()

        partitions = store.list_partitions("test_cat")

        assert len(partitions) == 1
        assert partitions[0] == date(2026, 4, 1)


class TestStorageErrorHandling:
    """Tests for error handling in FundDbStore."""

    def test_異常系_書き込み不可パスでStorageErrorが発生する(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        partition = date(2026, 4, 1)

        # Create the partition dir and make records.json a directory to cause write error
        records_path = tmp_path / "fund_db" / "bad_cat" / "2026-04-01" / "records.json"
        records_path.mkdir(parents=True)

        with pytest.raises(StorageError) as exc_info:
            store.save_records([{"a": 1}], "bad_cat", partition)

        assert exc_info.value.path is not None

    def test_異常系_save_raw_excelで書き込みエラーでStorageError(
        self, tmp_path: Path
    ) -> None:
        store = FundDbStore(tmp_path / "fund_db")
        partition = date(2026, 4, 1)

        # Create a directory where the file should be to cause write error
        file_path = (
            tmp_path / "fund_db" / "bad_cat" / "2026-04-01" / "raw" / "file.xlsx"
        )
        file_path.mkdir(parents=True)

        with pytest.raises(StorageError):
            store.save_raw_excel(b"data", "bad_cat", "file.xlsx", partition)
