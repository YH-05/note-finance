"""Unit tests for auto_poster.py Wave 4 components.

Wave 4: リトライ戦略（tenacity）+ 結果サマリー出力。
- HTTP 429/500/502/503/504 エラー時に max 3回リトライ（5s→20s→80s）
- ConnectError / TimeoutError 時もリトライ
- HTTP 400/401/403 エラー時はリトライせず即座に失敗
- Instagram container FAILED 時はリトライせず即座に失敗
- 3回リトライ後も失敗した場合は次のスロット処理を継続
- main() の末尾で 投稿成功/スキップ/失敗 の集計サマリーが出力される
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# _is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    """_is_retryable_error のテスト。"""

    def test_正常系_HTTP429はリトライ対象である(self) -> None:
        """HTTP 429 は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(429, request=request)
        error = httpx.HTTPStatusError("429", request=request, response=response)
        assert _is_retryable_error(error) is True

    def test_正常系_HTTP500はリトライ対象である(self) -> None:
        """HTTP 500 は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("500", request=request, response=response)
        assert _is_retryable_error(error) is True

    def test_正常系_HTTP502はリトライ対象である(self) -> None:
        """HTTP 502 は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(502, request=request)
        error = httpx.HTTPStatusError("502", request=request, response=response)
        assert _is_retryable_error(error) is True

    def test_正常系_HTTP503はリトライ対象である(self) -> None:
        """HTTP 503 は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(503, request=request)
        error = httpx.HTTPStatusError("503", request=request, response=response)
        assert _is_retryable_error(error) is True

    def test_正常系_HTTP504はリトライ対象である(self) -> None:
        """HTTP 504 は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(504, request=request)
        error = httpx.HTTPStatusError("504", request=request, response=response)
        assert _is_retryable_error(error) is True

    def test_正常系_HTTP400はリトライ対象外である(self) -> None:
        """HTTP 400 は retryable でないと判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(400, request=request)
        error = httpx.HTTPStatusError("400", request=request, response=response)
        assert _is_retryable_error(error) is False

    def test_正常系_HTTP401はリトライ対象外である(self) -> None:
        """HTTP 401 は retryable でないと判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(401, request=request)
        error = httpx.HTTPStatusError("401", request=request, response=response)
        assert _is_retryable_error(error) is False

    def test_正常系_HTTP403はリトライ対象外である(self) -> None:
        """HTTP 403 は retryable でないと判定される。"""
        from scripts.auto_poster import _is_retryable_error

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(403, request=request)
        error = httpx.HTTPStatusError("403", request=request, response=response)
        assert _is_retryable_error(error) is False

    def test_正常系_ConnectErrorはリトライ対象である(self) -> None:
        """httpx.ConnectError は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        error = httpx.ConnectError("Connection refused")
        assert _is_retryable_error(error) is True

    def test_正常系_TimeoutExceptionはリトライ対象である(self) -> None:
        """httpx.TimeoutException は retryable と判定される。"""
        from scripts.auto_poster import _is_retryable_error

        error = httpx.TimeoutException("Timeout")
        assert _is_retryable_error(error) is True

    def test_正常系_RuntimeErrorはリトライ対象外である(self) -> None:
        """RuntimeError（container FAILED 等）は retryable でないと判定される。"""
        from scripts.auto_poster import _is_retryable_error

        error = RuntimeError("container FAILED")
        assert _is_retryable_error(error) is False

    def test_正常系_一般的な例外はリトライ対象外である(self) -> None:
        """一般的な Exception は retryable でないと判定される。"""
        from scripts.auto_poster import _is_retryable_error

        error = ValueError("bad value")
        assert _is_retryable_error(error) is False


# ---------------------------------------------------------------------------
# AccountPoster リトライ動作
# ---------------------------------------------------------------------------


class TestAccountPosterRetry:
    """AccountPoster のリトライ動作テスト。"""

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_HTTP429で3回リトライして成功する(
        self, mock_threads_class: Any
    ) -> None:
        """HTTP 429 エラー後にリトライし、3回目に成功することを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import AccountPoster

        request = httpx.Request("POST", "https://example.com")
        response_429 = httpx.Response(429, request=request)
        error_429 = httpx.HTTPStatusError("429", request=request, response=response_429)

        success_result = PostResult(
            platform="threads",
            media_id="t-success",
            permalink="https://www.threads.com/@mitsuki/post/SUCCESS",
        )

        mock_threads = MagicMock()
        # 1回目と2回目は失敗、3回目は成功
        mock_threads.post_text.side_effect = [error_429, error_429, success_result]
        mock_threads_class.return_value = mock_threads

        poster = AccountPoster(account="mitsuki")
        content = "テスト投稿テキスト"

        result = poster.post(content)

        assert result.media_id == "t-success"
        assert mock_threads.post_text.call_count == 3

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_HTTP500で最大3回リトライ後に例外が伝播する(
        self, mock_threads_class: Any
    ) -> None:
        """HTTP 500 エラーが3回続いた後に例外が再 raise されることを確認。"""
        from scripts.auto_poster import AccountPoster

        request = httpx.Request("POST", "https://example.com")
        response_500 = httpx.Response(500, request=request)
        error_500 = httpx.HTTPStatusError("500", request=request, response=response_500)

        mock_threads = MagicMock()
        mock_threads.post_text.side_effect = [error_500, error_500, error_500]
        mock_threads_class.return_value = mock_threads

        poster = AccountPoster(account="mitsuki")
        content = "テスト投稿テキスト"

        with pytest.raises(httpx.HTTPStatusError):
            poster.post(content)

        # 3回試みたことを確認
        assert mock_threads.post_text.call_count == 3

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_HTTP401はリトライせず即座に失敗する(
        self, mock_threads_class: Any
    ) -> None:
        """HTTP 401 エラーはリトライされずに即座に例外が伝播することを確認。"""
        from scripts.auto_poster import AccountPoster

        request = httpx.Request("POST", "https://example.com")
        response_401 = httpx.Response(401, request=request)
        error_401 = httpx.HTTPStatusError("401", request=request, response=response_401)

        mock_threads = MagicMock()
        mock_threads.post_text.side_effect = error_401
        mock_threads_class.return_value = mock_threads

        poster = AccountPoster(account="mitsuki")
        content = "テスト投稿テキスト"

        with pytest.raises(httpx.HTTPStatusError):
            poster.post(content)

        # リトライなし（1回のみ）
        assert mock_threads.post_text.call_count == 1

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_ConnectErrorでリトライする(self, mock_threads_class: Any) -> None:
        """httpx.ConnectError でリトライが実行されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import AccountPoster

        connect_error = httpx.ConnectError("Connection refused")
        success_result = PostResult(
            platform="threads",
            media_id="t-connect-ok",
            permalink="https://www.threads.com/@mitsuki/post/CONNECT_OK",
        )

        mock_threads = MagicMock()
        mock_threads.post_text.side_effect = [connect_error, success_result]
        mock_threads_class.return_value = mock_threads

        poster = AccountPoster(account="mitsuki")
        result = poster.post("テスト")

        assert result.media_id == "t-connect-ok"
        assert mock_threads.post_text.call_count == 2


# ---------------------------------------------------------------------------
# _execute_post: 3回リトライ後も失敗した場合は次スロット処理を継続
# ---------------------------------------------------------------------------


class TestExecutePostRetryBehavior:
    """_execute_post のリトライ後の継続動作テスト。"""

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_3回リトライ後失敗でも例外を伝播させない(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: "Path",
    ) -> None:
        """AccountPoster が3回失敗しても _execute_post は例外を発生させずに終了する。"""
        from scripts.auto_poster import StateUpdater, _execute_post

        request = httpx.Request("POST", "https://example.com")
        response_500 = httpx.Response(500, request=request)
        error_500 = httpx.HTTPStatusError("500", request=request, response=response_500)

        mock_threads = MagicMock()
        mock_threads.post.side_effect = error_500
        mock_account_poster_class.return_value = mock_threads

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [{"slot": "朝", "category": "有益"}],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト。", encoding="utf-8")

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="mitsuki",
        )

        # 例外が伝播しないことを確認
        _execute_post(
            account="mitsuki",
            slot_name="朝",
            today_str="2026-03-27",
            slot_file=slot_dir / "threads_post.md",
            updater=updater,
            fresh_meta=meta,
        )


# ---------------------------------------------------------------------------
# PostingSummary
# ---------------------------------------------------------------------------


class TestPostingSummary:
    """PostingSummary のテスト。"""

    def test_正常系_インスタンスを生成できる(self) -> None:
        """PostingSummary が生成できることを確認。"""
        from scripts.auto_poster import PostingSummary

        summary = PostingSummary()
        assert summary is not None

    def test_正常系_初期値がゼロである(self) -> None:
        """PostingSummary の初期値が全てゼロであることを確認。"""
        from scripts.auto_poster import PostingSummary

        summary = PostingSummary()
        assert summary.posted == 0
        assert summary.skipped == 0
        assert summary.failed == 0

    def test_正常系_posted_をインクリメントできる(self) -> None:
        """posted フィールドをインクリメントできることを確認。"""
        from scripts.auto_poster import PostingSummary

        summary = PostingSummary()
        summary.posted += 1
        assert summary.posted == 1

    def test_正常系_skipped_をインクリメントできる(self) -> None:
        """skipped フィールドをインクリメントできることを確認。"""
        from scripts.auto_poster import PostingSummary

        summary = PostingSummary()
        summary.skipped += 1
        assert summary.skipped == 1

    def test_正常系_failed_をインクリメントできる(self) -> None:
        """failed フィールドをインクリメントできることを確認。"""
        from scripts.auto_poster import PostingSummary

        summary = PostingSummary()
        summary.failed += 1
        assert summary.failed == 1


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------


class TestPrintSummary:
    """print_summary のテスト。"""

    def test_正常系_サマリーが正しい形式で出力される(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """print_summary がアカウント別のサマリーを正しい形式で出力することを確認。"""
        from scripts.auto_poster import PostingSummary, print_summary

        summaries = {
            "mitsuki": PostingSummary(posted=2, skipped=1, failed=0),
            "career_sister": PostingSummary(posted=1, skipped=0, failed=0),
        }

        print_summary(summaries)

        captured = capsys.readouterr()
        output = captured.out

        # ヘッダー確認
        assert "=== Auto Poster Summary ===" in output

        # mitsuki のサマリー確認
        assert "mitsuki" in output
        assert "posted: 2 slots" in output
        assert "skipped (already posted): 1 slots" in output

        # career_sister のサマリー確認
        assert "career_sister" in output

    def test_正常系_失敗ありのサマリーが出力される(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """failed > 0 のケースでサマリーが正しく出力されることを確認。"""
        from scripts.auto_poster import PostingSummary, print_summary

        summaries = {
            "mitsuki": PostingSummary(posted=0, skipped=0, failed=2),
        }

        print_summary(summaries)

        captured = capsys.readouterr()
        output = captured.out

        assert "failed: 2" in output

    def test_正常系_空のサマリーでもエラーなく出力される(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """空の summaries dict でもエラーが発生しないことを確認。"""
        from scripts.auto_poster import print_summary

        print_summary({})

        captured = capsys.readouterr()
        assert "=== Auto Poster Summary ===" in captured.out


# ---------------------------------------------------------------------------
# main() のサマリー出力統合テスト
# ---------------------------------------------------------------------------


class TestMainSummaryOutput:
    """main() のサマリー出力統合テスト。"""

    @patch("scripts.auto_poster.print_summary")
    @patch("scripts.auto_poster._process_account")
    def test_正常系_main終了時にprint_summaryが呼ばれる(
        self,
        mock_process_account: Any,
        mock_print_summary: Any,
    ) -> None:
        """main() が終了時に print_summary を呼ぶことを確認。"""
        from scripts.auto_poster import main

        main(["--dry-run", "--account", "mitsuki"])

        mock_print_summary.assert_called_once()

    @patch("scripts.auto_poster.print_summary")
    @patch("scripts.auto_poster._process_account")
    def test_正常系_全アカウント処理後にprint_summaryが呼ばれる(
        self,
        mock_process_account: Any,
        mock_print_summary: Any,
    ) -> None:
        """全アカウント処理後に print_summary が一度だけ呼ばれることを確認。"""
        from scripts.auto_poster import main

        main(["--dry-run"])

        mock_print_summary.assert_called_once()


# ---------------------------------------------------------------------------
# _run_post_slot のエッジケース
# ---------------------------------------------------------------------------


class TestRunPostSlotEdgeCases:
    """_run_post_slot のエッジケーステスト。"""

    def test_正常系_fresh_metaがNoneのときsummary_failedがインクリメントされる(
        self, tmp_path: "Path"
    ) -> None:
        """reader.load() が None を返す場合、summary.failed が +1 され早期リターンする。"""
        from unittest.mock import patch

        from scripts.auto_poster import (
            AutoPosterConfig,
            DraftReader,
            PostingSummary,
            _run_post_slot,
        )

        creator_root = tmp_path / "creator" / "mitsuki"
        creator_root.mkdir(parents=True)
        drafts_root = creator_root / "drafts"
        drafts_root.mkdir()

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [{"slot": "朝", "category": "有益"}],
                }
            ],
        }
        week_dir = drafts_root / "week_2026-03-24"
        week_dir.mkdir()
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        config = AutoPosterConfig(dry_run=False)
        reader = DraftReader(drafts_root=drafts_root, account="mitsuki")

        # slot_file は存在するものとし、load() だけ None を返す
        slot_file = week_dir / "slot_1_morning" / "threads_post.md"
        slot_file.parent.mkdir(parents=True)
        slot_file.write_text("朝の投稿。", encoding="utf-8")

        with (
            patch.object(reader, "get_slot_file", return_value=slot_file),
            patch.object(reader, "load", return_value=None),
        ):
            summary = PostingSummary()
            _run_post_slot(
                account="mitsuki",
                config=config,
                reader=reader,
                creator_root=creator_root,
                meta=meta,
                today_str="2026-03-27",
                slot_name="朝",
                summary=summary,
            )

        # meta 再読み込みが失敗 → failed が +1
        assert summary.failed == 1
        assert summary.posted == 0
        assert summary.skipped == 0
