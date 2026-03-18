"""skill_run_tracer.py の純粋関数に対するユニットテスト。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# generate_skill_run_id
# ---------------------------------------------------------------------------


class TestGenerateSkillRunId:
    """generate_skill_run_id のテスト。"""

    def test_正常系_決定論的にIDが生成される(self) -> None:
        """同じ入力で同じ ID が生成されることを確認。"""
        from scripts.skill_run_tracer import generate_skill_run_id

        id1 = generate_skill_run_id(
            "test-skill", "session-1", "2026-03-18T00:00:00+00:00"
        )
        id2 = generate_skill_run_id(
            "test-skill", "session-1", "2026-03-18T00:00:00+00:00"
        )
        assert id1 == id2

    def test_正常系_SHA256の先頭32文字(self) -> None:
        """生成される ID が SHA-256 の先頭 32 文字であることを確認。"""
        from scripts.skill_run_tracer import generate_skill_run_id

        skill_name = "test-skill"
        session_id = "session-1"
        start_at = "2026-03-18T00:00:00+00:00"
        result = generate_skill_run_id(skill_name, session_id, start_at)

        expected_key = f"{skill_name}:{session_id}:{start_at}"
        expected = hashlib.sha256(expected_key.encode()).hexdigest()[:32]
        assert result == expected

    def test_正常系_32文字の長さ(self) -> None:
        """生成される ID が 32 文字であることを確認。"""
        from scripts.skill_run_tracer import generate_skill_run_id

        result = generate_skill_run_id("skill", "sess", "2026-01-01T00:00:00Z")
        assert len(result) == 32

    def test_正常系_異なる入力で異なるID(self) -> None:
        """異なる入力で異なる ID が生成されることを確認。"""
        from scripts.skill_run_tracer import generate_skill_run_id

        id1 = generate_skill_run_id("skill-a", "session-1", "2026-03-18T00:00:00+00:00")
        id2 = generate_skill_run_id("skill-b", "session-1", "2026-03-18T00:00:00+00:00")
        assert id1 != id2


# ---------------------------------------------------------------------------
# build_start_cypher
# ---------------------------------------------------------------------------


class TestBuildStartCypher:
    """build_start_cypher のテスト。"""

    def test_正常系_MERGE文が生成される(self) -> None:
        """MERGE を含む Cypher が生成されることを確認。"""
        from scripts.skill_run_tracer import build_start_cypher

        query, params = build_start_cypher(
            skill_run_id="abc123",
            skill_name="test-skill",
            session_id="sess-1",
            start_at="2026-03-18T00:00:00+00:00",
            command_source="manual",
            input_summary=None,
        )
        assert "MERGE" in query
        assert "Memory" in query
        assert "SkillRun" in query
        assert params["skill_run_id"] == "abc123"
        assert params["skill_name"] == "test-skill"

    def test_正常系_command_sourceがパラメータに含まれる(self) -> None:
        """command_source がパラメータに含まれることを確認。"""
        from scripts.skill_run_tracer import build_start_cypher

        _, params = build_start_cypher(
            skill_run_id="abc123",
            skill_name="test-skill",
            session_id="sess-1",
            start_at="2026-03-18T00:00:00+00:00",
            command_source="topic-discovery",
            input_summary=None,
        )
        assert params["command_source"] == "topic-discovery"

    def test_正常系_input_summaryがパラメータに含まれる(self) -> None:
        """input_summary がパラメータに含まれることを確認。"""
        from scripts.skill_run_tracer import build_start_cypher

        _, params = build_start_cypher(
            skill_run_id="abc123",
            skill_name="test-skill",
            session_id="sess-1",
            start_at="2026-03-18T00:00:00+00:00",
            command_source=None,
            input_summary="test input",
        )
        assert params["input_summary"] == "test input"

    def test_正常系_statusがrunningに設定される(self) -> None:
        """status が 'running' に設定されることを確認。"""
        from scripts.skill_run_tracer import build_start_cypher

        _, params = build_start_cypher(
            skill_run_id="abc123",
            skill_name="test-skill",
            session_id="sess-1",
            start_at="2026-03-18T00:00:00+00:00",
            command_source=None,
            input_summary=None,
        )
        assert params["status"] == "running"


# ---------------------------------------------------------------------------
# build_complete_cypher
# ---------------------------------------------------------------------------


class TestBuildCompleteCypher:
    """build_complete_cypher のテスト。"""

    def test_正常系_MATCH文が生成される(self) -> None:
        """MATCH を含む Cypher が生成されることを確認。"""
        from scripts.skill_run_tracer import build_complete_cypher

        query, params = build_complete_cypher(
            skill_run_id="abc123",
            status="success",
            end_at="2026-03-18T00:01:00+00:00",
            duration_ms=60000,
            output_summary=None,
            error_message=None,
            error_type=None,
        )
        assert "MATCH" in query
        assert "SkillRun" in query
        assert params["skill_run_id"] == "abc123"
        assert params["status"] == "success"

    def test_正常系_duration_msがパラメータに含まれる(self) -> None:
        """duration_ms がパラメータに含まれることを確認。"""
        from scripts.skill_run_tracer import build_complete_cypher

        _, params = build_complete_cypher(
            skill_run_id="abc123",
            status="success",
            end_at="2026-03-18T00:01:00+00:00",
            duration_ms=5000,
            output_summary=None,
            error_message=None,
            error_type=None,
        )
        assert params["duration_ms"] == 5000

    def test_正常系_エラー情報がパラメータに含まれる(self) -> None:
        """error_message と error_type がパラメータに含まれることを確認。"""
        from scripts.skill_run_tracer import build_complete_cypher

        _, params = build_complete_cypher(
            skill_run_id="abc123",
            status="failure",
            end_at="2026-03-18T00:01:00+00:00",
            duration_ms=3000,
            output_summary=None,
            error_message="Connection timeout",
            error_type="TimeoutError",
        )
        assert params["error_message"] == "Connection timeout"
        assert params["error_type"] == "TimeoutError"

    def test_正常系_output_summaryがパラメータに含まれる(self) -> None:
        """output_summary がパラメータに含まれることを確認。"""
        from scripts.skill_run_tracer import build_complete_cypher

        _, params = build_complete_cypher(
            skill_run_id="abc123",
            status="success",
            end_at="2026-03-18T00:01:00+00:00",
            duration_ms=1000,
            output_summary="processed 10 items",
            error_message=None,
            error_type=None,
        )
        assert params["output_summary"] == "processed 10 items"


# ---------------------------------------------------------------------------
# build_feedback_cypher
# ---------------------------------------------------------------------------


class TestBuildFeedbackCypher:
    """build_feedback_cypher のテスト。"""

    def test_正常系_feedback_scoreがパラメータに含まれる(self) -> None:
        """feedback_score がパラメータに含まれることを確認。"""
        from scripts.skill_run_tracer import build_feedback_cypher

        _, params = build_feedback_cypher(
            skill_run_id="abc123",
            feedback_score=0.85,
        )
        assert params["feedback_score"] == 0.85
        assert params["skill_run_id"] == "abc123"

    def test_正常系_MATCH_SET文が生成される(self) -> None:
        """MATCH...SET を含む Cypher が生成されることを確認。"""
        from scripts.skill_run_tracer import build_feedback_cypher

        query, _ = build_feedback_cypher(
            skill_run_id="abc123",
            feedback_score=0.5,
        )
        assert "MATCH" in query
        assert "SET" in query
        assert "feedback_score" in query


# ---------------------------------------------------------------------------
# build_invoked_skill_cypher
# ---------------------------------------------------------------------------


class TestBuildInvokedSkillCypher:
    """build_invoked_skill_cypher のテスト。"""

    def test_正常系_INVOKED_SKILLリレーションが生成される(self) -> None:
        """INVOKED_SKILL リレーション作成の Cypher が生成されることを確認。"""
        from scripts.skill_run_tracer import build_invoked_skill_cypher

        query, params = build_invoked_skill_cypher(
            parent_id="parent123",
            child_id="child456",
        )
        assert "INVOKED_SKILL" in query
        assert params["parent_id"] == "parent123"
        assert params["child_id"] == "child456"

    def test_正常系_MERGE文が使用される(self) -> None:
        """冪等性のため MERGE が使用されることを確認。"""
        from scripts.skill_run_tracer import build_invoked_skill_cypher

        query, _ = build_invoked_skill_cypher(
            parent_id="p1",
            child_id="c1",
        )
        assert "MERGE" in query


# ---------------------------------------------------------------------------
# get_session_id
# ---------------------------------------------------------------------------


class TestGetSessionId:
    """get_session_id のテスト。"""

    def test_正常系_環境変数から取得(self) -> None:
        """CLAUDE_SESSION_ID 環境変数が設定されていればそれを返すことを確認。"""
        from scripts.skill_run_tracer import get_session_id

        with patch.dict("os.environ", {"CLAUDE_SESSION_ID": "env-session-123"}):
            result = get_session_id()
            assert result == "env-session-123"

    def test_正常系_環境変数未設定時はUUIDを返す(self) -> None:
        """CLAUDE_SESSION_ID が未設定の場合 UUID 形式の値を返すことを確認。"""
        from scripts.skill_run_tracer import get_session_id

        with patch.dict("os.environ", {}, clear=True):
            result = get_session_id()
            # UUID4 format: 8-4-4-4-12 hex characters
            assert len(result) == 36
            assert result.count("-") == 4


# ---------------------------------------------------------------------------
# compute_duration_ms
# ---------------------------------------------------------------------------


class TestComputeDurationMs:
    """compute_duration_ms のテスト。"""

    def test_正常系_開始と終了からミリ秒を計算(self) -> None:
        """start_at と end_at から duration_ms を計算できることを確認。"""
        from scripts.skill_run_tracer import compute_duration_ms

        start = "2026-03-18T00:00:00+00:00"
        end = "2026-03-18T00:01:00+00:00"
        result = compute_duration_ms(start, end)
        assert result == 60000

    def test_正常系_同時刻で0ミリ秒(self) -> None:
        """同じ時刻を指定した場合 0 を返すことを確認。"""
        from scripts.skill_run_tracer import compute_duration_ms

        ts = "2026-03-18T00:00:00+00:00"
        result = compute_duration_ms(ts, ts)
        assert result == 0

    def test_異常系_パース失敗時はNone(self) -> None:
        """パースに失敗した場合 None を返すことを確認。"""
        from scripts.skill_run_tracer import compute_duration_ms

        result = compute_duration_ms("invalid", "2026-03-18T00:00:00+00:00")
        assert result is None


# ---------------------------------------------------------------------------
# truncate_summary
# ---------------------------------------------------------------------------


class TestTruncateSummary:
    """truncate_summary のテスト。"""

    def test_正常系_500文字以下はそのまま(self) -> None:
        """500 文字以下の入力はそのまま返されることを確認。"""
        from scripts.skill_run_tracer import truncate_summary

        text = "short text"
        assert truncate_summary(text) == text

    def test_正常系_500文字超過は切り詰め(self) -> None:
        """500 文字を超える入力が切り詰められることを確認。"""
        from scripts.skill_run_tracer import truncate_summary

        text = "a" * 600
        result = truncate_summary(text)
        assert result is not None
        assert len(result) <= 503  # 500 + "..."
        assert result.endswith("...")

    def test_エッジケース_Noneで_None(self) -> None:
        """None を渡すと None が返されることを確認。"""
        from scripts.skill_run_tracer import truncate_summary

        assert truncate_summary(None) is None

    def test_エッジケース_空文字列はそのまま(self) -> None:
        """空文字列はそのまま返されることを確認。"""
        from scripts.skill_run_tracer import truncate_summary

        assert truncate_summary("") == ""


# ---------------------------------------------------------------------------
# execute_cypher (graceful degradation)
# ---------------------------------------------------------------------------


class TestExecuteCypher:
    """execute_cypher のテスト。"""

    def test_正常系_Neoドライバで実行される(self) -> None:
        """Neo4j ドライバが利用可能な場合 Cypher が実行されることを確認。"""
        from scripts.skill_run_tracer import execute_cypher

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = execute_cypher(mock_driver, "MATCH (n) RETURN n", {"key": "val"})

        assert result is True
        mock_session.run.assert_called_once_with("MATCH (n) RETURN n", key="val")

    def test_正常系_ドライバNoneで失敗(self) -> None:
        """ドライバが None の場合 False を返すことを確認。"""
        from scripts.skill_run_tracer import execute_cypher

        result = execute_cypher(None, "MATCH (n) RETURN n", {})
        assert result is False

    def test_異常系_実行時例外でFalse(self) -> None:
        """Cypher 実行中に例外が発生した場合 False を返すことを確認。"""
        from scripts.skill_run_tracer import execute_cypher

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = execute_cypher(mock_driver, "MATCH (n) RETURN n", {})
        assert result is False


# ---------------------------------------------------------------------------
# create_neo4j_driver (graceful degradation)
# ---------------------------------------------------------------------------


class TestCreateNeo4jDriver:
    """create_neo4j_driver のテスト。"""

    def test_正常系_パスワード未設定でNone(self) -> None:
        """パスワードが未設定の場合 None を返すことを確認。"""
        from scripts.skill_run_tracer import create_neo4j_driver

        with patch.dict("os.environ", {}, clear=True):
            result = create_neo4j_driver(
                uri="bolt://localhost:7688",
                user="neo4j",
                password=None,
            )
            assert result is None

    def test_異常系_接続失敗でNone(self) -> None:
        """Neo4j への接続に失敗した場合 None を返すことを確認。"""
        from scripts.skill_run_tracer import create_neo4j_driver

        with patch("scripts.skill_run_tracer.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_driver.verify_connectivity.side_effect = Exception(
                "Connection refused"
            )
            mock_gdb.driver.return_value = mock_driver

            result = create_neo4j_driver(
                uri="bolt://localhost:7688",
                user="neo4j",
                password="password",
            )
            assert result is None


# ---------------------------------------------------------------------------
# parse_feedback_file
# ---------------------------------------------------------------------------


class TestParseFeedbackFile:
    """parse_feedback_file のテスト。"""

    def test_正常系_JSONファイルから親子IDを取得(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """JSON ファイルから parent/child ID リストを取得できることを確認。"""
        import json

        from scripts.skill_run_tracer import parse_feedback_file

        feedback = {
            "invocations": [
                {"parent_id": "p1", "child_id": "c1"},
                {"parent_id": "p1", "child_id": "c2"},
            ]
        }
        path = tmp_path / "feedback.json"  # type: ignore[operator]
        path.write_text(json.dumps(feedback))

        result = parse_feedback_file(str(path))
        assert len(result) == 2
        assert result[0] == ("p1", "c1")
        assert result[1] == ("p1", "c2")

    def test_異常系_ファイル不存在で空リスト(self) -> None:
        """ファイルが存在しない場合空リストを返すことを確認。"""
        from scripts.skill_run_tracer import parse_feedback_file

        result = parse_feedback_file("/nonexistent/path.json")
        assert result == []

    def test_異常系_不正JSONで空リスト(self, tmp_path: pytest.TempPathFactory) -> None:
        """不正な JSON ファイルで空リストを返すことを確認。"""
        from scripts.skill_run_tracer import parse_feedback_file

        path = tmp_path / "bad.json"  # type: ignore[operator]
        path.write_text("not json")

        result = parse_feedback_file(str(path))
        assert result == []
