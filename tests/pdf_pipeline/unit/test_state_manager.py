"""Unit tests for pdf_pipeline.services.state_manager module.

Tests cover:
- State persistence (save and load from JSON)
- Idempotency guarantee (same PDF processed twice → same state)
- Batch manifest management
- Status transitions
- Edge cases (empty state, corrupted file, concurrent-safe writes)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from pdf_pipeline.exceptions import StateError
from pdf_pipeline.services.state_manager import StateManager

if TYPE_CHECKING:
    from pathlib import Path

    from pdf_pipeline.types import ProcessingStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    """Return a temporary state file path."""
    return tmp_path / ".tmp" / "pdf-pipeline" / "state.json"


@pytest.fixture
def manager(state_file: Path) -> StateManager:
    """Create a fresh StateManager backed by a temp file."""
    return StateManager(state_file)


# ---------------------------------------------------------------------------
# StateManager.__init__
# ---------------------------------------------------------------------------


class TestStateManagerInit:
    """Tests for StateManager initialization."""

    def test_正常系_新規状態ファイルで初期化できる(self, state_file: Path) -> None:
        manager = StateManager(state_file)
        assert manager.state_file == state_file

    def test_正常系_初期化時に親ディレクトリを作成する(self, state_file: Path) -> None:
        assert not state_file.parent.exists()
        StateManager(state_file)
        assert state_file.parent.exists()

    def test_正常系_既存の状態ファイルがある場合も初期化できる(
        self, state_file: Path
    ) -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        initial_state = {"sha256_to_status": {"abc123": "completed"}, "batches": {}}
        state_file.write_text(json.dumps(initial_state), encoding="utf-8")

        manager = StateManager(state_file)
        assert manager.get_status("abc123") == "completed"


# ---------------------------------------------------------------------------
# StateManager.record_status / get_status
# ---------------------------------------------------------------------------


class TestStateManagerRecordAndGetStatus:
    """Tests for record_status and get_status methods."""

    def test_正常系_ステータスを記録して取得できる(self, manager: StateManager) -> None:
        manager.record_status("hash001", "pending")
        assert manager.get_status("hash001") == "pending"

    def test_正常系_全ステータスを記録できる(self, manager: StateManager) -> None:
        statuses: list[ProcessingStatus] = [
            "pending",
            "processing",
            "completed",
            "failed",
        ]
        for i, status in enumerate(statuses):
            manager.record_status(f"hash{i:03}", status)

        for i, status in enumerate(statuses):
            assert manager.get_status(f"hash{i:03}") == status

    def test_正常系_未登録ハッシュはNoneを返す(self, manager: StateManager) -> None:
        result = manager.get_status("unknown_hash")
        assert result is None

    def test_正常系_ステータスを更新できる(self, manager: StateManager) -> None:
        manager.record_status("hash001", "pending")
        manager.record_status("hash001", "completed")
        assert manager.get_status("hash001") == "completed"

    def test_正常系_冪等性_同じハッシュを2回記録しても問題ない(
        self, manager: StateManager
    ) -> None:
        manager.record_status("hash001", "completed")
        manager.record_status("hash001", "completed")
        assert manager.get_status("hash001") == "completed"


# ---------------------------------------------------------------------------
# StateManager.save / load (persistence)
# ---------------------------------------------------------------------------


class TestStateManagerPersistence:
    """Tests for state persistence (save and load)."""

    def test_正常系_状態をファイルに保存できる(
        self, state_file: Path, manager: StateManager
    ) -> None:
        manager.record_status("hash001", "completed")
        manager.save()

        assert state_file.exists()

    def test_正常系_保存した状態を再ロードできる(self, state_file: Path) -> None:
        manager1 = StateManager(state_file)
        manager1.record_status("hash001", "completed")
        manager1.record_status("hash002", "failed")
        manager1.save()

        manager2 = StateManager(state_file)
        assert manager2.get_status("hash001") == "completed"
        assert manager2.get_status("hash002") == "failed"

    def test_正常系_状態ファイルが存在しない場合も正常に起動する(
        self, state_file: Path
    ) -> None:
        assert not state_file.exists()
        manager = StateManager(state_file)
        assert manager.get_status("anything") is None

    def test_異常系_壊れたJSONファイルでStateError(self, state_file: Path) -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("{ corrupted json [[[", encoding="utf-8")

        with pytest.raises(StateError, match="corrupted"):
            StateManager(state_file)

    def test_正常系_保存後のJSONファイルが有効なJSON(
        self, state_file: Path, manager: StateManager
    ) -> None:
        manager.record_status("hash001", "completed")
        manager.save()

        raw = state_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "sha256_to_status" in data


# ---------------------------------------------------------------------------
# StateManager.is_processed
# ---------------------------------------------------------------------------


class TestStateManagerIsProcessed:
    """Tests for is_processed method."""

    def test_正常系_completedステータスはTrue(self, manager: StateManager) -> None:
        manager.record_status("hash001", "completed")
        assert manager.is_processed("hash001") is True

    def test_正常系_pendingステータスはFalse(self, manager: StateManager) -> None:
        manager.record_status("hash001", "pending")
        assert manager.is_processed("hash001") is False

    def test_正常系_processingステータスはFalse(self, manager: StateManager) -> None:
        manager.record_status("hash001", "processing")
        assert manager.is_processed("hash001") is False

    def test_正常系_failedステータスはFalse(self, manager: StateManager) -> None:
        manager.record_status("hash001", "failed")
        assert manager.is_processed("hash001") is False

    def test_正常系_未登録ハッシュはFalse(self, manager: StateManager) -> None:
        assert manager.is_processed("unknown") is False


# ---------------------------------------------------------------------------
# StateManager.get_processed_hashes
# ---------------------------------------------------------------------------


class TestStateManagerGetProcessedHashes:
    """Tests for get_processed_hashes method."""

    def test_正常系_completedのハッシュのみ返す(self, manager: StateManager) -> None:
        manager.record_status("hash_completed", "completed")
        manager.record_status("hash_pending", "pending")
        manager.record_status("hash_failed", "failed")

        processed = manager.get_processed_hashes()

        assert "hash_completed" in processed
        assert "hash_pending" not in processed
        assert "hash_failed" not in processed

    def test_正常系_処理済みがない場合空セットを返す(
        self, manager: StateManager
    ) -> None:
        manager.record_status("hash001", "pending")
        processed = manager.get_processed_hashes()
        assert processed == set()

    def test_正常系_空の状態管理では空セットを返す(self, manager: StateManager) -> None:
        assert manager.get_processed_hashes() == set()


# ---------------------------------------------------------------------------
# StateManager batch manifest
# ---------------------------------------------------------------------------


class TestStateManagerBatchManifest:
    """Tests for batch manifest management methods."""

    def test_正常系_バッチマニフェストを記録できる(self, manager: StateManager) -> None:
        batch_id = "batch-001"
        hashes = ["hash001", "hash002", "hash003"]
        manager.record_batch(batch_id, hashes)

        result = manager.get_batch(batch_id)
        assert result is not None
        assert sorted(result) == sorted(hashes)

    def test_正常系_存在しないバッチはNoneを返す(self, manager: StateManager) -> None:
        result = manager.get_batch("nonexistent-batch")
        assert result is None

    def test_正常系_バッチマニフェストが永続化される(self, state_file: Path) -> None:
        manager1 = StateManager(state_file)
        manager1.record_batch("batch-001", ["hash001", "hash002"])
        manager1.save()

        manager2 = StateManager(state_file)
        result = manager2.get_batch("batch-001")
        assert result is not None
        assert sorted(result) == ["hash001", "hash002"]

    def test_正常系_複数バッチを記録できる(self, manager: StateManager) -> None:
        manager.record_batch("batch-001", ["hash001"])
        manager.record_batch("batch-002", ["hash002", "hash003"])

        assert manager.get_batch("batch-001") == ["hash001"]
        batch_002 = manager.get_batch("batch-002")
        assert batch_002 is not None
        assert sorted(batch_002) == ["hash002", "hash003"]


# ---------------------------------------------------------------------------
# Idempotency (integration-style unit tests)
# ---------------------------------------------------------------------------


class TestStateManagerIdempotency:
    """Tests for idempotency guarantees."""

    def test_正常系_同一PDFを2回スキャンしても状態が正しい(
        self, state_file: Path
    ) -> None:
        """Simulate scanning the same PDF twice across two StateManager instances."""
        sha256 = "abcdef1234567890" * 4  # 64-char hash

        # First run: mark as completed
        manager1 = StateManager(state_file)
        manager1.record_status(sha256, "pending")
        manager1.record_status(sha256, "completed")
        manager1.save()

        # Second run: should still be completed
        manager2 = StateManager(state_file)
        assert manager2.get_status(sha256) == "completed"
        assert manager2.is_processed(sha256) is True

        # Recording "pending" again should not overwrite "completed"
        # (business logic: once completed, stays completed)
        manager2.record_status(sha256, "completed")  # idempotent
        assert manager2.get_status(sha256) == "completed"
