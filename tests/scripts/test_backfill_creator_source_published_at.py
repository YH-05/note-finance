"""Tests for creator Source.published_at backfill helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts.backfill_creator_source_published_at import (
    _discover_updates,
    _extract_from_jsonld,
    _extract_from_meta,
    _extract_from_reddit,
    _extract_from_time,
    _iter_json_objects,
    extract_published_at,
    parse_args,
)


# ---------------------------------------------------------------------------
# _iter_json_objects
# ---------------------------------------------------------------------------


class TestIterJsonObjects:
    def test_正常系_dictを単一要素リストに変換できる(self) -> None:
        obj = {"datePublished": "2026-01-01"}
        assert _iter_json_objects(obj) == [obj]

    def test_正常系_listのdictを展開できる(self) -> None:
        objs = [{"a": 1}, {"b": 2}]
        assert _iter_json_objects(objs) == objs

    def test_正常系_graphキーを再帰展開できる(self) -> None:
        payload = {
            "@context": "https://schema.org",
            "@graph": [{"datePublished": "2026-03-01"}, {"name": "test"}],
        }
        result = _iter_json_objects(payload)
        # root dict + 2 graph items
        assert len(result) == 3
        assert {"datePublished": "2026-03-01"} in result

    def test_正常系_ネストしたgraphを再帰展開できる(self) -> None:
        payload = {"@graph": [{"@graph": [{"datePublished": "2026-01-15"}]}]}
        result = _iter_json_objects(payload)
        assert {"datePublished": "2026-01-15"} in result

    def test_正常系_スカラー値は空リストを返す(self) -> None:
        assert _iter_json_objects("string") == []
        assert _iter_json_objects(42) == []
        assert _iter_json_objects(None) == []


# ---------------------------------------------------------------------------
# _extract_from_jsonld
# ---------------------------------------------------------------------------


class TestExtractFromJsonld:
    def test_正常系_datePublishedを抽出できる(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@context":"https://schema.org","datePublished":"2026-03-26T10:00:00+09:00"}
        </script>
        """
        assert _extract_from_jsonld(html) == "2026-03-26T10:00:00+09:00"

    def test_正常系_dateCreatedにフォールバックできる(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@context":"https://schema.org","dateCreated":"2026-03-25T00:00:00Z"}
        </script>
        """
        assert _extract_from_jsonld(html) == "2026-03-25T00:00:00Z"

    def test_正常系_uploadDateにフォールバックできる(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type":"VideoObject","uploadDate":"2026-03-24"}
        </script>
        """
        assert _extract_from_jsonld(html) == "2026-03-24"

    def test_正常系_datePublishedがdateCreatedより優先される(self) -> None:
        html = """
        <script type="application/ld+json">
        {"datePublished":"2026-03-26","dateCreated":"2026-01-01"}
        </script>
        """
        assert _extract_from_jsonld(html) == "2026-03-26"

    def test_正常系_graphブロックから抽出できる(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@graph":[{"@type":"Article","datePublished":"2026-03-10T09:00:00Z"}]}
        </script>
        """
        assert _extract_from_jsonld(html) == "2026-03-10T09:00:00Z"

    def test_正常系_配列形式のJSONLDから抽出できる(self) -> None:
        html = """
        <script type="application/ld+json">
        [{"@type":"WebPage"},{"@type":"Article","datePublished":"2026-02-15"}]
        </script>
        """
        assert _extract_from_jsonld(html) == "2026-02-15"

    def test_正常系_不正なJSONはスキップされる(self) -> None:
        html = """
        <script type="application/ld+json">INVALID JSON</script>
        <script type="application/ld+json">{"datePublished":"2026-03-01"}</script>
        """
        assert _extract_from_jsonld(html) == "2026-03-01"

    def test_正常系_該当なしはNoneを返す(self) -> None:
        html = '<script type="application/ld+json">{"name":"test"}</script>'
        assert _extract_from_jsonld(html) is None

    def test_正常系_スクリプトタグなしはNoneを返す(self) -> None:
        assert _extract_from_jsonld("<html><body></body></html>") is None


# ---------------------------------------------------------------------------
# _extract_from_meta
# ---------------------------------------------------------------------------


class TestExtractFromMeta:
    def test_正常系_article_published_timeを抽出できる(self) -> None:
        html = '<meta property="article:published_time" content="2026-03-25T12:34:56+00:00">'
        assert _extract_from_meta(html) == "2026-03-25T12:34:56+00:00"

    def test_正常系_og_published_timeを抽出できる(self) -> None:
        html = '<meta property="og:published_time" content="2026-03-20">'
        assert _extract_from_meta(html) == "2026-03-20"

    def test_正常系_parsely_pub_dateを抽出できる(self) -> None:
        html = '<meta name="parsely-pub-date" content="2026-01-10T00:00:00">'
        assert _extract_from_meta(html) == "2026-01-10T00:00:00"

    def test_正常系_dc_dateを抽出できる(self) -> None:
        html = '<meta name="dc.date" content="2025-12-31">'
        assert _extract_from_meta(html) == "2025-12-31"

    def test_正常系_contentが空のタグはスキップされる(self) -> None:
        html = '<meta property="article:published_time" content="">'
        assert _extract_from_meta(html) is None

    def test_正常系_該当なしはNoneを返す(self) -> None:
        html = '<meta name="description" content="some description">'
        assert _extract_from_meta(html) is None


# ---------------------------------------------------------------------------
# _extract_from_time
# ---------------------------------------------------------------------------


class TestExtractFromTime:
    def test_正常系_time_datetimeを抽出できる(self) -> None:
        html = '<time datetime="2026-03-24T08:00:00+09:00">March 24</time>'
        assert _extract_from_time(html) == "2026-03-24T08:00:00+09:00"

    def test_正常系_datetimeなしはNoneを返す(self) -> None:
        html = "<time>March 24</time>"
        assert _extract_from_time(html) is None


# ---------------------------------------------------------------------------
# _extract_from_reddit
# ---------------------------------------------------------------------------


class TestExtractFromReddit:
    def test_正常系_created_timestampを抽出できる(self) -> None:
        html = '<shreddit-post created-timestamp="2026-03-23T01:02:03.000Z"></shreddit-post>'
        assert _extract_from_reddit(html) == "2026-03-23T01:02:03.000Z"

    def test_正常系_該当なしはNoneを返す(self) -> None:
        assert _extract_from_reddit("<html></html>") is None


# ---------------------------------------------------------------------------
# extract_published_at (優先度・統合)
# ---------------------------------------------------------------------------


class TestExtractPublishedAt:
    def test_正常系_jsonld_datePublishedを抽出できる(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","datePublished":"2026-03-26T10:00:00+09:00"}
        </script>
        </head></html>
        """
        assert extract_published_at(html) == "2026-03-26T10:00:00+09:00"

    def test_正常系_meta_article_published_timeを抽出できる(self) -> None:
        html = """
        <html><head>
        <meta property="article:published_time" content="2026-03-25T12:34:56+00:00">
        </head></html>
        """
        assert extract_published_at(html) == "2026-03-25T12:34:56+00:00"

    def test_正常系_time_datetimeを抽出できる(self) -> None:
        html = '<html><body><time datetime="2026-03-24T08:00:00+09:00"></time></body></html>'
        assert extract_published_at(html) == "2026-03-24T08:00:00+09:00"

    def test_正常系_reddit_created_timestampを抽出できる(self) -> None:
        html = '<shreddit-post created-timestamp="2026-03-23T01:02:03.000Z"></shreddit-post>'
        assert extract_published_at(html, domain="reddit.com") == "2026-03-23T01:02:03.000Z"

    def test_正常系_値が無ければNone(self) -> None:
        html = "<html><head><title>No date</title></head></html>"
        assert extract_published_at(html) is None

    def test_正常系_jsonldがmetaより優先される(self) -> None:
        html = """
        <script type="application/ld+json">{"datePublished":"2026-03-26"}</script>
        <meta property="article:published_time" content="2026-01-01">
        """
        assert extract_published_at(html) == "2026-03-26"

    def test_正常系_metaがtimeより優先される(self) -> None:
        html = """
        <meta property="article:published_time" content="2026-03-25">
        <time datetime="2026-01-01"></time>
        """
        assert extract_published_at(html) == "2026-03-25"

    def test_正常系_redditはdomain指定なしでは無視される(self) -> None:
        html = '<shreddit-post created-timestamp="2026-03-23T01:02:03.000Z"></shreddit-post>'
        assert extract_published_at(html) is None

    def test_正常系_redditはdomain不一致でも無視される(self) -> None:
        html = '<shreddit-post created-timestamp="2026-03-23T01:02:03.000Z"></shreddit-post>'
        assert extract_published_at(html, domain="example.com") is None


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_デフォルト値が設定される(self) -> None:
        args = parse_args([])
        assert args.neo4j_uri == "bolt://localhost:7689"
        assert args.neo4j_user == "neo4j"
        assert args.limit is None
        assert args.batch_size == 100
        assert args.timeout == 20
        assert args.domains is None
        assert args.exclude_domains is None
        assert args.dry_run is False

    def test_正常系_limitを指定できる(self) -> None:
        args = parse_args(["--limit", "50"])
        assert args.limit == 50

    def test_正常系_domainを複数指定できる(self) -> None:
        args = parse_args(["--domain", "reuters.com", "--domain", "bloomberg.com"])
        assert args.domains == ["reuters.com", "bloomberg.com"]

    def test_正常系_exclude_domainを指定できる(self) -> None:
        args = parse_args(["--exclude-domain", "reddit.com"])
        assert args.exclude_domains == ["reddit.com"]

    def test_正常系_dry_runフラグを設定できる(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_正常系_batch_sizeを指定できる(self) -> None:
        args = parse_args(["--batch-size", "50"])
        assert args.batch_size == 50


# ---------------------------------------------------------------------------
# _discover_updates
# ---------------------------------------------------------------------------


class TestDiscoverUpdates:
    def _make_candidate(
        self,
        source_id: str = "src-1",
        url: str = "https://example.com/article",
        domain: str | None = None,
    ) -> dict[str, str]:
        c: dict[str, str] = {"source_id": source_id, "url": url}
        if domain is not None:
            c["domain"] = domain
        return c

    def test_正常系_日付抽出成功はupdatesに入る(self) -> None:
        html = '<script type="application/ld+json">{"datePublished":"2026-03-26"}</script>'
        mock_resp = MagicMock()
        mock_resp.text = html

        with patch(
            "scripts.backfill_creator_source_published_at.requests.Session.get",
            return_value=mock_resp,
        ):
            updates, skipped, failures = _discover_updates(
                [self._make_candidate()], timeout=5
            )

        assert len(updates) == 1
        assert updates[0]["published_at"] == "2026-03-26"
        assert skipped == []
        assert failures == []

    def test_正常系_日付なしページはskippedに入る(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>No date here</body></html>"

        with patch(
            "scripts.backfill_creator_source_published_at.requests.Session.get",
            return_value=mock_resp,
        ):
            updates, skipped, failures = _discover_updates(
                [self._make_candidate()], timeout=5
            )

        assert updates == []
        assert len(skipped) == 1
        assert skipped[0]["reason"] == "published_at not found"
        assert failures == []

    def test_正常系_HTTPエラーはfailuresに入る(self) -> None:
        import requests as req

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("404")

        with patch(
            "scripts.backfill_creator_source_published_at.requests.Session.get",
            return_value=mock_resp,
        ):
            updates, skipped, failures = _discover_updates(
                [self._make_candidate()], timeout=5
            )

        assert updates == []
        assert skipped == []
        assert len(failures) == 1

    def test_正常系_ネットワークエラーはfailuresに入る(self) -> None:
        import requests as req

        with patch(
            "scripts.backfill_creator_source_published_at.requests.Session.get",
            side_effect=req.ConnectionError("timeout"),
        ):
            updates, skipped, failures = _discover_updates(
                [self._make_candidate()], timeout=5
            )

        assert updates == []
        assert skipped == []
        assert len(failures) == 1

    def test_正常系_複数candidateを独立して処理できる(self) -> None:
        html_with_date = (
            '<script type="application/ld+json">{"datePublished":"2026-01-01"}</script>'
        )
        html_no_date = "<html><body>no date</body></html>"

        responses = [
            MagicMock(text=html_with_date),
            MagicMock(text=html_no_date),
        ]

        with patch(
            "scripts.backfill_creator_source_published_at.requests.Session.get",
            side_effect=responses,
        ):
            updates, skipped, failures = _discover_updates(
                [
                    self._make_candidate("s1", "https://a.com/1"),
                    self._make_candidate("s2", "https://a.com/2"),
                ],
                timeout=5,
            )

        assert len(updates) == 1
        assert len(skipped) == 1
        assert failures == []
