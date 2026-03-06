"""Scraper registry: manages BaseReportScraper instances by source key.

ScraperRegistry provides a mapping between source keys and their scraper
implementations. Supports manual registration and automatic registration
from a list of ``SourceConfig`` objects.

Classes
-------
ScraperRegistry
    Registry for report scraper instances.

Examples
--------
>>> from report_scraper.core.scraper_registry import ScraperRegistry
>>> registry = ScraperRegistry()
>>> registry.list_sources()
[]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from report_scraper.core.base_scraper import BaseReportScraper
    from report_scraper.types import SourceConfig


from report_scraper._logging import get_logger

logger = get_logger(__name__, module="scraper_registry")


# ---------------------------------------------------------------------------
# _DefaultScraper (internal)
# ---------------------------------------------------------------------------


class _StubScraper:
    """Stub scraper that returns empty listings for unregistered sources.

    Used by ``register_from_configs`` as a placeholder for sources without
    custom scraper implementations. Accepts config at init time, avoiding
    dynamic class creation on every call.
    """

    def __init__(self, config: SourceConfig) -> None:
        self._config = config

    @property
    def source_key(self) -> str:
        return self._config.key

    @property
    def source_config(self) -> SourceConfig:
        return self._config

    async def fetch_listing(self) -> list[Any]:
        # AIDEV-NOTE: Default scraper returns empty listing.
        # Real scraping logic is in concrete scraper subclasses.
        return []

    async def extract_report(self, meta: Any) -> Any:
        from report_scraper.types import ScrapedReport

        return ScrapedReport(metadata=meta)

    async def collect_latest(self, max_reports: int = 20) -> Any:
        from report_scraper.types import CollectResult

        return CollectResult(
            source_key=self.source_key,
            reports=(),
            errors=(),
            duration=0.0,
        )


# ---------------------------------------------------------------------------
# ScraperRegistry
# ---------------------------------------------------------------------------


class ScraperRegistry:
    """Registry that maps source keys to BaseReportScraper instances.

    Provides registration, lookup, and listing of scrapers. Supports
    automatic registration from ``SourceConfig`` objects, creating
    default scrapers for sources without custom implementations.

    Parameters
    ----------
    scrapers : dict[str, BaseReportScraper] | None
        Initial mapping of source keys to scraper instances.
        Defaults to an empty dict.

    Examples
    --------
    >>> registry = ScraperRegistry()
    >>> registry.list_sources()
    []
    """

    def __init__(
        self,
        scrapers: dict[str, BaseReportScraper] | None = None,
    ) -> None:
        self._scrapers: dict[str, BaseReportScraper] = (
            dict(scrapers) if scrapers else {}
        )

        logger.debug(
            "ScraperRegistry initialized",
            scraper_count=len(self._scrapers),
            registered_keys=list(self._scrapers.keys()),
        )

    # -- Registration --------------------------------------------------------

    def register(self, scraper: BaseReportScraper) -> None:
        """Register a scraper instance using its source_key.

        If a scraper is already registered for the same key, it is
        overwritten.

        Parameters
        ----------
        scraper : BaseReportScraper
            Scraper instance to register. Its ``source_key`` property
            is used as the registry key.

        Examples
        --------
        >>> from report_scraper.core.scraper_registry import ScraperRegistry
        >>> registry = ScraperRegistry()
        >>> # registry.register(my_scraper)
        """
        key = scraper.source_key
        self._scrapers[key] = scraper
        logger.info(
            "Scraper registered",
            source_key=key,
            scraper_type=type(scraper).__name__,
        )

    def register_from_configs(self, configs: list[SourceConfig]) -> int:
        """Register default scrapers for configs without existing scrapers.

        For each ``SourceConfig``, if no scraper is already registered
        for its key, a default (stub) scraper is created and registered.
        Existing registrations are never overwritten.

        Parameters
        ----------
        configs : list[SourceConfig]
            List of source configurations.

        Returns
        -------
        int
            Number of newly registered scrapers.

        Examples
        --------
        >>> registry = ScraperRegistry()
        >>> # registered = registry.register_from_configs(configs)
        """
        count = 0
        for config in configs:
            if config.key in self._scrapers:
                logger.debug(
                    "Skipping config, scraper already registered",
                    source_key=config.key,
                )
                continue

            stub = _StubScraper(config)
            self._scrapers[config.key] = stub  # type: ignore[assignment]
            count += 1
            logger.info(
                "Default scraper registered from config",
                source_key=config.key,
                rendering=config.rendering,
            )

        logger.info(
            "register_from_configs completed",
            total_configs=len(configs),
            newly_registered=count,
        )
        return count

    # -- Lookup --------------------------------------------------------------

    def get_scraper(self, source_key: str) -> BaseReportScraper:
        """Get a registered scraper by source key.

        Parameters
        ----------
        source_key : str
            Source key to look up.

        Returns
        -------
        BaseReportScraper
            The registered scraper instance.

        Raises
        ------
        KeyError
            If no scraper is registered for the given key.

        Examples
        --------
        >>> registry = ScraperRegistry()
        >>> # scraper = registry.get_scraper("advisor_perspectives")
        """
        if source_key not in self._scrapers:
            logger.warning("Scraper not found", source_key=source_key)
            msg = f"No scraper registered for source key: {source_key}"
            raise KeyError(msg)

        return self._scrapers[source_key]

    # -- Listing -------------------------------------------------------------

    def list_sources(self) -> list[str]:
        """List all registered source keys.

        Returns
        -------
        list[str]
            List of source keys in the registry.

        Examples
        --------
        >>> registry = ScraperRegistry()
        >>> registry.list_sources()
        []
        """
        return list(self._scrapers.keys())
