"""Unit tests for scripts/validate_rss_presets.py.

validate_json_structure, validate_preset_entry, _determine_result_status,
format_results_table の核心ロジックをテストする。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from validate_rss_presets import (
    FileValidationSummary,
    PresetValidationResult,
    _determine_result_status,
    format_results_table,
    validate_json_structure,
    validate_preset_entry,
)

# ---------------------------------------------------------------------------
# validate_json_structure
# ---------------------------------------------------------------------------


class TestValidateJsonStructure:
    """validate_json_structure のテスト。"""

    def test_正常系_正しいJSON構造でエラーなし(self) -> None:
        data = {"version": "1.0", "presets": []}
        errors = validate_json_structure(data)
        assert errors == []

    def test_異常系_ルートがdictでない場合エラー(self) -> None:
        errors = validate_json_structure(["not", "a", "dict"])
        assert len(errors) == 1
        assert "Root must be a JSON object" in errors[0]

    def test_異常系_presetsキーが欠損している場合エラー(self) -> None:
        errors = validate_json_structure({"version": "1.0"})
        assert len(errors) == 1
        assert "'presets'" in errors[0]

    def test_異常系_presetsが配列でない場合エラー(self) -> None:
        errors = validate_json_structure({"presets": {"not": "a list"}})
        assert len(errors) == 1
        assert "'presets' must be an array" in errors[0]

    def test_エッジケース_空のdict(self) -> None:
        errors = validate_json_structure({})
        assert len(errors) >= 1

    def test_エッジケース_Noneはルートが非dictとして扱われる(self) -> None:
        errors = validate_json_structure(None)
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# validate_preset_entry
# ---------------------------------------------------------------------------


_VALID_ENTRY = {
    "url": "https://example.com/feed/",
    "title": "Example Feed",
    "category": "personal_finance",
    "fetch_interval": "daily",
    "enabled": True,
    "tier": 1,
}


class TestValidatePresetEntry:
    """validate_preset_entry のテスト。"""

    def test_正常系_全フィールドが揃っている場合エラーなし(self) -> None:
        url, title, errors, _warnings = validate_preset_entry(_VALID_ENTRY.copy(), 0)
        assert url == "https://example.com/feed/"
        assert title == "Example Feed"
        assert errors == []

    def test_異常系_必須フィールドが欠損している場合エラー(self) -> None:
        entry = {k: v for k, v in _VALID_ENTRY.items() if k != "url"}
        _url, _title, errors, _warnings = validate_preset_entry(entry, 0)
        assert any("url" in e for e in errors)

    def test_異常系_不正URLスキームの場合エラー(self) -> None:
        entry = {**_VALID_ENTRY, "url": "ftp://example.com/feed/"}
        _url, _title, errors, _warnings = validate_preset_entry(entry, 0)
        assert any("scheme" in e.lower() or "http" in e.lower() for e in errors)

    def test_異常系_enabled非boolの場合エラー(self) -> None:
        entry = {**_VALID_ENTRY, "enabled": "yes"}
        _url, _title, errors, _warnings = validate_preset_entry(entry, 0)
        assert any("enabled" in e.lower() or "bool" in e.lower() for e in errors)

    def test_警告系_tier非intの場合警告(self) -> None:
        entry = {**_VALID_ENTRY, "tier": "1"}
        _url, _title, errors, warnings = validate_preset_entry(entry, 0)
        assert errors == []
        assert any("tier" in w.lower() for w in warnings)

    def test_異常系_entryがdictでない場合エラー(self) -> None:
        url, _title, errors, _warnings = validate_preset_entry("not_a_dict", 3)
        assert len(errors) == 1
        assert url == ""

    def test_エッジケース_空dictの場合全必須フィールドが欠損エラー(self) -> None:
        _url, _title, errors, _warnings = validate_preset_entry({}, 0)
        # All required fields are missing
        assert len(errors) >= 5


# ---------------------------------------------------------------------------
# _determine_result_status
# ---------------------------------------------------------------------------


class TestDetermineResultStatus:
    """_determine_result_status の5分岐をテスト。"""

    def _make_result(
        self,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> PresetValidationResult:
        return PresetValidationResult(
            url="https://example.com/feed/",
            title="Test",
            errors=errors or [],
            warnings=warnings or [],
        )

    def test_正常系_エラーあり_ERRORステータス(self) -> None:
        result = self._make_result(errors=["bad url"])
        _determine_result_status(result, 200, result.url)
        assert result.status == "ERROR"

    def test_正常系_警告あり_WARNステータス(self) -> None:
        result = self._make_result(warnings=["tier is string"])
        _determine_result_status(result, 200, result.url)
        assert result.status == "WARN"

    def test_正常系_http400以上_WARNステータスに変わる(self) -> None:
        result = self._make_result()
        _determine_result_status(result, 404, result.url)
        assert result.status == "WARN"
        assert any("404" in w for w in result.warnings)

    def test_正常系_httpNone_WARNステータスに変わる(self) -> None:
        result = self._make_result()
        _determine_result_status(result, None, "https://example.com/feed/")
        assert result.status == "WARN"

    def test_正常系_全クリア_OKステータス(self) -> None:
        result = self._make_result()
        _determine_result_status(result, 200, result.url)
        assert result.status == "OK"


# ---------------------------------------------------------------------------
# TEST-006: format_results_table
# ---------------------------------------------------------------------------


def _make_summary_with_results(
    results: list[PresetValidationResult],
    file_path: str = "/path/to/presets.json",
) -> FileValidationSummary:
    """ヘルパー: 結果リストからFileValidationSummaryを作る。"""
    summary = FileValidationSummary(file_path=file_path)
    for r in results:
        summary.results.append(r)
        summary.total += 1
        if r.status == "OK":
            summary.ok_count += 1
        elif r.status == "WARN":
            summary.warn_count += 1
        elif r.status == "ERROR":
            summary.error_count += 1
    return summary


class TestFormatResultsTable:
    """TEST-006: format_results_table の出力フォーマットテスト。"""

    def _ok_result(
        self, url: str = "https://example.com/feed/"
    ) -> PresetValidationResult:
        r = PresetValidationResult(url=url, title="Feed", errors=[], warnings=[])
        r.status = "OK"
        r.http_code = 200
        r.robots_status = "SKIP"
        return r

    def test_正常系_check_robots_Falseのヘッダーに_robots列がない(self) -> None:
        """check_robots=False のときrobots.txt列がヘッダーに含まれないことを確認する。"""
        summary = _make_summary_with_results([self._ok_result()])
        table = format_results_table(summary, check_robots=False)
        assert "robots.txt" not in table
        assert "Status" in table

    def test_正常系_check_robots_Trueのヘッダーに_robots列がある(self) -> None:
        """check_robots=True のときrobots.txt列がヘッダーに含まれることを確認する。"""
        summary = _make_summary_with_results([self._ok_result()])
        table = format_results_table(summary, check_robots=True)
        assert "robots.txt" in table

    def test_正常系_結果なしのとき_No_presets_メッセージが出る(self) -> None:
        """results が空のとき 'No presets to validate.' が含まれることを確認する。"""
        summary = _make_summary_with_results([])
        table = format_results_table(summary, check_robots=False)
        assert "No presets to validate." in table

    def test_正常系_サマリー行にOK_WARN_ERROR件数が含まれる(self) -> None:
        """フッターに Total/OK/WARN/ERROR の集計が含まれることを確認する。"""
        ok_r = self._ok_result("https://example.com/feed1/")
        warn_r = PresetValidationResult(
            url="https://example.com/feed2/",
            title="Feed2",
            errors=[],
            warnings=["tier is string"],
        )
        warn_r.status = "WARN"
        warn_r.http_code = 200
        warn_r.robots_status = "SKIP"

        summary = _make_summary_with_results([ok_r, warn_r])
        table = format_results_table(summary, check_robots=False)

        assert "OK: 1" in table
        assert "WARN: 1" in table
        assert "ERROR: 0" in table
        assert "Total: 2" in table

    def test_正常系_エラーがある場合ERROR行が出力される(self) -> None:
        """errors リストがある場合 'ERROR:' 行が含まれることを確認する。"""
        err_r = PresetValidationResult(
            url="",
            title="",
            errors=["missing url field"],
            warnings=[],
        )
        err_r.status = "ERROR"
        err_r.http_code = None
        err_r.robots_status = "SKIP"

        summary = _make_summary_with_results([err_r])
        table = format_results_table(summary, check_robots=False)
        assert "ERROR: missing url field" in table
