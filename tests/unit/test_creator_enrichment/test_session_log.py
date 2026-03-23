"""creator_enrichment.session_log のテスト.

SessionLogger の record_cycle / record_error / finalize が
期待するファイル内容を生成することを検証する。
"""

from pathlib import Path

from creator_enrichment.session_log import SessionLogger
from creator_enrichment.types import CycleReport


class TestSessionLoggerInit:
    """SessionLogger 初期化のテスト."""

    def test_正常系_ログファイルが作成される(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-001", log_dir=tmp_log_dir)
        assert sl.log_path.exists()

    def test_正常系_ログファイルにヘッダーが含まれる(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-001", log_dir=tmp_log_dir)
        content = sl.log_path.read_text(encoding="utf-8")
        assert "# Creator Enrichment Session" in content
        assert "- session_id: test-001" in content
        assert "- start:" in content
        assert "## Cycles" in content

    def test_正常系_ファイル名にセッションIDが含まれる(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("my-session-42", log_dir=tmp_log_dir)
        assert sl.log_path.name == "creator-enrichment-my-session-42.log.md"

    def test_正常系_存在しないディレクトリが自動作成される(
        self, tmp_path: Path
    ) -> None:
        nested_dir = tmp_path / "a" / "b" / "c"
        sl = SessionLogger("nested", log_dir=nested_dir)
        assert sl.log_path.exists()
        assert nested_dir.exists()


class TestRecordCycle:
    """SessionLogger.record_cycle のテスト."""

    def test_正常系_サイクル情報が記録される(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-cycle", log_dir=tmp_log_dir)
        report: CycleReport = {
            "genre": "career",
            "search_results": 12,
            "contents_created": {"Fact": 3, "Tip": 5, "Story": 2},
            "entities_extracted": 18,
            "relations_detected": 7,
            "pipeline_status": "success",
            "cross_entity_added": 4,
        }
        sl.record_cycle(1, report)
        content = sl.log_path.read_text(encoding="utf-8")

        assert "### Cycle 1 - career" in content
        assert "- genre: career" in content
        assert "- search_results: 12" in content
        assert "Fact: 3" in content
        assert "Tip: 5" in content
        assert "Story: 2" in content
        assert "- entities_extracted: 18" in content
        assert "- relations_detected: 7" in content
        assert "- pipeline_status: success" in content

    def test_正常系_複数サイクルが追記される(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-multi", log_dir=tmp_log_dir)
        report1: CycleReport = {
            "genre": "career",
            "search_results": 10,
            "contents_created": {"Fact": 2, "Tip": 3, "Story": 1},
            "entities_extracted": 8,
            "relations_detected": 3,
            "pipeline_status": "success",
            "cross_entity_added": 0,
        }
        report2: CycleReport = {
            "genre": "beauty-romance",
            "search_results": 8,
            "contents_created": {"Fact": 1, "Tip": 4, "Story": 2},
            "entities_extracted": 12,
            "relations_detected": 5,
            "pipeline_status": "dry-run",
            "cross_entity_added": 0,
        }
        sl.record_cycle(1, report1)
        sl.record_cycle(2, report2)
        content = sl.log_path.read_text(encoding="utf-8")

        assert "### Cycle 1 - career" in content
        assert "### Cycle 2 - beauty-romance" in content
        assert "- pipeline_status: dry-run" in content

    def test_正常系_時刻が記録される(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-time", log_dir=tmp_log_dir)
        report: CycleReport = {
            "genre": "spiritual",
            "search_results": 5,
            "contents_created": {"Fact": 1},
            "entities_extracted": 3,
            "relations_detected": 1,
            "pipeline_status": "success",
            "cross_entity_added": 0,
        }
        sl.record_cycle(1, report)
        content = sl.log_path.read_text(encoding="utf-8")
        assert "- time:" in content

    def test_正常系_conftest_sample_cycle_reportで動作する(
        self,
        tmp_log_dir: Path,
        sample_cycle_report: CycleReport,
    ) -> None:
        sl = SessionLogger("test-fixture", log_dir=tmp_log_dir)
        sl.record_cycle(1, sample_cycle_report)
        content = sl.log_path.read_text(encoding="utf-8")
        assert "### Cycle 1 - career" in content
        assert "- search_results: 12" in content


class TestRecordError:
    """SessionLogger.record_error のテスト."""

    def test_正常系_エラー情報が記録される(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-error", log_dir=tmp_log_dir)
        try:
            msg = "Connection refused"
            raise ConnectionError(msg)
        except ConnectionError as e:
            sl.record_error(3, e)

        content = sl.log_path.read_text(encoding="utf-8")
        assert "### Cycle 3 - ERROR" in content
        assert "- error: Connection refused" in content

    def test_正常系_スタックトレースが含まれる(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-traceback", log_dir=tmp_log_dir)
        try:
            msg = "invalid data"
            raise ValueError(msg)
        except ValueError as e:
            sl.record_error(1, e)

        content = sl.log_path.read_text(encoding="utf-8")
        assert "- traceback:" in content
        assert "```" in content
        assert "ValueError" in content
        assert "invalid data" in content

    def test_正常系_tracebackがコードブロックで囲まれる(
        self,
        tmp_log_dir: Path,
    ) -> None:
        sl = SessionLogger("test-code-block", log_dir=tmp_log_dir)
        try:
            msg = "test error"
            raise RuntimeError(msg)
        except RuntimeError as e:
            sl.record_error(2, e)

        content = sl.log_path.read_text(encoding="utf-8")
        # traceback 部分が ``` で囲まれていることを確認
        assert "```\n" in content

    def test_正常系_エラーとサイクルが混在できる(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-mixed", log_dir=tmp_log_dir)
        report: CycleReport = {
            "genre": "career",
            "search_results": 5,
            "contents_created": {"Fact": 1},
            "entities_extracted": 3,
            "relations_detected": 1,
            "pipeline_status": "success",
            "cross_entity_added": 0,
        }
        sl.record_cycle(1, report)
        try:
            msg = "API timeout"
            raise TimeoutError(msg)
        except TimeoutError as e:
            sl.record_error(2, e)

        content = sl.log_path.read_text(encoding="utf-8")
        assert "### Cycle 1 - career" in content
        assert "### Cycle 2 - ERROR" in content
        assert "API timeout" in content


class TestFinalize:
    """SessionLogger.finalize のテスト."""

    def test_正常系_サマリーセクションが記録される(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-finalize", log_dir=tmp_log_dir)
        sl.finalize(total_cycles=5)
        content = sl.log_path.read_text(encoding="utf-8")

        assert "## Summary" in content
        assert "- total_cycles: 5" in content
        assert "- end_reason: completed" in content

    def test_正常系_サイクル記録後にfinalizeできる(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-full-flow", log_dir=tmp_log_dir)
        report: CycleReport = {
            "genre": "career",
            "search_results": 10,
            "contents_created": {"Fact": 2, "Tip": 3, "Story": 1},
            "entities_extracted": 8,
            "relations_detected": 3,
            "pipeline_status": "success",
            "cross_entity_added": 0,
        }
        sl.record_cycle(1, report)
        sl.finalize(total_cycles=1)

        content = sl.log_path.read_text(encoding="utf-8")

        # ヘッダー → サイクル → サマリーの順序を確認
        header_pos = content.index("# Creator Enrichment Session")
        cycle_pos = content.index("### Cycle 1")
        summary_pos = content.index("## Summary")
        assert header_pos < cycle_pos < summary_pos

    def test_正常系_total_cycles_0でも動作する(self, tmp_log_dir: Path) -> None:
        sl = SessionLogger("test-zero", log_dir=tmp_log_dir)
        sl.finalize(total_cycles=0)
        content = sl.log_path.read_text(encoding="utf-8")
        assert "- total_cycles: 0" in content
