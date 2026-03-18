"""Quota tracker for YouTube Data API v3 daily quota management.

This module provides QuotaTracker, which records API unit consumption
and raises QuotaExceededError when the daily budget is exhausted.

The daily budget defaults to 9,000 units (leaving a buffer below the
YouTube-imposed 10,000 unit/day limit) and can be overridden via the
``YT_QUOTA_BUDGET`` environment variable or the ``budget`` constructor
parameter.

Quota state is persisted to ``quota_usage.json`` in the given data
directory so that usage survives process restarts.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from youtube_transcript._errors import log_and_reraise
from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import QuotaExceededError, StorageError
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import QuotaUsage

logger = get_logger(__name__)

_DEFAULT_BUDGET = 9_000


class QuotaTracker:
    """Track and enforce YouTube Data API v3 daily quota usage.

    Quota state is persisted via :class:`~youtube_transcript.storage.json_storage.JSONStorage`
    so that usage is retained across process restarts.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.  The tracker reads
        and writes ``quota_usage.json`` inside this directory.
    budget : int, optional
        Maximum API units allowed per day.  Defaults to ``YT_QUOTA_BUDGET``
        environment variable, or 9,000 if the variable is not set.

    Examples
    --------
    >>> from pathlib import Path
    >>> tracker = QuotaTracker(Path("data/raw/youtube_transcript"))
    >>> tracker.consume(100)
    >>> tracker.remaining()
    8900
    >>> tracker.today_usage()
    100
    """

    def __init__(self, data_dir: Path, budget: int | None = None) -> None:
        """Initialise QuotaTracker.

        Parameters
        ----------
        data_dir : Path
            Root directory for youtube_transcript data.
        budget : int | None, optional
            Daily quota budget.  If *None*, the value is read from the
            ``YT_QUOTA_BUDGET`` environment variable, falling back to
            9,000.
        """
        self._storage = JSONStorage(data_dir)

        if budget is not None:
            self._budget = budget
        else:
            env_val = os.environ.get("YT_QUOTA_BUDGET")
            if env_val is not None:
                try:
                    self._budget = int(env_val)
                except ValueError:
                    logger.warning(
                        "Invalid YT_QUOTA_BUDGET value, using default",
                        env_value=env_val,
                        default_budget=_DEFAULT_BUDGET,
                    )
                    self._budget = _DEFAULT_BUDGET
            else:
                self._budget = _DEFAULT_BUDGET

        logger.debug(
            "QuotaTracker initialized",
            data_dir=str(data_dir),
            budget=self._budget,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def budget(self) -> int:
        """Daily quota budget in API units.

        Returns
        -------
        int
            Maximum number of API units allowed per day.
        """
        return self._budget

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def consume(self, units: int) -> None:
        """Record consumption of *units* API quota units.

        Parameters
        ----------
        units : int
            Number of API units to consume.  Must be non-negative.

        Raises
        ------
        ValueError
            If *units* is negative.
        QuotaExceededError
            If consuming *units* would exceed the daily budget.

        Examples
        --------
        >>> tracker.consume(100)
        >>> tracker.today_usage()
        100
        """
        if units < 0:
            raise ValueError(f"units must be non-negative, got {units}")

        quota = self._load_or_create_today()

        new_total = quota.units_used + units
        if new_total > self._budget:
            logger.warning(
                "Quota exceeded",
                current_usage=quota.units_used,
                requested_units=units,
                budget=self._budget,
            )
            raise QuotaExceededError(
                f"Daily quota exceeded: {new_total}/{self._budget} units "
                f"(requested {units}, already used {quota.units_used})"
            )

        quota.units_used = new_total

        with log_and_reraise(
            logger,
            "save quota usage after consume",
            context={"units": units, "new_total": new_total},
            reraise_as=StorageError,
        ):
            self._storage.save_quota_usage(quota)

        logger.info(
            "Quota consumed",
            units=units,
            total_used=new_total,
            remaining=self._budget - new_total,
        )

    def remaining(self) -> int:
        """Return the number of API quota units remaining today.

        Returns
        -------
        int
            Remaining units (``budget - today_usage()``).  Never negative.

        Examples
        --------
        >>> tracker.remaining()
        9000
        """
        quota = self._load_or_create_today()
        result = max(0, self._budget - quota.units_used)
        logger.debug(
            "Remaining quota queried",
            remaining=result,
            units_used=quota.units_used,
            budget=self._budget,
        )
        return result

    def today_usage(self) -> int:
        """Return the number of API quota units consumed today.

        Returns
        -------
        int
            Units consumed so far today.

        Examples
        --------
        >>> tracker.today_usage()
        0
        """
        quota = self._load_or_create_today()
        logger.debug(
            "Today's quota usage queried",
            units_used=quota.units_used,
            date=quota.date,
        )
        return quota.units_used

    def reset_if_new_day(self) -> None:
        """Reset the quota counter if the stored date is not today.

        This method is idempotent: calling it multiple times on the same
        day has no effect.  It should be called at the start of each
        collection run to ensure accurate daily accounting.

        Examples
        --------
        >>> tracker.reset_if_new_day()
        """
        today = self._today_str()
        quota = self._storage.load_quota_usage()

        if quota is None:
            logger.debug("No quota file found; nothing to reset", today=today)
            return

        if quota.date == today:
            logger.debug("Quota date matches today; no reset needed", today=today)
            return

        logger.info(
            "New day detected; resetting quota counter",
            old_date=quota.date,
            new_date=today,
        )
        fresh = QuotaUsage(date=today, units_used=0, budget=self._budget)
        self._storage.save_quota_usage(fresh)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _today_str() -> str:
        """Return today's date as an ISO 8601 date string (YYYY-MM-DD).

        Returns
        -------
        str
            Today's date in ``YYYY-MM-DD`` format (UTC).
        """
        return datetime.now(tz=timezone.utc).date().isoformat()

    def _load_or_create_today(self) -> QuotaUsage:
        """Load quota for today, or create a fresh record if absent / outdated.

        Returns
        -------
        QuotaUsage
            Quota usage record for today.  If the stored record belongs to
            a previous day it is **not** persisted here — the caller
            should persist any changes via :meth:`consume`.
        """
        today = self._today_str()
        quota = self._storage.load_quota_usage()

        if quota is None or quota.date != today:
            logger.debug(
                "Creating fresh quota record",
                today=today,
                stored_date=quota.date if quota else None,
            )
            quota = QuotaUsage(date=today, units_used=0, budget=self._budget)

        return quota
