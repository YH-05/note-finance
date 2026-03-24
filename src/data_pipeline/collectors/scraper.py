"""スクレイピングコレクター: サイトマップベースの記事収集.

MCP不要。Python単独で日次バッチ実行可能。
wealth-sitemap-config.json からサイトマップURLを解決し、
サイトマップから記事URLを取得、trafilatura で本文を取得する。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import requests
import trafilatura

from data_pipeline.collectors.base import (
    BaseCollector,
    CollectedItem,
    CollectionResult,
)
from data_pipeline.registry.models import DataSource

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
}


def _load_sitemap_config(
    config_dir: Path,
    config_file: str,
) -> list[dict[str, Any]]:
    """サイトマップ設定ファイルからサイト情報をロードする.

    JSON 形式の sitemap config のみ対応。YAML や Python スクリプトは非対応。
    """
    path = config_dir / config_file
    if not path.exists():
        return []
    # JSON 以外はスキップ
    if not config_file.endswith(".json"):
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sites", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _fetch_sitemap_urls(
    sitemap_url: str,
    *,
    max_urls: int = 20,
    exclude_patterns: list[str] | None = None,
    timeout: float = 10.0,
) -> list[dict[str, str]]:
    """サイトマップXMLから記事URLリストを取得する.

    Returns
    -------
    list[dict]
        各dict: {"url": str, "lastmod": str | None}
    """
    exclude = exclude_patterns or []
    try:
        resp = requests.get(
            sitemap_url,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    try:
        root = ElementTree.fromstring(resp.content)  # noqa: S314
    except ElementTree.ParseError:
        return []

    # サイトマップインデックスの場合、最初のサイトマップを取得
    sitemaps = root.findall("sm:sitemap/sm:loc", _SITEMAP_NS)
    if sitemaps:
        # インデックス → 最初のサブサイトマップを取得
        sub_url = sitemaps[0].text
        if sub_url:
            return _fetch_sitemap_urls(
                sub_url,
                max_urls=max_urls,
                exclude_patterns=exclude,
                timeout=timeout,
            )

    # 通常のサイトマップ
    urls: list[dict[str, str]] = []
    for url_elem in root.findall("sm:url", _SITEMAP_NS):
        loc = url_elem.find("sm:loc", _SITEMAP_NS)
        lastmod = url_elem.find("sm:lastmod", _SITEMAP_NS)
        if loc is None or not loc.text:
            continue
        url = loc.text.strip()

        # 除外パターンチェック
        if any(p in url for p in exclude):
            continue

        urls.append({
            "url": url,
            "lastmod": lastmod.text.strip() if lastmod is not None and lastmod.text else None,
        })

        if len(urls) >= max_urls:
            break

    return urls


def _fetch_article_text(url: str, timeout: float = 10.0) -> str | None:
    """trafilatura でURLから記事本文を取得する."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return None
        return trafilatura.extract(downloaded)
    except Exception:  # noqa: BLE001
        return None


class ScrapingCollector(BaseCollector):
    """サイトマップベースのスクレイピングコレクター.

    Parameters
    ----------
    config_dir : Path
        data/config/ ディレクトリのパス。
    max_articles_per_site : int
        1サイトあたりの最大記事取得数。
    request_delay : float
        記事取得間のリクエスト間隔（秒）。
    request_timeout : float
        HTTPリクエストのタイムアウト（秒）。

    Examples
    --------
    >>> collector = ScrapingCollector(config_dir=loader.config_dir)
    >>> result = collector.collect(source)
    """

    def __init__(
        self,
        config_dir: Path,
        *,
        max_articles_per_site: int = 10,
        request_delay: float = 1.0,
        request_timeout: float = 10.0,
    ) -> None:
        self.config_dir = config_dir
        self.max_articles_per_site = max_articles_per_site
        self.request_delay = request_delay
        self.request_timeout = request_timeout

    def collect(self, source: DataSource) -> CollectionResult:
        """サイトマップからスクレイピングで記事を収集する."""
        result = CollectionResult(source_id=source.source_id)

        sites = self._resolve_sites(source)
        if not sites:
            result.errors.append(
                f"No sites resolved for source '{source.source_id}'",
            )
            result.finish()
            return result

        for site in sites:
            try:
                items = self._scrape_site(source, site)
                result.items.extend(items)
            except Exception as e:  # noqa: BLE001
                result.errors.append(
                    f"Failed to scrape '{site.get('domain', '?')}': {e}",
                )

        result.finish()
        return result

    def _resolve_sites(self, source: DataSource) -> list[dict[str, Any]]:
        """DataSource からサイト一覧を解決する."""
        if source.config_ref is not None:
            sites = _load_sitemap_config(
                self.config_dir,
                source.config_ref.file,
            )
            if sites:
                return sites

        # url があれば単一サイトとして扱う
        if source.url:
            return [{
                "domain": source.url.split("//")[-1].split("/")[0],
                "sitemap_url": source.url.rstrip("/") + "/sitemap.xml",
                "exclude_patterns": [],
            }]

        return []

    def _scrape_site(
        self,
        source: DataSource,
        site: dict[str, Any],
    ) -> list[CollectedItem]:
        """1サイトのサイトマップから記事を収集する."""
        domain = site.get("domain", "")
        sitemap_url = site.get("sitemap_url", "")
        exclude = site.get("exclude_patterns", [])

        if not sitemap_url:
            return []

        # サイトマップからURL取得
        article_urls = _fetch_sitemap_urls(
            sitemap_url,
            max_urls=self.max_articles_per_site,
            exclude_patterns=exclude,
            timeout=self.request_timeout,
        )

        items: list[CollectedItem] = []
        for i, entry in enumerate(article_urls):
            if i > 0:
                time.sleep(self.request_delay)

            url = entry["url"]
            text = _fetch_article_text(url, timeout=self.request_timeout)
            if not text:
                continue

            # lastmod から published_at を推定
            published_at = None
            if entry.get("lastmod"):
                try:
                    published_at = datetime.fromisoformat(entry["lastmod"])
                except (ValueError, TypeError):
                    pass

            items.append(
                CollectedItem(
                    source_id=source.source_id,
                    url=url,
                    title=url.split("/")[-2] if url.endswith("/") else url.split("/")[-1],
                    raw_text=text,
                    published_at=published_at,
                    collection_method="scraping",
                    content_type="article",
                    metadata={
                        "domain": domain,
                        "sitemap_url": sitemap_url,
                        "source_key": site.get("source_key", domain),
                    },
                ),
            )

        return items
