#!/usr/bin/env python3
"""Backfill ``Source.published_at`` in creator-neo4j from source URLs.

The script fetches pages for Sources missing ``published_at`` and extracts a
publication timestamp from HTML metadata when possible. It only updates the
``Source`` node property and leaves all content nodes untouched.
"""

from __future__ import annotations

import argparse
import email.utils
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from neo4j_utils import create_driver

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 20
_DEFAULT_BATCH_SIZE = 100

_JSONLD_SCRIPT_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_META_TAG_RE = re.compile(r"<meta\s+([^>]+)>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)=["\']([^"\']+)["\']')
_TIME_DATETIME_RE = re.compile(
    r"<time[^>]+datetime=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_REDDIT_CREATED_TS_RE = re.compile(
    r'created-timestamp=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_META_DATE_KEYS: tuple[tuple[str, str], ...] = (
    ("property", "article:published_time"),
    ("property", "og:published_time"),
    ("property", "og:article:published_time"),
    ("name", "parsely-pub-date"),
    ("name", "publish-date"),
    ("name", "pubdate"),
    ("name", "date"),
    ("name", "dc.date"),
    ("name", "dc.date.issued"),
    ("itemprop", "datepublished"),
)
_JSON_DATE_KEYS: tuple[str, ...] = (
    "datePublished",
    "dateCreated",
    "uploadDate",
    "publishedAt",
    "publishAt",
)


@dataclass(slots=True)
class BackfillResult:
    """Execution summary."""

    candidates: int
    attempted: int
    updated: int
    skipped: int
    failed: int


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill creator Source.published_at from source URLs.",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7689",
        help="creator-neo4j URI",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username",
    )
    parser.add_argument(
        "--neo4j-password",
        default="gomasuke",
        help="Neo4j password",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of candidate Sources to process.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help="Batch size for Neo4j writes.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_DEFAULT_TIMEOUT,
        help="HTTP timeout seconds.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        default=None,
        help="Restrict to a specific domain. Can be passed multiple times.",
    )
    parser.add_argument(
        "--exclude-domain",
        action="append",
        dest="exclude_domains",
        default=None,
        help="Exclude a specific domain. Can be passed multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and parse only, do not write updates.",
    )
    return parser.parse_args(args)


def _fetch_candidates(
    driver: Any,
    *,
    domains: list[str] | None,
    exclude_domains: list[str] | None,
    limit: int | None,
) -> list[dict[str, str]]:
    """Fetch Source candidates missing ``published_at``."""
    query = """
    MATCH (s:Source)
    WHERE s.published_at IS NULL
      AND s.url STARTS WITH 'http'
      AND ($domains IS NULL OR s.domain IN $domains)
      AND ($exclude_domains IS NULL OR s.domain IS NULL OR NOT s.domain IN $exclude_domains)
    RETURN s.source_id AS source_id, s.url AS url, s.domain AS domain
    ORDER BY coalesce(s.domain, ''), s.url
    """
    if limit is not None:
        query += "\nLIMIT $limit"

    with driver.session() as session:
        records = session.run(
            query,
            domains=domains if domains else None,
            exclude_domains=exclude_domains if exclude_domains else None,
            limit=limit,
        )
        return [dict(record) for record in records]


def _clean_json_text(text: str) -> str:
    """Remove HTML wrappers from JSON-LD content."""
    return text.strip().replace("&quot;", '"')


def _iter_json_objects(value: Any) -> list[dict[str, Any]]:
    """Flatten dict/list JSON-LD payloads into dict objects."""
    if isinstance(value, dict):
        objects = [value]
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                objects.extend(_iter_json_objects(item))
        return objects
    if isinstance(value, list):
        objects: list[dict[str, Any]] = []
        for item in value:
            objects.extend(_iter_json_objects(item))
        return objects
    return []


def _extract_from_jsonld(html: str) -> str | None:
    """Extract publication date from JSON-LD blocks."""
    for match in _JSONLD_SCRIPT_RE.finditer(html):
        payload = _clean_json_text(match.group(1))
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for obj in _iter_json_objects(parsed):
            for key in _JSON_DATE_KEYS:
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _extract_from_meta(html: str) -> str | None:
    """Extract publication date from meta tags."""
    for match in _META_TAG_RE.finditer(html):
        attrs = {
            key.lower(): value.strip()
            for key, value in _ATTR_RE.findall(match.group(1))
            if value.strip()
        }
        content = attrs.get("content", "")
        if not content:
            continue
        for attr_name, attr_value in _META_DATE_KEYS:
            if attrs.get(attr_name) == attr_value:
                return content
    return None


def _extract_from_time(html: str) -> str | None:
    """Extract publication date from ``<time datetime>``."""
    match = _TIME_DATETIME_RE.search(html)
    if match:
        return match.group(1).strip()
    return None


def _extract_from_reddit(html: str) -> str | None:
    """Extract publication date from Reddit HTML."""
    match = _REDDIT_CREATED_TS_RE.search(html)
    if match:
        return match.group(1).strip()
    return None


def _normalize_date(value: str) -> str | None:
    """Convert common date formats to ISO 8601 string Neo4j datetime() accepts.

    Tries ISO 8601 normalization first, then RFC 2822. Returns None if the
    value cannot be parsed to a format Neo4j accepts.
    """
    value = value.strip()
    # Replace slash-separated date: 2026/03/26 -> 2026-03-26
    normalized = value.replace("/", "-")
    # Replace space between date and time: 2026-03-26 10:00 -> 2026-03-26T10:00
    normalized = re.sub(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", r"\1T\2", normalized)
    # Remove space before timezone offset: T09:44:30 +0900 -> T09:44:30+0900
    normalized = re.sub(r"(\d{2}:\d{2}(?::\d{2})?)\s+([+-]\d{2}:?\d{2})", r"\1\2", normalized)
    # Validate with Python datetime (Python 3.11+ fromisoformat handles ±HHmm)
    try:
        datetime.fromisoformat(normalized)
        return normalized
    except ValueError:
        pass
    # Fallback: try RFC 2822 (e.g. "Wed, 26 Mar 2026 10:00:00 +0900")
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.isoformat()
    except Exception:  # noqa: BLE001
        pass
    return None


def extract_published_at(html: str, *, domain: str | None = None) -> str | None:
    """Extract a publication timestamp from HTML."""
    for extractor in (_extract_from_jsonld, _extract_from_meta, _extract_from_time):
        value = extractor(html)
        if value:
            return value

    if domain == "reddit.com":
        return _extract_from_reddit(html)

    return None


def _build_session(timeout: int) -> requests.Session:
    """Create a requests session with browser-like headers."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }
    )
    session.request = _wrap_request_with_timeout(session.request, timeout)
    return session


def _wrap_request_with_timeout(request_func: Any, timeout: int) -> Any:
    """Bind a default timeout to a session request method."""
    def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", timeout)
        return request_func(method, url, **kwargs)

    return _request


def _discover_updates(
    candidates: list[dict[str, str]],
    *,
    timeout: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Fetch candidate URLs and return updates, skipped, and failures.

    Returns
    -------
    tuple[list, list, list]
        updates  : candidates where published_at was extracted successfully
        skipped  : candidates where the page loaded but no date was found
        failures : candidates where an HTTP or network error occurred
    """
    session = _build_session(timeout)
    updates: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    for candidate in candidates:
        url = candidate["url"]
        domain = candidate.get("domain")
        try:
            response = session.get(url, allow_redirects=True)
            response.raise_for_status()
            published_at = extract_published_at(response.text, domain=domain)
            if published_at:
                published_at = _normalize_date(published_at)
            if published_at:
                updates.append(
                    {
                        "source_id": candidate["source_id"],
                        "url": url,
                        "published_at": published_at,
                    }
                )
            else:
                skipped.append({"url": url, "reason": "published_at not found"})
        except Exception as exc:  # noqa: BLE001
            failures.append({"url": url, "reason": str(exc)})

    return updates, skipped, failures


def _write_updates(driver: Any, updates: list[dict[str, str]], *, batch_size: int) -> int:
    """Write ``published_at`` updates to Neo4j."""
    if not updates:
        return 0

    updated = 0
    with driver.session() as session:
        for idx in range(0, len(updates), batch_size):
            batch = updates[idx : idx + batch_size]
            result = session.run(
                """
                UNWIND $rows AS row
                MATCH (s:Source {source_id: row.source_id})
                SET s.published_at = datetime(row.published_at)
                RETURN count(s) AS updated
                """,
                rows=batch,
            ).single()
            if result:
                updated += int(result["updated"])
    return updated


def run_backfill(args: argparse.Namespace) -> BackfillResult:
    """Run the published_at backfill workflow."""
    driver = create_driver(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
    )
    try:
        candidates = _fetch_candidates(
            driver,
            domains=args.domains,
            exclude_domains=args.exclude_domains,
            limit=args.limit,
        )
        updates, skipped, failures = _discover_updates(candidates, timeout=args.timeout)
        updated = 0
        if not args.dry_run:
            updated = _write_updates(driver, updates, batch_size=args.batch_size)

        result = BackfillResult(
            candidates=len(candidates),
            attempted=len(candidates),
            updated=updated if not args.dry_run else len(updates),
            skipped=len(skipped),
            failed=len(failures),
        )
        logger.info("Backfill result: %s", result)
        if skipped:
            logger.debug("Skipped sample (no date found): %s", skipped[:10])
        if failures:
            logger.info("Failure sample: %s", failures[:10])
        return result
    finally:
        driver.close()


def main() -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    result = run_backfill(args)
    print(
        json.dumps(
            {
                "candidates": result.candidates,
                "attempted": result.attempted,
                "updated": result.updated,
                "skipped": result.skipped,
                "failed": result.failed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
