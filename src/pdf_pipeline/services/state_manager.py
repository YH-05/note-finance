"""Processing state manager for the pdf_pipeline package.

Manages processing state persistence via ``state.json``, providing
idempotency guarantees by tracking SHA-256 hashes and their processing
status. Also manages batch manifests for grouping related PDFs.

Classes
-------
StateManager
    Manages PDF processing state with JSON-backed persistence.

Examples
--------
>>> from pathlib import Path
>>> manager = StateManager(Path(".tmp/pdf-pipeline/state.json"))
>>> manager.record_status("abc123...", "completed")
>>> manager.is_processed("abc123...")
True
>>> manager.save()
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import StateError

if TYPE_CHECKING:
    from pathlib import Path

    from pdf_pipeline.types import ProcessingStatus

logger = get_logger(__name__, module="state_manager")

# ---------------------------------------------------------------------------
# State schema version
# ---------------------------------------------------------------------------

_STATE_VERSION = 2

# ---------------------------------------------------------------------------
# StateManager class
# ---------------------------------------------------------------------------


class StateManager:
    """Manages PDF processing state with JSON-backed persistence.

    Stores SHA-256 hash → processing status mappings and batch manifests
    in a single JSON file, providing idempotency across pipeline runs.

    Parameters
    ----------
    state_file : Path
        Path to the JSON state file. Parent directories are created
        automatically. If the file exists, its contents are loaded on
        initialization.

    Raises
    ------
    StateError
        If the state file exists but contains corrupted JSON.

    Examples
    --------
    >>> from pathlib import Path
    >>> manager = StateManager(Path(".tmp/pdf-pipeline/state.json"))
    >>> manager.record_status("abc123", "pending")
    >>> manager.get_status("abc123")
    'pending'
    """

    def __init__(self, state_file: Path) -> None:
        """Initialize StateManager and load existing state if present.

        Parameters
        ----------
        state_file : Path
            Path to the JSON state file.

        Raises
        ------
        StateError
            If the state file exists but contains corrupted JSON.
        """
        self.state_file = state_file
        # Each entry: {"status": ..., "filename": ..., "processed_at": ...}
        self._entries: dict[str, dict[str, str | None]] = {}
        self._batches: dict[str, list[str]] = {}

        # Ensure parent directory exists
        state_file.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("StateManager initialized", state_file=str(state_file))

        # Load existing state if file exists
        if state_file.exists():
            self._load()

    # -----------------------------------------------------------------------
    # Public API: status management
    # -----------------------------------------------------------------------

    def record_status(
        self,
        sha256: str,
        status: ProcessingStatus,
        *,
        filename: str | None = None,
        processed_at: str | None = None,
    ) -> None:
        """Record the processing status for a SHA-256 hash.

        Parameters
        ----------
        sha256 : str
            SHA-256 hex digest of the PDF file.
        status : ProcessingStatus
            New processing status.
        filename : str | None
            Original PDF filename for provenance tracking.
            If omitted, any previously recorded filename is preserved.
        processed_at : str | None
            ISO 8601 timestamp when processing completed.
            If omitted, any previously recorded timestamp is preserved.

        Examples
        --------
        >>> manager.record_status("abc123", "completed", filename="report.pdf")
        >>> manager.get_status("abc123")
        'completed'
        """
        existing = self._entries.get(sha256, {})
        self._entries[sha256] = {
            "status": status,
            "filename": filename if filename is not None else existing.get("filename"),
            "processed_at": (
                processed_at if processed_at is not None else existing.get("processed_at")
            ),
        }
        logger.debug(
            "Status recorded",
            sha256=sha256[:16] + "...",
            status=status,
            filename=filename,
        )

    def get_status(self, sha256: str) -> ProcessingStatus | None:
        """Get the processing status for a SHA-256 hash.

        Parameters
        ----------
        sha256 : str
            SHA-256 hex digest of the PDF file.

        Returns
        -------
        ProcessingStatus | None
            Current status, or ``None`` if not registered.

        Examples
        --------
        >>> manager.get_status("unknown")
        # Returns None
        """
        entry = self._entries.get(sha256)
        if entry is None:
            return None
        return entry.get("status")  # type: ignore[return-value]

    def get_filename(self, sha256: str) -> str | None:
        """Get the original PDF filename recorded for a SHA-256 hash.

        Parameters
        ----------
        sha256 : str
            SHA-256 hex digest of the PDF file.

        Returns
        -------
        str | None
            Original filename, or ``None`` if not recorded.

        Examples
        --------
        >>> manager.record_status("abc123", "completed", filename="report.pdf")
        >>> manager.get_filename("abc123")
        'report.pdf'
        """
        entry = self._entries.get(sha256)
        if entry is None:
            return None
        return entry.get("filename")

    def is_processed(self, sha256: str) -> bool:
        """Check whether a PDF has been successfully processed.

        A PDF is considered processed only if its status is ``'completed'``.

        Parameters
        ----------
        sha256 : str
            SHA-256 hex digest of the PDF file.

        Returns
        -------
        bool
            ``True`` if status is ``'completed'``, ``False`` otherwise.

        Examples
        --------
        >>> manager.record_status("abc123", "completed")
        >>> manager.is_processed("abc123")
        True
        """
        return self.get_status(sha256) == "completed"

    def get_processed_hashes(self) -> set[str]:
        """Return the set of SHA-256 hashes with status ``'completed'``.

        Returns
        -------
        set[str]
            Set of SHA-256 hashes that have been successfully processed.

        Examples
        --------
        >>> manager.record_status("hash1", "completed")
        >>> manager.record_status("hash2", "pending")
        >>> manager.get_processed_hashes()
        {'hash1'}
        """
        return {
            sha256
            for sha256, entry in self._entries.items()
            if entry.get("status") == "completed"
        }

    def get_all_statuses(self) -> dict[str, ProcessingStatus]:
        """Return a copy of all SHA-256 hashes and their processing statuses.

        Returns
        -------
        dict[str, ProcessingStatus]
            Mapping of SHA-256 hash to processing status for all tracked PDFs.

        Examples
        --------
        >>> manager.record_status("hash1", "completed")
        >>> manager.record_status("hash2", "pending")
        >>> manager.get_all_statuses()
        {'hash1': 'completed', 'hash2': 'pending'}
        """
        return {
            sha256: entry["status"]  # type: ignore[misc]
            for sha256, entry in self._entries.items()
            if "status" in entry
        }

    # -----------------------------------------------------------------------
    # Public API: batch manifest management
    # -----------------------------------------------------------------------

    def record_batch(self, batch_id: str, hashes: list[str]) -> None:
        """Record a batch manifest associating a batch ID with PDF hashes.

        Parameters
        ----------
        batch_id : str
            Unique identifier for this batch.
        hashes : list[str]
            List of SHA-256 hashes belonging to this batch.

        Examples
        --------
        >>> manager.record_batch("batch-001", ["hash1", "hash2"])
        >>> manager.get_batch("batch-001")
        ['hash1', 'hash2']
        """
        self._batches[batch_id] = list(hashes)
        logger.debug(
            "Batch manifest recorded",
            batch_id=batch_id,
            hash_count=len(hashes),
        )

    def get_batch(self, batch_id: str) -> list[str] | None:
        """Get the PDF hashes belonging to a batch.

        Parameters
        ----------
        batch_id : str
            Batch identifier to look up.

        Returns
        -------
        list[str] | None
            List of SHA-256 hashes in the batch, or ``None`` if not found.
        """
        return self._batches.get(batch_id)

    # -----------------------------------------------------------------------
    # Public API: persistence
    # -----------------------------------------------------------------------

    def save(self) -> None:
        """Persist the current state to the JSON state file.

        Raises
        ------
        StateError
            If the file cannot be written.

        Examples
        --------
        >>> manager.record_status("hash001", "completed")
        >>> manager.save()
        """
        state_data = {
            "version": _STATE_VERSION,
            "sha256_to_status": self._entries,
            "batches": self._batches,
        }

        try:
            self.state_file.write_text(
                json.dumps(state_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            msg = f"Failed to write state file: {exc}"
            logger.error(msg, state_file=str(self.state_file), error=str(exc))
            raise StateError(msg, state_file=str(self.state_file)) from exc

        logger.info(
            "State saved",
            state_file=str(self.state_file),
            total_entries=len(self._entries),
            completed=len(self.get_processed_hashes()),
            batch_count=len(self._batches),
        )

    # -----------------------------------------------------------------------
    # Private methods
    # -----------------------------------------------------------------------

    def _load(self) -> None:
        """Load state from the JSON state file.

        Raises
        ------
        StateError
            If the state file contains corrupted or unexpected JSON.
        """
        logger.debug("Loading state", state_file=str(self.state_file))

        try:
            raw = self.state_file.read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"Failed to read state file: {exc}"
            logger.error(msg, state_file=str(self.state_file), error=str(exc))
            raise StateError(msg, state_file=str(self.state_file)) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"State file is corrupted (invalid JSON): {exc}"
            logger.error(msg, state_file=str(self.state_file), error=str(exc))
            raise StateError(msg, state_file=str(self.state_file)) from exc

        if not isinstance(data, dict):
            msg = "State file is corrupted: root must be a JSON object"
            logger.error(msg, state_file=str(self.state_file))
            raise StateError(msg, state_file=str(self.state_file))

        # Support both v1 (string values) and v2 (dict values) formats
        raw_entries = data.get("sha256_to_status", {})
        self._entries = {}
        for sha256, value in raw_entries.items():
            if isinstance(value, str):
                # v1 format: just a status string — migrate to v2 structure
                self._entries[sha256] = {
                    "status": value,
                    "filename": None,
                    "processed_at": None,
                }
            elif isinstance(value, dict):
                self._entries[sha256] = value
        self._batches = data.get("batches", {})

        logger.info(
            "State loaded",
            state_file=str(self.state_file),
            total_entries=len(self._entries),
            completed=len(self.get_processed_hashes()),
            batch_count=len(self._batches),
        )
