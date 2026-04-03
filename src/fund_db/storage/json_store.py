"""JSON-based persistent storage for fund database records.

Manages date-partitioned JSON files for fund data, supporting
per-category storage with automatic directory creation.

Classes
-------
FundDbStore
    JSON storage for fund database records with date partitioning.

Examples
--------
>>> from pathlib import Path
>>> store = FundDbStore(Path("/tmp/fund_db"))
>>> store.list_partitions("nisa_unlisted")
[]
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fund_db._logging import get_logger
from fund_db.exceptions import StorageError

logger = get_logger(__name__, module="json_store")


class FundDbStore:
    """JSON-based persistent storage for fund database records.

    Stores records in date-partitioned directories under a category.
    Directory structure:

    .. code-block:: text

        data_dir/
            {category}/
                {YYYY-MM-DD}/
                    records.json
                    raw/
                        {filename}.xlsx

    Parameters
    ----------
    data_dir : Path | None
        Root directory for fund data storage. Defaults to
        ``Path("data/fund_db")``. Subdirectories are created
        automatically on initialization.

    Examples
    --------
    >>> from pathlib import Path
    >>> store = FundDbStore(Path("/tmp/fund_db"))
    >>> store.data_dir
    PosixPath('/tmp/fund_db')
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize FundDbStore and create base directory.

        Parameters
        ----------
        data_dir : Path | None
            Root directory for fund data storage.
            Defaults to ``Path("data/fund_db")``.
        """
        self.data_dir = data_dir if data_dir is not None else Path("data/fund_db")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("FundDbStore initialized", data_dir=str(self.data_dir))

    def _partition_dir(self, category: str, partition_date: date) -> Path:
        """Get the directory path for a given category and date partition.

        Parameters
        ----------
        category : str
            Data category (e.g., "nisa_unlisted").
        partition_date : date
            Date for the partition directory.

        Returns
        -------
        Path
            Path to the partition directory.
        """
        return self.data_dir / category / partition_date.isoformat()

    def save_records(
        self,
        records: list[dict[str, Any]],
        category: str,
        partition_date: date | None = None,
    ) -> Path:
        """Save parsed records as a JSON file in a date-partitioned directory.

        Parameters
        ----------
        records : list[dict[str, Any]]
            List of record dictionaries to save.
        category : str
            Data category (e.g., "nisa_unlisted", "jpx_listed").
        partition_date : date | None
            Date for the partition directory. Defaults to today (UTC).

        Returns
        -------
        Path
            Path to the saved JSON file.

        Raises
        ------
        StorageError
            If the file cannot be written.

        Examples
        --------
        >>> from pathlib import Path
        >>> store = FundDbStore(Path("/tmp/fund_db"))
        >>> path = store.save_records(
        ...     [{"name": "Fund A"}], "nisa_unlisted"
        ... )
        """
        if partition_date is None:
            partition_date = datetime.now(timezone.utc).date()

        partition_dir = self._partition_dir(category, partition_date)
        partition_dir.mkdir(parents=True, exist_ok=True)

        output_path = partition_dir / "records.json"
        try:
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "category": category,
                        "partition_date": partition_date.isoformat(),
                        "record_count": len(records),
                        "saved_at": datetime.now(timezone.utc).isoformat(),
                        "records": records,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(
                "Records saved",
                category=category,
                partition_date=partition_date.isoformat(),
                record_count=len(records),
                path=str(output_path),
            )
        except OSError as exc:
            raise StorageError(
                f"Failed to save records: {exc}",
                path=str(output_path),
            ) from exc

        return output_path

    def save_raw_excel(
        self,
        content: bytes,
        category: str,
        filename: str,
        partition_date: date | None = None,
    ) -> Path:
        """Save raw Excel file content in a date-partitioned directory.

        Parameters
        ----------
        content : bytes
            Raw binary content of the Excel file.
        category : str
            Data category (e.g., "nisa_unlisted").
        filename : str
            Filename for the saved Excel file (e.g., "tsumitate_target.xlsx").
        partition_date : date | None
            Date for the partition directory. Defaults to today (UTC).

        Returns
        -------
        Path
            Path to the saved Excel file.

        Raises
        ------
        StorageError
            If the file cannot be written.
        """
        if partition_date is None:
            partition_date = datetime.now(timezone.utc).date()

        raw_dir = self._partition_dir(category, partition_date) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        output_path = raw_dir / filename
        try:
            output_path.write_bytes(content)
            logger.info(
                "Raw Excel saved",
                category=category,
                filename=filename,
                partition_date=partition_date.isoformat(),
                size_bytes=len(content),
                path=str(output_path),
            )
        except OSError as exc:
            raise StorageError(
                f"Failed to save raw Excel: {exc}",
                path=str(output_path),
            ) from exc

        return output_path

    def get_latest_raw_files(self, category: str) -> list[Path]:
        """Get raw Excel files from the latest partition.

        Parameters
        ----------
        category : str
            Data category.

        Returns
        -------
        list[Path]
            List of raw file paths from the latest partition.
        """
        partitions = self.list_partitions(category)
        if not partitions:
            return []
        latest = max(partitions)
        raw_dir = self._partition_dir(category, latest) / "raw"
        if not raw_dir.exists():
            return []
        return sorted(raw_dir.iterdir())

    def load_latest(
        self,
        category: str,
        partitions: list[date] | None = None,
    ) -> list[dict[str, Any]] | None:
        """Load records from the latest partition for a given category.

        Parameters
        ----------
        category : str
            Data category to load from.
        partitions : list[date] | None
            Pre-fetched partition list. When provided, avoids a
            redundant ``list_partitions()`` call. Defaults to None.

        Returns
        -------
        list[dict[str, Any]] | None
            List of record dictionaries from the latest partition,
            or ``None`` if no partitions exist.

        Examples
        --------
        >>> from pathlib import Path
        >>> store = FundDbStore(Path("/tmp/fund_db_empty"))
        >>> store.load_latest("nisa_unlisted") is None
        True
        """
        if partitions is None:
            partitions = self.list_partitions(category)
        if not partitions:
            logger.debug("No partitions found", category=category)
            return None

        latest_date = max(partitions)
        records_path = self._partition_dir(category, latest_date) / "records.json"

        if not records_path.exists():
            logger.warning(
                "Partition directory exists but records.json missing",
                category=category,
                partition_date=latest_date.isoformat(),
            )
            return None

        try:
            with records_path.open(encoding="utf-8") as f:
                data: Any = json.load(f)
            records: list[dict[str, Any]] = data.get("records", [])
            logger.info(
                "Records loaded",
                category=category,
                partition_date=latest_date.isoformat(),
                record_count=len(records),
            )
            return records
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load records",
                category=category,
                partition_date=latest_date.isoformat(),
                error=str(exc),
            )
            return None

    def list_partitions(self, category: str) -> list[date]:
        """List all date partitions for a given category.

        Parameters
        ----------
        category : str
            Data category to list partitions for.

        Returns
        -------
        list[date]
            Sorted list of partition dates.

        Examples
        --------
        >>> from pathlib import Path
        >>> store = FundDbStore(Path("/tmp/fund_db_empty"))
        >>> store.list_partitions("nisa_unlisted")
        []
        """
        category_dir = self.data_dir / category
        if not category_dir.exists():
            return []

        partitions: list[date] = []
        for entry in sorted(category_dir.iterdir()):
            if entry.is_dir():
                try:
                    partitions.append(date.fromisoformat(entry.name))
                except ValueError:
                    logger.debug(
                        "Skipping non-date directory",
                        category=category,
                        name=entry.name,
                    )
        return partitions
