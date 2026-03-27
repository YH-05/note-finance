"""Unit tests for auto_poster.py Wave 5 components.

Wave 5: マルチマシン対応（NasLockManager + NasSyncer）
- NAS マウント時は NAS 上のロックファイルでロック取得
- NAS 未マウント時は /tmp フォールバック + WARNING（マルチマシン運用時は NAS マウント必須の旨）
- NasSyncer.pull() が scripts/sync_nas.sh --pull を呼ぶ
- NasSyncer.push() が scripts/sync_nas.sh --push を呼ぶ
- NAS 未マウント時は pull/push がスキップされる
- main() 内: ロック取得 → pull → アカウントループ → push → ロック解放
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# ---------------------------------------------------------------------------
# NasLockManager
# ---------------------------------------------------------------------------


class TestNasLockManager:
    """NasLockManager のテスト。"""

    def test_正常系_NASマウント時はNASロックパスを返す(self, tmp_path: Path) -> None:
        """NAS がマウントされている場合に NAS_LOCK_PATH の FileLock を返す。"""
        from scripts.auto_poster import NasLockManager

        manager = NasLockManager()
        # NAS マウントポイントが存在すると仮定してパッチ
        with patch("pathlib.Path.is_mount", return_value=True):
            lock = manager.get_lock()

        import filelock

        assert isinstance(lock, filelock.FileLock)
        assert "personal_folder" in str(lock.lock_file)

    def test_正常系_NAS未マウント時はフォールバックロックパスを返す(self) -> None:
        """NAS がマウントされていない場合に LOCAL_FALLBACK_LOCK の FileLock を返す。"""
        from scripts.auto_poster import NasLockManager

        manager = NasLockManager()
        with patch("pathlib.Path.is_mount", return_value=False):
            lock = manager.get_lock()

        import filelock

        assert isinstance(lock, filelock.FileLock)
        assert "tmp" in str(lock.lock_file)

    def test_正常系_NAS未マウント時にWARNINGログが出力される(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """NAS 未マウント時に WARNING レベルのログが出力されることを確認。"""
        import logging

        from scripts.auto_poster import NasLockManager

        manager = NasLockManager()
        with (
            patch("pathlib.Path.is_mount", return_value=False),
            caplog.at_level(logging.WARNING),
        ):
            manager.get_lock()

        # WARNING が出力されていること
        warning_msgs = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert len(warning_msgs) >= 1

    def test_正常系_WARNINGにマルチマシン運用NASマウント必須の旨が含まれる(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """WARNING メッセージにマルチマシン運用時の注意が含まれることを確認。"""
        import logging

        from scripts.auto_poster import NasLockManager

        manager = NasLockManager()
        with (
            patch("pathlib.Path.is_mount", return_value=False),
            caplog.at_level(logging.WARNING),
        ):
            manager.get_lock()

        # ログメッセージをすべて連結して検索
        all_messages = " ".join(
            r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
        )
        # マルチマシン運用に関するキーワードが含まれること
        assert (
            "NAS" in all_messages
            or "multi" in all_messages.lower()
            or "マルチ" in all_messages
        )

    def test_正常系_NASロックパス定数が正しく定義されている(self) -> None:
        """NAS_LOCK_PATH 定数が正しく定義されていることを確認。"""
        from scripts.auto_poster import NAS_LOCK_PATH

        assert "/Volumes/personal_folder" in str(NAS_LOCK_PATH)
        assert "auto_poster_lock" in str(NAS_LOCK_PATH)

    def test_正常系_フォールバックロックパス定数が正しく定義されている(self) -> None:
        """LOCAL_FALLBACK_LOCK 定数が正しく定義されていることを確認。"""
        from scripts.auto_poster import LOCAL_FALLBACK_LOCK

        assert "/tmp" in str(LOCAL_FALLBACK_LOCK)
        assert "note-finance" in str(LOCAL_FALLBACK_LOCK)


# ---------------------------------------------------------------------------
# NasSyncer
# ---------------------------------------------------------------------------


class TestNasSyncer:
    """NasSyncer のテスト。"""

    def test_正常系_NASマウント時pullがsync_nas_shを呼ぶ(
        self, tmp_path: "Path"
    ) -> None:
        """NAS マウント時に pull() が sync_nas.sh --pull を実行することを確認。"""
        from scripts.auto_poster import NasSyncer

        syncer = NasSyncer()
        with (
            patch("pathlib.Path.is_mount", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            syncer.pull()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--pull" in call_args
        assert "sync_nas.sh" in " ".join(call_args)

    def test_正常系_NASマウント時pushがsync_nas_shを呼ぶ(
        self, tmp_path: "Path"
    ) -> None:
        """NAS マウント時に push() が sync_nas.sh --push を実行することを確認。"""
        from scripts.auto_poster import NasSyncer

        syncer = NasSyncer()
        with (
            patch("pathlib.Path.is_mount", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            syncer.push()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--push" in call_args
        assert "sync_nas.sh" in " ".join(call_args)

    def test_正常系_NAS未マウント時はpullがスキップされる(self) -> None:
        """NAS 未マウント時に pull() が subprocess.run を呼ばないことを確認。"""
        from scripts.auto_poster import NasSyncer

        syncer = NasSyncer()
        with (
            patch("pathlib.Path.is_mount", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            syncer.pull()

        mock_run.assert_not_called()

    def test_正常系_NAS未マウント時はpushがスキップされる(self) -> None:
        """NAS 未マウント時に push() が subprocess.run を呼ばないことを確認。"""
        from scripts.auto_poster import NasSyncer

        syncer = NasSyncer()
        with (
            patch("pathlib.Path.is_mount", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            syncer.push()

        mock_run.assert_not_called()

    def test_正常系_NasSyncerインスタンスを生成できる(self) -> None:
        """NasSyncer が引数なしで生成できることを確認。"""
        from scripts.auto_poster import NasSyncer

        syncer = NasSyncer()
        assert syncer is not None


# ---------------------------------------------------------------------------
# main() への NasLockManager + NasSyncer 組み込み
# ---------------------------------------------------------------------------


class TestMainNasIntegration:
    """main() に NasLockManager と NasSyncer が正しく組み込まれていることを確認。"""

    @patch("scripts.auto_poster.NasSyncer")
    @patch("scripts.auto_poster.NasLockManager")
    @patch("scripts.auto_poster._process_account")
    @patch("scripts.auto_poster.print_summary")
    def test_正常系_mainでNasLockManagerが使用される(
        self,
        mock_print_summary: MagicMock,
        mock_process_account: MagicMock,
        mock_nas_lock_manager_class: MagicMock,
        mock_nas_syncer_class: MagicMock,
    ) -> None:
        """main() が NasLockManager.get_lock() を呼ぶことを確認。"""
        from scripts.auto_poster import main

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_manager = MagicMock()
        mock_manager.get_lock.return_value = mock_lock
        mock_nas_lock_manager_class.return_value = mock_manager

        main(["--dry-run", "--account", "mitsuki"])

        mock_nas_lock_manager_class.assert_called_once()
        mock_manager.get_lock.assert_called_once()

    @patch("scripts.auto_poster.NasSyncer")
    @patch("scripts.auto_poster.NasLockManager")
    @patch("scripts.auto_poster._process_account")
    @patch("scripts.auto_poster.print_summary")
    def test_正常系_mainで投稿前にpullが実行される(
        self,
        mock_print_summary: MagicMock,
        mock_process_account: MagicMock,
        mock_nas_lock_manager_class: MagicMock,
        mock_nas_syncer_class: MagicMock,
    ) -> None:
        """main() が投稿前に NasSyncer.pull() を呼ぶことを確認。"""
        from scripts.auto_poster import main

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_manager = MagicMock()
        mock_manager.get_lock.return_value = mock_lock
        mock_nas_lock_manager_class.return_value = mock_manager

        mock_syncer = MagicMock()
        mock_nas_syncer_class.return_value = mock_syncer

        main(["--dry-run", "--account", "mitsuki"])

        mock_syncer.pull.assert_called_once()

    @patch("scripts.auto_poster.NasSyncer")
    @patch("scripts.auto_poster.NasLockManager")
    @patch("scripts.auto_poster._process_account")
    @patch("scripts.auto_poster.print_summary")
    def test_正常系_mainで投稿後にpushが実行される(
        self,
        mock_print_summary: MagicMock,
        mock_process_account: MagicMock,
        mock_nas_lock_manager_class: MagicMock,
        mock_nas_syncer_class: MagicMock,
    ) -> None:
        """main() が投稿後に NasSyncer.push() を呼ぶことを確認。"""
        from scripts.auto_poster import main

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_manager = MagicMock()
        mock_manager.get_lock.return_value = mock_lock
        mock_nas_lock_manager_class.return_value = mock_manager

        mock_syncer = MagicMock()
        mock_nas_syncer_class.return_value = mock_syncer

        main(["--dry-run", "--account", "mitsuki"])

        mock_syncer.push.assert_called_once()

    @patch("scripts.auto_poster.NasSyncer")
    @patch("scripts.auto_poster.NasLockManager")
    @patch("scripts.auto_poster._process_account")
    @patch("scripts.auto_poster.print_summary")
    def test_正常系_pullはアカウントループより前に呼ばれる(
        self,
        mock_print_summary: MagicMock,
        mock_process_account: MagicMock,
        mock_nas_lock_manager_class: MagicMock,
        mock_nas_syncer_class: MagicMock,
    ) -> None:
        """main() で pull() が _process_account() より先に呼ばれることを確認。"""
        from scripts.auto_poster import main

        call_order: list[str] = []

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_manager = MagicMock()
        mock_manager.get_lock.return_value = mock_lock
        mock_nas_lock_manager_class.return_value = mock_manager

        mock_syncer = MagicMock()
        mock_syncer.pull.side_effect = lambda: call_order.append("pull")
        mock_syncer.push.side_effect = lambda: call_order.append("push")
        mock_nas_syncer_class.return_value = mock_syncer

        mock_process_account.side_effect = lambda *a, **kw: (
            call_order.append("process"),
            MagicMock(),
        )[1]

        main(["--account", "mitsuki"])

        assert call_order.index("pull") < call_order.index("process")

    @patch("scripts.auto_poster.NasSyncer")
    @patch("scripts.auto_poster.NasLockManager")
    @patch("scripts.auto_poster._process_account")
    @patch("scripts.auto_poster.print_summary")
    def test_正常系_pushはアカウントループより後に呼ばれる(
        self,
        mock_print_summary: MagicMock,
        mock_process_account: MagicMock,
        mock_nas_lock_manager_class: MagicMock,
        mock_nas_syncer_class: MagicMock,
    ) -> None:
        """main() で push() が _process_account() より後に呼ばれることを確認。"""
        from scripts.auto_poster import main

        call_order: list[str] = []

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=mock_lock)
        mock_lock.__exit__ = MagicMock(return_value=False)
        mock_manager = MagicMock()
        mock_manager.get_lock.return_value = mock_lock
        mock_nas_lock_manager_class.return_value = mock_manager

        mock_syncer = MagicMock()
        mock_syncer.pull.side_effect = lambda: call_order.append("pull")
        mock_syncer.push.side_effect = lambda: call_order.append("push")
        mock_nas_syncer_class.return_value = mock_syncer

        mock_process_account.side_effect = lambda *a, **kw: (
            call_order.append("process"),
            MagicMock(),
        )[1]

        main(["--account", "mitsuki"])

        assert call_order.index("process") < call_order.index("push")
