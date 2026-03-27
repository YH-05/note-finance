"""Unit tests for auto_poster.py Wave 3 components.

Wave 3: career_sister Instagram カルーセル投稿 + エラー分離。
- instagram: true スロットでカルーセル投稿が実行される
- carousel/slide_*.png が R2 にアップロードされ公開 URL が取得できる
- instagram_caption.md 存在時はそれをキャプション使用
- instagram_caption.md 不在時は threads_post.md をフォールバック
- R2 未設定時は Instagram 投稿をスキップし WARNING ログを出力
- Threads・Instagram 投稿が独立した try/except で実装されている
- 投稿後に slots[].instagram_permalink が meta.json に更新される
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call, patch
from zoneinfo import ZoneInfo

import pytest

if TYPE_CHECKING:
    from pathlib import Path

JST = ZoneInfo("Asia/Tokyo")


# ---------------------------------------------------------------------------
# CareerSisterInstagramPoster
# ---------------------------------------------------------------------------


class TestCareerSisterInstagramPoster:
    """CareerSisterInstagramPoster のテスト。"""

    def test_正常系_インスタンスを生成できる(self) -> None:
        """CareerSisterInstagramPoster が生成できることを確認。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        poster = CareerSisterInstagramPoster()
        assert poster is not None

    def test_正常系_instagram_caption_mdが存在する場合にそれをキャプションとして使用する(
        self, tmp_path: Path
    ) -> None:
        """instagram_caption.md が存在する場合にそのファイルをキャプションとして返す。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)

        caption_content = "Instagramキャプションテスト\n#キャリア"
        (slot_dir / "instagram_caption.md").write_text(
            caption_content, encoding="utf-8"
        )

        poster = CareerSisterInstagramPoster()
        result = poster._get_caption(slot_dir)

        assert result == caption_content

    def test_正常系_instagram_caption_mdが存在しない場合はthreads_post_mdをフォールバックとして使用する(
        self, tmp_path: Path
    ) -> None:
        """instagram_caption.md が不在の場合に threads_post.md をフォールバックとして返す。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)

        fallback_content = "スレッズ投稿テスト\n#キャリア"
        (slot_dir / "threads_post.md").write_text(fallback_content, encoding="utf-8")

        poster = CareerSisterInstagramPoster()
        result = poster._get_caption(slot_dir)

        assert result == fallback_content

    def test_正常系_carousel_slide_pngをソートしてリストを返す(
        self, tmp_path: Path
    ) -> None:
        """carousel/slide_*.png がソートされたリストで取得できることを確認。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        slot_dir = tmp_path / "slot_1_morning"
        carousel_dir = slot_dir / "carousel"
        carousel_dir.mkdir(parents=True)

        # slide_*.png を逆順に作成（ソートのテスト用）
        for i in [3, 1, 2]:
            (carousel_dir / f"slide_{i:02d}.png").write_bytes(b"fake_png_data")

        poster = CareerSisterInstagramPoster()
        result = poster._get_carousel_images(slot_dir)

        assert len(result) == 3
        # ソートされていることを確認
        names = [p.name for p in result]
        assert names == ["slide_01.png", "slide_02.png", "slide_03.png"]

    def test_正常系_carousel_ディレクトリが存在しない場合は空リストを返す(
        self, tmp_path: Path
    ) -> None:
        """carousel/ ディレクトリが存在しない場合に空リストが返されることを確認。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        slot_dir = tmp_path / "slot_no_carousel"
        slot_dir.mkdir(parents=True)

        poster = CareerSisterInstagramPoster()
        result = poster._get_carousel_images(slot_dir)

        assert result == []

    @patch("scripts.auto_poster.R2ImageHost")
    @patch("scripts.auto_poster.InstagramPoster")
    def test_正常系_R2設定済みでInstagramカルーセル投稿が実行される(
        self,
        mock_instagram_class: Any,
        mock_r2_class: Any,
        tmp_path: Path,
    ) -> None:
        """R2 設定済みかつ carousel 画像がある場合に Instagram カルーセル投稿が実行される。"""
        from creator.poster import PostResult
        from scripts.auto_poster import CareerSisterInstagramPoster

        # R2ImageHost モック
        mock_r2 = MagicMock()
        mock_r2.is_configured = True
        mock_r2.upload_batch.return_value = [
            "https://r2.example.com/slide_01.png",
            "https://r2.example.com/slide_02.png",
        ]
        mock_r2_class.return_value = mock_r2

        # InstagramPoster モック
        mock_ig = MagicMock()
        mock_ig.post_carousel.return_value = PostResult(
            platform="instagram",
            media_id="ig-12345",
            permalink="https://www.instagram.com/p/TEST123/",
        )
        mock_instagram_class.return_value = mock_ig

        # スロットディレクトリをセットアップ
        slot_dir = tmp_path / "slot_1_morning"
        carousel_dir = slot_dir / "carousel"
        carousel_dir.mkdir(parents=True)
        (carousel_dir / "slide_01.png").write_bytes(b"fake")
        (carousel_dir / "slide_02.png").write_bytes(b"fake")
        (slot_dir / "instagram_caption.md").write_text(
            "テストキャプション", encoding="utf-8"
        )

        poster = CareerSisterInstagramPoster()
        result = poster.post(slot_dir)

        assert result is not None
        assert result.platform == "instagram"
        assert result.media_id == "ig-12345"
        assert result.permalink == "https://www.instagram.com/p/TEST123/"

        # upload_batch が呼ばれたことを確認
        mock_r2.upload_batch.assert_called_once()

        # post_carousel が呼ばれたことを確認
        mock_ig.post_carousel.assert_called_once_with(
            caption="テストキャプション",
            image_urls=[
                "https://r2.example.com/slide_01.png",
                "https://r2.example.com/slide_02.png",
            ],
        )

    @patch("scripts.auto_poster.R2ImageHost")
    def test_正常系_R2未設定時はNoneを返してスキップする(
        self,
        mock_r2_class: Any,
        tmp_path: Path,
    ) -> None:
        """R2 が未設定の場合に None を返してスキップすることを確認。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        # R2ImageHost モック（未設定）
        mock_r2 = MagicMock()
        mock_r2.is_configured = False
        mock_r2_class.return_value = mock_r2

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)

        poster = CareerSisterInstagramPoster()
        result = poster.post(slot_dir)

        assert result is None

    @patch("scripts.auto_poster.R2ImageHost")
    def test_正常系_carousel画像が存在しない場合はNoneを返す(
        self,
        mock_r2_class: Any,
        tmp_path: Path,
    ) -> None:
        """carousel/ に PNG 画像がない場合に None を返すことを確認。"""
        from scripts.auto_poster import CareerSisterInstagramPoster

        mock_r2 = MagicMock()
        mock_r2.is_configured = True
        mock_r2_class.return_value = mock_r2

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        # carousel ディレクトリなし

        poster = CareerSisterInstagramPoster()
        result = poster.post(slot_dir)

        assert result is None

    @patch("scripts.auto_poster.R2ImageHost")
    @patch("scripts.auto_poster.InstagramPoster")
    def test_正常系_upload_batchにauto_posterプレフィックスを使用する(
        self,
        mock_instagram_class: Any,
        mock_r2_class: Any,
        tmp_path: Path,
    ) -> None:
        """upload_batch が prefix='auto_poster' で呼ばれることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import CareerSisterInstagramPoster

        mock_r2 = MagicMock()
        mock_r2.is_configured = True
        mock_r2.upload_batch.return_value = ["https://r2.example.com/slide_01.png"]
        mock_r2_class.return_value = mock_r2

        mock_ig = MagicMock()
        mock_ig.post_carousel.return_value = PostResult(
            platform="instagram",
            media_id="ig-99",
            permalink="https://www.instagram.com/p/XYZ/",
        )
        mock_instagram_class.return_value = mock_ig

        slot_dir = tmp_path / "slot_1_morning"
        carousel_dir = slot_dir / "carousel"
        carousel_dir.mkdir(parents=True)
        (carousel_dir / "slide_01.png").write_bytes(b"fake")
        (slot_dir / "threads_post.md").write_text("キャプション", encoding="utf-8")

        poster = CareerSisterInstagramPoster()
        poster.post(slot_dir)

        # prefix='auto_poster' で呼ばれていることを確認
        call_kwargs = mock_r2.upload_batch.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("prefix") == "auto_poster"


# ---------------------------------------------------------------------------
# StateUpdater: instagram_permalink サポート
# ---------------------------------------------------------------------------


class TestStateUpdaterInstagramPermalink:
    """StateUpdater の instagram_permalink サポートテスト。"""

    def test_正常系_career_sisterのupdate_metaにinstagram_permalinkを書き込める(
        self, tmp_path: Path
    ) -> None:
        """update_meta が instagram_permalink を meta.json に書き込むことを確認。"""
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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": True,
                        }
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

        posted_at = "2026-03-27T07:32:00+09:00"
        threads_permalink = "https://www.threads.com/@career_sister/post/THREADS001"
        instagram_permalink = "https://www.instagram.com/p/IG001/"

        updater.update_meta(
            date="2026-03-27",
            slot="朝",
            posted_at=posted_at,
            permalink=threads_permalink,
            instagram_permalink=instagram_permalink,
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        morning_slot = updated_meta["days"][0]["slots"][0]
        assert morning_slot["status"] == "published"
        assert morning_slot["threads_permalink"] == threads_permalink
        assert morning_slot["instagram_permalink"] == instagram_permalink

    def test_正常系_instagram_permalink未指定の場合は書き込まない(
        self, tmp_path: Path
    ) -> None:
        """instagram_permalink が None の場合にフィールドが書き込まれないことを確認。"""
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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": False,
                        }
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
            slot="朝",
            posted_at="2026-03-27T07:32:00+09:00",
            permalink="https://www.threads.com/@career_sister/post/THREADS002",
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        morning_slot = updated_meta["days"][0]["slots"][0]
        assert "instagram_permalink" not in morning_slot

    def test_正常系_mitsukiアカウントのupdate_meta既存動作は変わらない(
        self, tmp_path: Path
    ) -> None:
        """mitsuki の update_meta は instagram_permalink 追加後も既存動作が変わらない。"""
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
                    "slots": [{"slot": "朝", "category": "有益"}],
                }
            ],
        }
        meta_path = week_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        posting_state_path = tmp_path / "posting_state.json"
        posting_state_path.write_text(
            json.dumps({"post_history": []}, ensure_ascii=False)
        )

        # mitsuki はデフォルトアカウント
        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
        )

        posted_at = "2026-03-27T07:32:00+09:00"
        permalink = "https://www.threads.com/@mitsuki/post/ABC"

        updater.update_meta(
            date="2026-03-27",
            slot="朝",
            posted_at=posted_at,
            permalink=permalink,
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        morning_slot = updated_meta["days"][0]["slots"][0]
        # mitsuki フォーマット
        assert morning_slot["posted_at"] == posted_at
        assert morning_slot["permalink"] == permalink
        assert "instagram_permalink" not in morning_slot


# ---------------------------------------------------------------------------
# _execute_post: Threads・Instagram 独立 try/except
# ---------------------------------------------------------------------------


class TestExecutePostWave3:
    """_execute_post の Wave 3: Threads・Instagram 独立投稿テスト。"""

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_instagram_trueスロットでInstagram投稿が実行される(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """instagram: True のスロットで CareerSisterInstagramPoster.post が呼ばれる。"""
        from creator.poster import PostResult
        from scripts.auto_poster import StateUpdater, _execute_post

        # AccountPoster モック（Threads）
        mock_threads = MagicMock()
        mock_threads.post.return_value = PostResult(
            platform="threads",
            media_id="t-001",
            permalink="https://www.threads.com/@career_sister/post/T001",
        )
        mock_account_poster_class.return_value = mock_threads

        # CareerSisterInstagramPoster モック
        mock_ig = MagicMock()
        mock_ig.post.return_value = PostResult(
            platform="instagram",
            media_id="ig-001",
            permalink="https://www.instagram.com/p/IG001/",
        )
        mock_ig_poster_class.return_value = mock_ig

        # スロットディレクトリ
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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": True,
                        }
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

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text(
            "---\ntopic_tag: '#キャリア'\n---\nテスト。", encoding="utf-8"
        )

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        slot_file = slot_dir / "threads_post.md"
        _execute_post(
            account="career_sister",
            slot_name="朝",
            today_str="2026-03-27",
            slot_file=slot_file,
            updater=updater,
            fresh_meta=meta,
        )

        # CareerSisterInstagramPoster.post が呼ばれたことを確認
        mock_ig.post.assert_called_once()

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_instagram_falseスロットでInstagram投稿はスキップされる(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """instagram: False のスロットで Instagram 投稿が実行されないことを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import StateUpdater, _execute_post

        mock_threads = MagicMock()
        mock_threads.post.return_value = PostResult(
            platform="threads",
            media_id="t-002",
            permalink="https://www.threads.com/@career_sister/post/T002",
        )
        mock_account_poster_class.return_value = mock_threads

        mock_ig = MagicMock()
        mock_ig_poster_class.return_value = mock_ig

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
                        {
                            "slot": "昼",
                            "category": "有益",
                            "instagram": False,
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

        slot_dir = tmp_path / "slot_2_noon"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("昼投稿テスト。", encoding="utf-8")

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        slot_file = slot_dir / "threads_post.md"
        _execute_post(
            account="career_sister",
            slot_name="昼",
            today_str="2026-03-27",
            slot_file=slot_file,
            updater=updater,
            fresh_meta=meta,
        )

        # Instagram 投稿は呼ばれない
        mock_ig.post.assert_not_called()

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_Threads失敗時もInstagram投稿はスキップされる(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """Threads 投稿が失敗した場合に Instagram 投稿もスキップされることを確認。

        Threads 失敗後は Instagram は実行しない（Instagram 投稿の前提が Threads 成功）。
        """
        from scripts.auto_poster import StateUpdater, _execute_post

        # Threads 投稿が例外を発生させる
        mock_threads = MagicMock()
        mock_threads.post.side_effect = RuntimeError("Threads API error")
        mock_account_poster_class.return_value = mock_threads

        mock_ig = MagicMock()
        mock_ig_poster_class.return_value = mock_ig

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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": True,
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

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト投稿。", encoding="utf-8")

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        # _execute_post は例外を発生させずに終了する（Threads エラーは内部でキャッチ）
        _execute_post(
            account="career_sister",
            slot_name="朝",
            today_str="2026-03-27",
            slot_file=slot_dir / "threads_post.md",
            updater=updater,
            fresh_meta=meta,
        )

        # Threads 失敗後は Instagram 投稿は呼ばれない
        mock_ig.post.assert_not_called()

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_Instagram失敗時もThreads投稿済み状態は保持される(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """Instagram 投稿が失敗しても Threads 投稿済み状態が保持されることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import StateUpdater, _execute_post

        # Threads 投稿は成功
        mock_threads = MagicMock()
        mock_threads.post.return_value = PostResult(
            platform="threads",
            media_id="t-003",
            permalink="https://www.threads.com/@career_sister/post/T003",
        )
        mock_account_poster_class.return_value = mock_threads

        # Instagram 投稿は例外を発生させる
        mock_ig = MagicMock()
        mock_ig.post.side_effect = RuntimeError("Instagram API error")
        mock_ig_poster_class.return_value = mock_ig

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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": True,
                        }
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

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト投稿。", encoding="utf-8")

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        # 例外が伝播しないこと（_execute_post が内部でキャッチ）
        _execute_post(
            account="career_sister",
            slot_name="朝",
            today_str="2026-03-27",
            slot_file=slot_dir / "threads_post.md",
            updater=updater,
            fresh_meta=meta,
        )

        # Threads 投稿後に meta.json が更新されている
        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        morning_slot = updated_meta["days"][0]["slots"][0]
        assert morning_slot.get("status") == "published"
        assert morning_slot.get("threads_permalink") is not None

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_Instagram成功時にinstagram_permalinkがmeta_jsonに書き込まれる(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """Instagram 投稿成功後に instagram_permalink が meta.json に書き込まれることを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import StateUpdater, _execute_post

        mock_threads = MagicMock()
        mock_threads.post.return_value = PostResult(
            platform="threads",
            media_id="t-004",
            permalink="https://www.threads.com/@career_sister/post/T004",
        )
        mock_account_poster_class.return_value = mock_threads

        mock_ig = MagicMock()
        mock_ig.post.return_value = PostResult(
            platform="instagram",
            media_id="ig-004",
            permalink="https://www.instagram.com/p/IG004/",
        )
        mock_ig_poster_class.return_value = mock_ig

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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": True,
                        }
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

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト投稿。", encoding="utf-8")

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="career_sister",
        )

        _execute_post(
            account="career_sister",
            slot_name="朝",
            today_str="2026-03-27",
            slot_file=slot_dir / "threads_post.md",
            updater=updater,
            fresh_meta=meta,
        )

        updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        morning_slot = updated_meta["days"][0]["slots"][0]
        assert (
            morning_slot.get("instagram_permalink")
            == "https://www.instagram.com/p/IG004/"
        )

    @patch("scripts.auto_poster.CareerSisterInstagramPoster")
    @patch("scripts.auto_poster.AccountPoster")
    def test_正常系_mitsukiアカウントではInstagram投稿は実行されない(
        self,
        mock_account_poster_class: Any,
        mock_ig_poster_class: Any,
        tmp_path: Path,
    ) -> None:
        """mitsuki アカウントでは Instagram 投稿が実行されないことを確認。"""
        from creator.poster import PostResult
        from scripts.auto_poster import StateUpdater, _execute_post

        mock_threads = MagicMock()
        mock_threads.post.return_value = PostResult(
            platform="threads",
            media_id="m-001",
            permalink="https://www.threads.com/@mitsuki/post/M001",
        )
        mock_account_poster_class.return_value = mock_threads

        mock_ig = MagicMock()
        mock_ig_poster_class.return_value = mock_ig

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
                        {
                            "slot": "朝",
                            "category": "有益",
                            "instagram": True,  # mitsuki でも instagram=True が設定されても無視
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

        slot_dir = tmp_path / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト投稿。", encoding="utf-8")

        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="mitsuki",
        )

        _execute_post(
            account="mitsuki",
            slot_name="朝",
            today_str="2026-03-27",
            slot_file=slot_dir / "threads_post.md",
            updater=updater,
            fresh_meta=meta,
        )

        # mitsuki では Instagram 投稿は呼ばれない
        mock_ig.post.assert_not_called()
