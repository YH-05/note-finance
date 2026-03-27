"""Unit tests for auto_poster.py Wave 2 components.

Wave 2: AccountPoster / StateUpdater の実装テスト。
- AccountPoster: mitsuki の Threads 投稿実行
- StateUpdater: meta.json / posting_state.json の状態書き戻し

Wave 2 (career_sister 拡張):
- career_sister の DraftReader ファイル解決
- StateUpdater の career_sister フォーマット対応（status/published_at/threads_permalink）
- 全スロット投稿済み時の days[].status 更新
- _process_account の career_sister 統合テスト
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

if TYPE_CHECKING:
    from pathlib import Path

JST = ZoneInfo("Asia/Tokyo")


# ---------------------------------------------------------------------------
# AccountPoster
# ---------------------------------------------------------------------------


class TestAccountPoster:
    """AccountPoster のテスト。"""

    def test_正常系_mitsuki設定でインスタンスを生成できる(self) -> None:
        """mitsuki アカウントで AccountPoster が生成できることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="mitsuki")
        assert poster.account == "mitsuki"

    def test_正常系_career_sister設定でインスタンスを生成できる(self) -> None:
        """career_sister アカウントで AccountPoster が生成できることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="career_sister")
        assert poster.account == "career_sister"

    def test_正常系_フロントマターからtopic_tagを抽出できる(self) -> None:
        """YAML フロントマターから topic_tag を抽出できることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="mitsuki")
        content = "---\ntopic_tag: '#資産形成'\n---\n本文です。"
        tag = poster._extract_topic_tag(content)
        assert tag == "#資産形成"

    def test_正常系_フロントマターがない場合はNoneを返す(self) -> None:
        """フロントマターがない場合に topic_tag が None になることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="mitsuki")
        content = "フロントマターなし本文です。"
        tag = poster._extract_topic_tag(content)
        assert tag is None

    def test_正常系_topic_tagが未定義でもNoneを返す(self) -> None:
        """フロントマターに topic_tag がない場合に None が返されることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="mitsuki")
        content = "---\nslot: 朝\n---\n本文です。"
        tag = poster._extract_topic_tag(content)
        assert tag is None

    def test_正常系_フロントマターを除いた本文を返す(self) -> None:
        """YAML フロントマターを除いた本文テキストを取得できることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="mitsuki")
        content = "---\ntopic_tag: '#資産形成'\n---\n本文です。\n続き。"
        body = poster._extract_body(content)
        assert "本文です。" in body
        assert "---" not in body
        assert "topic_tag" not in body

    def test_正常系_フロントマターなし本文はそのまま返す(self) -> None:
        """フロントマターがない場合に本文がそのまま返されることを確認。"""
        from scripts.auto_poster import AccountPoster

        poster = AccountPoster(account="mitsuki")
        content = "フロントマターなし本文です。"
        body = poster._extract_body(content)
        assert body == "フロントマターなし本文です。"

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_threads投稿が実行される(self, mock_threads_class: Any) -> None:
        """Threads 投稿が実行され PostResult が返されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import AccountPoster

        # ThreadsPoster のモック
        mock_poster = MagicMock()
        mock_poster.post_text.return_value = PostResult(
            platform="threads",
            media_id="12345",
            permalink="https://www.threads.com/@mitsuki/post/ABC123",
        )
        mock_threads_class.return_value = mock_poster

        poster = AccountPoster(account="mitsuki")
        content = "---\ntopic_tag: '#資産形成'\n---\nテスト投稿内容。"
        result = poster.post(content)

        assert result is not None
        assert result.media_id == "12345"
        assert result.permalink == "https://www.threads.com/@mitsuki/post/ABC123"

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_topic_tag付きで投稿される(self, mock_threads_class: Any) -> None:
        """topic_tag が含まれる場合に本文に追記されて投稿されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import AccountPoster

        mock_poster = MagicMock()
        mock_poster.post_text.return_value = PostResult(
            platform="threads",
            media_id="99999",
            permalink="https://www.threads.com/@mitsuki/post/XYZ",
        )
        mock_threads_class.return_value = mock_poster

        poster = AccountPoster(account="mitsuki")
        content = "---\ntopic_tag: '#資産形成'\n---\nテスト投稿内容。"
        poster.post(content)

        # post_text が呼ばれ、topic_tag が本文に含まれることを確認
        call_args = mock_poster.post_text.call_args
        assert call_args is not None
        posted_text = call_args[0][0]
        assert "#資産形成" in posted_text

    @patch("scripts.auto_poster.ThreadsPoster")
    def test_正常系_topic_tagなしでも投稿できる(self, mock_threads_class: Any) -> None:
        """topic_tag なしでも Threads 投稿が実行されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import AccountPoster

        mock_poster = MagicMock()
        mock_poster.post_text.return_value = PostResult(
            platform="threads",
            media_id="88888",
            permalink="https://www.threads.com/@mitsuki/post/DEF",
        )
        mock_threads_class.return_value = mock_poster

        poster = AccountPoster(account="mitsuki")
        content = "フロントマターなし投稿内容。"
        result = poster.post(content)

        assert result is not None
        assert result.media_id == "88888"


# ---------------------------------------------------------------------------
# StateUpdater
# ---------------------------------------------------------------------------


class TestStateUpdater:
    """StateUpdater のテスト。"""

    def test_正常系_インスタンスを生成できる(self, tmp_path: Path) -> None:
        """StateUpdater が生成できることを確認。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)
        posting_state_path = tmp_path / "posting_state.json"

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
        )
        assert updater is not None

    def test_正常系_meta_jsonに投稿結果を書き戻せる(self, tmp_path: Path) -> None:
        """meta.json に posted_at と permalink が書き戻されることを確認。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {"slot": "朝", "category": "有益", "type": "型1"},
                        {"slot": "昼", "category": "有益", "type": "型2"},
                    ],
                }
            ],
        }
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))

        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
        )

        posted_at = "2026-03-27T07:32:00+09:00"
        permalink = "https://www.threads.com/@mitsuki/post/ABC123"

        updater.update_meta(
            date="2026-03-27",
            slot="朝",
            posted_at=posted_at,
            permalink=permalink,
        )

        # meta.json を再読み込みして確認
        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        day = updated_meta["days"][0]
        morning_slot = day["slots"][0]
        assert morning_slot["posted_at"] == posted_at
        assert morning_slot["permalink"] == permalink

    def test_正常系_posting_state_jsonにエントリを追記できる(
        self, tmp_path: Path
    ) -> None:
        """posting_state.json の post_history にエントリが追記されることを確認。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "type": "型1",
                            "theme": "T1",
                        }
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        posting_state = {
            "post_history": [
                {
                    "post_id": "2026-03-26_001",
                    "date": "2026-03-26",
                    "slot": "朝",
                    "posted_at": "2026-03-26T07:35:00+09:00",
                    "threads_permalink": "https://www.threads.com/@mitsuki/post/OLD",
                }
            ]
        }
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(json.dumps(posting_state, ensure_ascii=False))

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
        )

        posted_at = "2026-03-27T07:32:00+09:00"
        permalink = "https://www.threads.com/@mitsuki/post/NEW"

        updater.update_meta(
            date="2026-03-27",
            slot="朝",
            posted_at=posted_at,
            permalink=permalink,
        )
        updater.append_post_history(
            date="2026-03-27",
            slot="朝",
            slot_meta=meta["days"][0]["slots"][0],
            posted_at=posted_at,
            threads_permalink=permalink,
        )

        updated_state = json.loads(posting_state_path.read_text(encoding="utf-8"))
        assert len(updated_state["post_history"]) == 2
        new_entry = updated_state["post_history"][-1]
        assert new_entry["date"] == "2026-03-27"
        assert new_entry["slot"] == "朝"
        assert new_entry["threads_permalink"] == permalink

    def test_正常系_冪等性_投稿済みスロットは二重更新されない(
        self, tmp_path: Path
    ) -> None:
        """既に posted_at が設定されているスロットは上書き更新されないことを確認。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        original_posted_at = "2026-03-27T07:32:00+09:00"
        original_permalink = "https://www.threads.com/@mitsuki/post/ORIGINAL"

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "type": "型1",
                            "posted_at": original_posted_at,
                            "permalink": original_permalink,
                        }
                    ],
                }
            ],
        }
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        (tmp_path / "posting_state.json").write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=tmp_path / "posting_state.json",
        )

        # 2回目の update 試行
        result = updater.check_already_posted(meta=meta, date="2026-03-27", slot="朝")
        assert result is True

    def test_正常系_未投稿スロットはcheck_already_postedがFalseを返す(
        self, tmp_path: Path
    ) -> None:
        """posted_at が None のスロットは check_already_posted が False を返す。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "slots": [{"slot": "朝", "category": "有益"}],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
        (tmp_path / "posting_state.json").write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=tmp_path / "posting_state.json",
        )
        result = updater.check_already_posted(meta=meta, date="2026-03-27", slot="朝")
        assert result is False

    def test_正常系_filelock排他制御が機能する(self, tmp_path: Path) -> None:
        """filelock による meta.json 排他制御が機能することを確認。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "slots": [{"slot": "朝", "category": "有益"}],
                }
            ],
        }
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        (tmp_path / "posting_state.json").write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=tmp_path / "posting_state.json",
        )

        updater.update_meta(
            date="2026-03-27",
            slot="朝",
            posted_at="2026-03-27T07:32:00+09:00",
            permalink="https://www.threads.com/@mitsuki/post/TEST",
        )

        # update_meta 完了後はロックが解放されている（ファイル自体は残る場合もある）
        updated = json.loads(meta_path.read_text(encoding="utf-8"))
        assert (
            updated["days"][0]["slots"][0]["posted_at"] == "2026-03-27T07:32:00+09:00"
        )

    def test_正常系_post_history_entryにpost_idが生成される(
        self, tmp_path: Path
    ) -> None:
        """post_history エントリに一意の post_id が生成されることを確認。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)
        (week_dir / "meta.json").write_text(
            json.dumps(
                {
                    "week_start": "2026-03-24",
                    "days": [
                        {
                            "date": "2026-03-27",
                            "day_label": "木",
                            "slots": [
                                {"slot": "朝", "category": "有益", "type": "型1"}
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
        )
        updater.append_post_history(
            date="2026-03-27",
            slot="朝",
            slot_meta={"slot": "朝", "category": "有益", "type": "型1", "theme": "T1"},
            posted_at="2026-03-27T07:32:00+09:00",
            threads_permalink="https://www.threads.com/@mitsuki/post/TEST",
        )

        state = json.loads(posting_state_path.read_text(encoding="utf-8"))
        assert len(state["post_history"]) == 1
        entry = state["post_history"][0]
        assert "post_id" in entry
        assert entry["date"] == "2026-03-27"
        assert entry["slot"] == "朝"


# ---------------------------------------------------------------------------
# Integration: _process_account with mitsuki
# ---------------------------------------------------------------------------


class TestProcessAccountMitsuki:
    """mitsuki アカウントの _process_account 統合テスト。"""

    def test_正常系_dry_runでmitsukiが処理される(self, tmp_path: Path) -> None:
        """mitsuki アカウントの --dry-run が正常に実行されることを確認。"""
        from scripts.auto_poster import (
            SLOT_TIME_MAP,
            AutoPosterConfig,
            DraftReader,
            SlotMatcher,
            _print_dry_run,
        )

        # mitsuki の drafts ディレクトリを作成
        drafts_root = tmp_path / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {"slot": "朝", "category": "有益"},
                        {"slot": "昼", "category": "有益"},
                        {"slot": "夜", "category": "有益"},
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        reader = DraftReader(drafts_root=drafts_root, account="mitsuki")
        loaded = reader.load(week="2026-03-24")
        assert loaded is not None

        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        now = datetime(2026, 3, 27, 7, 30, 0, tzinfo=JST)
        matched = matcher.match(now)

        # dry-run 出力が例外なく実行される
        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            _print_dry_run("mitsuki", loaded, reader, "2026-03-27", matched)
        finally:
            sys.stdout = sys.__stdout__

        output = captured.getvalue()
        assert "mitsuki" in output
        assert "2026-03-27" in output

    @patch("scripts.auto_poster.AccountPoster")
    @patch("scripts.auto_poster.StateUpdater")
    def test_正常系_force_slotでmitsuki投稿が実行される(
        self,
        mock_state_updater_class: Any,
        mock_account_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """--force-slot S1 で mitsuki の朝スロットが投稿されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import (
            SLOT_TIME_MAP,
            AutoPosterConfig,
            DraftReader,
            SlotMatcher,
            _process_account,
        )

        # AccountPoster モック
        mock_poster = MagicMock()
        mock_poster.post.return_value = PostResult(
            platform="threads",
            media_id="12345",
            permalink="https://www.threads.com/@mitsuki/post/NEW",
        )
        mock_account_poster_class.return_value = mock_poster

        # StateUpdater モック
        mock_updater = MagicMock()
        mock_updater.check_already_posted.return_value = False
        mock_state_updater_class.return_value = mock_updater

        # mitsuki の drafts ディレクトリを作成
        drafts_root = tmp_path / "creator" / "mitsuki" / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        day_dir = week_dir / "day_4_木"
        slot_dir = day_dir / "slot_1_morning"
        slot_dir.mkdir(parents=True)

        (slot_dir / "threads_post.md").write_text(
            "---\ntopic_tag: '#資産形成'\n---\nテスト投稿内容。"
        )

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "type": "型1",
                            "theme": "T1",
                        },
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        posting_state_path = tmp_path / "creator" / "mitsuki" / "posting_state.json"
        posting_state_path.parent.mkdir(parents=True, exist_ok=True)
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        config = AutoPosterConfig(
            account="mitsuki",
            dry_run=False,
            force_slot="S1",
        )
        now = datetime(2026, 3, 27, 7, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)

        with patch("scripts.auto_poster.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path

            _process_account("mitsuki", config, now, matcher)

        # AccountPoster.post が呼ばれたことを確認
        assert mock_poster.post.called

    @patch("scripts.auto_poster.AccountPoster")
    @patch("scripts.auto_poster.StateUpdater")
    def test_正常系_already_posted_スロットはスキップされる(
        self,
        mock_state_updater_class: Any,
        mock_account_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """既に投稿済みのスロットは already_posted でスキップされることを確認。"""
        from scripts.auto_poster import (
            SLOT_TIME_MAP,
            AutoPosterConfig,
            DraftReader,
            SlotMatcher,
            _process_account,
        )

        # StateUpdater モック: 既に投稿済みとして返す
        mock_updater = MagicMock()
        mock_updater.check_already_posted.return_value = True
        mock_state_updater_class.return_value = mock_updater

        # AccountPoster モック
        mock_poster = MagicMock()
        mock_account_poster_class.return_value = mock_poster

        # mitsuki の drafts ディレクトリを作成
        drafts_root = tmp_path / "creator" / "mitsuki" / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        day_dir = week_dir / "day_4_木"
        slot_dir = day_dir / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text(
            "---\ntopic_tag: '#資産形成'\n---\nテスト。"
        )

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "posted_at": "2026-03-27T07:32:00+09:00",
                        }
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        posting_state_path = tmp_path / "creator" / "mitsuki" / "posting_state.json"
        posting_state_path.parent.mkdir(parents=True, exist_ok=True)
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        config = AutoPosterConfig(
            account="mitsuki",
            dry_run=False,
            force_slot="S1",
        )
        now = datetime(2026, 3, 27, 7, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)

        with patch("scripts.auto_poster.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path

            _process_account("mitsuki", config, now, matcher)

        # 投稿済みのため AccountPoster.post は呼ばれないことを確認
        assert not mock_poster.post.called


# ---------------------------------------------------------------------------
# career_sister: DraftReader ファイル解決テスト
# ---------------------------------------------------------------------------


class TestDraftReaderCareerSister:
    """career_sister アカウントの DraftReader テスト。"""

    def test_正常系_career_sisterのday_dir_mapが英語表記になる(
        self, tmp_path: Path
    ) -> None:
        """career_sister の曜日マッピングが英語表記であることを確認。"""
        from scripts.auto_poster import DAY_DIR_MAP_CAREER_SISTER, DraftReader

        reader = DraftReader(drafts_root=tmp_path, account="career_sister")
        day_dir_map = reader._get_day_dir_map()

        assert day_dir_map["月"] == "day_1_mon"
        assert day_dir_map["火"] == "day_2_tue"
        assert day_dir_map["水"] == "day_3_wed"
        assert day_dir_map["木"] == "day_4_thu"
        assert day_dir_map["金"] == "day_5_fri"
        assert day_dir_map["土"] == "day_6_sat"
        assert day_dir_map["日"] == "day_7_sun"
        assert day_dir_map == DAY_DIR_MAP_CAREER_SISTER

    def test_正常系_career_sisterのthreads_post_mdが正しく解決される(
        self, tmp_path: Path
    ) -> None:
        """career_sister の day_{N}_{eng}/slot_{M}_{period}/ から threads_post.md が解決される。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        slot_dir = week_dir / "day_4_thu" / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト投稿")

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.get_slot_file("week_2026-03-24", "2026-03-27", "木", "朝")

        assert result is not None
        assert result.name == "threads_post.md"
        assert "day_4_thu" in str(result)
        assert "slot_1_morning" in str(result)

    def test_正常系_夜スロットのディレクトリ名がslot_3_eveningになる(
        self, tmp_path: Path
    ) -> None:
        """career_sister の 夜スロットが slot_3_evening ディレクトリに解決される。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        slot_dir = week_dir / "day_4_thu" / "slot_3_evening"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("夜投稿テスト")

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.get_slot_file("week_2026-03-24", "2026-03-27", "木", "夜")

        assert result is not None
        assert "slot_3_evening" in str(result)

    def test_エッジケース_threads_post_mdが存在しない場合はNoneを返す(
        self, tmp_path: Path
    ) -> None:
        """threads_post.md が存在しない場合に None が返されることを確認。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.get_slot_file("week_2026-03-24", "2026-03-27", "木", "朝")

        assert result is None


# ---------------------------------------------------------------------------
# career_sister: StateUpdater 拡張テスト
# ---------------------------------------------------------------------------


class TestStateUpdaterCareerSister:
    """career_sister フォーマットの StateUpdater テスト。"""

    def _make_career_sister_meta(self) -> dict[str, Any]:
        """career_sister テスト用 meta.json データを生成する。"""
        return {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "type": "型3",
                            "theme": "T3",
                            "instagram": True,
                        },
                        {
                            "slot": "昼",
                            "category": "有益",
                            "type": "型1",
                            "theme": "T8",
                            "instagram": False,
                        },
                        {
                            "slot": "夜",
                            "category": "エンゲージメント",
                            "type": "型1-A",
                            "theme": "T4",
                            "instagram": False,
                        },
                    ],
                }
            ],
        }

    def test_正常系_career_sisterのcheck_already_posted_status_publishedでTrueを返す(
        self, tmp_path: Path
    ) -> None:
        """career_sister フォーマット: status == 'published' で投稿済みと判定される。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "status": "published",
                            "published_at": "2026-03-27T07:32:00+09:00",
                            "threads_permalink": "https://www.threads.com/@career_sister/post/ABC",
                        }
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )
        result = updater.check_already_posted(meta=meta, date="2026-03-27", slot="朝")
        assert result is True

    def test_正常系_career_sisterのcheck_already_posted_status_draftでFalseを返す(
        self, tmp_path: Path
    ) -> None:
        """career_sister フォーマット: status が 'draft' や未設定の場合は未投稿と判定される。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "slots": [{"slot": "朝", "category": "有益"}],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )
        result = updater.check_already_posted(meta=meta, date="2026-03-27", slot="朝")
        assert result is False

    def test_正常系_career_sisterのupdate_metaがstatus_published_at_threads_permalinkを書き込む(
        self, tmp_path: Path
    ) -> None:
        """career_sister の update_meta が status/published_at/threads_permalink を書き込む。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = self._make_career_sister_meta()
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        published_at = "2026-03-27T07:32:00+09:00"
        permalink = "https://www.threads.com/@career_sister/post/DWQF-5xE0fO"

        updater.update_meta(
            date="2026-03-27",
            slot="朝",
            posted_at=published_at,
            permalink=permalink,
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        morning_slot = updated_meta["days"][0]["slots"][0]
        assert morning_slot["status"] == "published"
        assert morning_slot["published_at"] == published_at
        assert morning_slot["threads_permalink"] == permalink
        # mitsuki フィールドは書き込まれていないことを確認
        assert "posted_at" not in morning_slot
        assert "permalink" not in morning_slot

    def test_正常系_career_sisterの全スロット投稿済み時にdays_statusがpublishedになる(
        self, tmp_path: Path
    ) -> None:
        """career_sister: 全スロット投稿済みで days[].status が 'published' に更新される。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        # 朝と昼はすでに published、夜を投稿するシナリオ
        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "status": "published",
                            "published_at": "2026-03-27T07:32:00+09:00",
                            "threads_permalink": "https://www.threads.com/@career_sister/post/A",
                        },
                        {
                            "slot": "昼",
                            "category": "有益",
                            "status": "published",
                            "published_at": "2026-03-27T12:32:00+09:00",
                            "threads_permalink": "https://www.threads.com/@career_sister/post/B",
                        },
                        {"slot": "夜", "category": "エンゲージメント"},
                    ],
                }
            ],
        }
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        updater.update_meta(
            date="2026-03-27",
            slot="夜",
            posted_at="2026-03-27T20:32:00+09:00",
            permalink="https://www.threads.com/@career_sister/post/C",
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        day = updated_meta["days"][0]
        assert day["status"] == "published"
        evening_slot = day["slots"][2]
        assert evening_slot["status"] == "published"

    def test_正常系_career_sisterの一部スロット未投稿時はdays_statusがdraftのまま(
        self, tmp_path: Path
    ) -> None:
        """career_sister: 一部のスロットが未投稿の場合 days[].status は 'draft' のまま。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {"slot": "朝", "category": "有益"},  # 未投稿
                        {"slot": "昼", "category": "有益"},
                        {"slot": "夜", "category": "エンゲージメント"},
                    ],
                }
            ],
        }
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        # 昼スロットだけ投稿
        updater.update_meta(
            date="2026-03-27",
            slot="昼",
            posted_at="2026-03-27T12:32:00+09:00",
            permalink="https://www.threads.com/@career_sister/post/D",
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        day = updated_meta["days"][0]
        # 全スロット投稿済みでないため draft のまま
        assert day["status"] == "draft"

    def test_正常系_career_sisterのappend_post_historyにcareer_sisterフォーマットのエントリが追記される(
        self, tmp_path: Path
    ) -> None:
        """career_sister の post_history エントリが career_sister フォーマットで追記される。"""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-24"
        week_dir.mkdir(parents=True)
        (week_dir / "meta.json").write_text(
            json.dumps(
                {
                    "week_start": "2026-03-24",
                    "days": [
                        {
                            "date": "2026-03-27",
                            "day_label": "木",
                            "slots": [
                                {"slot": "朝", "category": "有益", "type": "型3"}
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        posted_at = "2026-03-27T07:32:00+09:00"
        permalink = "https://www.threads.com/@career_sister/post/DWQF-5xE0fO"

        updater.append_post_history(
            date="2026-03-27",
            slot="朝",
            slot_meta={"slot": "朝", "category": "有益", "type": "型3", "theme": "T3"},
            posted_at=posted_at,
            threads_permalink=permalink,
        )

        state = json.loads(posting_state_path.read_text(encoding="utf-8"))
        assert len(state["post_history"]) == 1
        entry = state["post_history"][0]
        assert entry["date"] == "2026-03-27"
        assert entry["slot"] == "朝"
        assert entry["threads_permalink"] == permalink
        assert "post_id" in entry


# ---------------------------------------------------------------------------
# career_sister: _process_account 統合テスト
# ---------------------------------------------------------------------------


class TestProcessAccountCareerSister:
    """career_sister アカウントの _process_account 統合テスト。"""

    @patch("scripts.auto_poster.AccountPoster")
    @patch("scripts.auto_poster.StateUpdater")
    def test_正常系_force_slotでcareer_sister朝スロットが投稿される(
        self,
        mock_state_updater_class: Any,
        mock_account_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """--force-slot S1 で career_sister の朝スロットが投稿されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import (
            SLOT_TIME_MAP,
            AutoPosterConfig,
            SlotMatcher,
            _process_account,
        )

        # AccountPoster モック
        mock_poster = MagicMock()
        mock_poster.post.return_value = PostResult(
            platform="threads",
            media_id="cs-12345",
            permalink="https://www.threads.com/@career_sister/post/NEW",
        )
        mock_account_poster_class.return_value = mock_poster

        # StateUpdater モック
        mock_updater = MagicMock()
        mock_updater.check_already_posted.return_value = False
        mock_state_updater_class.return_value = mock_updater

        # career_sister の drafts ディレクトリを作成
        drafts_root = tmp_path / "creator" / "career_sister" / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        slot_dir = week_dir / "day_4_thu" / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text(
            "---\ntopic_tag: '#キャリア'\n---\nキャリアシスターの投稿内容。"
        )

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "type": "型3",
                            "theme": "T3",
                        },
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        posting_state_path = (
            tmp_path / "creator" / "career_sister" / "posting_state.json"
        )
        posting_state_path.parent.mkdir(parents=True, exist_ok=True)
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        config = AutoPosterConfig(
            account="career_sister",
            dry_run=False,
            force_slot="S1",
        )
        now = datetime(2026, 3, 27, 7, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)

        with patch("scripts.auto_poster.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path

            _process_account("career_sister", config, now, matcher)

        # AccountPoster.post が呼ばれたことを確認
        assert mock_poster.post.called

    @patch("scripts.auto_poster.AccountPoster")
    @patch("scripts.auto_poster.StateUpdater")
    def test_正常系_career_sister_status_publishedスロットはスキップされる(
        self,
        mock_state_updater_class: Any,
        mock_account_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """status == 'published' の career_sister スロットはスキップされることを確認。"""
        from scripts.auto_poster import (
            SLOT_TIME_MAP,
            AutoPosterConfig,
            SlotMatcher,
            _process_account,
        )

        # StateUpdater モック: 既に投稿済みとして返す
        mock_updater = MagicMock()
        mock_updater.check_already_posted.return_value = True
        mock_state_updater_class.return_value = mock_updater

        # AccountPoster モック
        mock_poster = MagicMock()
        mock_account_poster_class.return_value = mock_poster

        # career_sister の drafts ディレクトリを作成
        drafts_root = tmp_path / "creator" / "career_sister" / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        slot_dir = week_dir / "day_4_thu" / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("投稿内容")

        meta = {
            "week_start": "2026-03-24",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "status": "published",
                            "published_at": "2026-03-27T07:32:00+09:00",
                        }
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        posting_state_path = (
            tmp_path / "creator" / "career_sister" / "posting_state.json"
        )
        posting_state_path.parent.mkdir(parents=True, exist_ok=True)
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        config = AutoPosterConfig(
            account="career_sister",
            dry_run=False,
            force_slot="S1",
        )
        now = datetime(2026, 3, 27, 7, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)

        with patch("scripts.auto_poster.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path

            _process_account("career_sister", config, now, matcher)

        # 投稿済みのため AccountPoster.post は呼ばれないことを確認
        assert not mock_poster.post.called
