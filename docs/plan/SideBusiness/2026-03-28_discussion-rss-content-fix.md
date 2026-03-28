# 議論メモ: RSS コンテンツ抽出修正（trafilatura Document 対応）

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

RSS スクレイパーで `--include-content` を有効化した際、記事本文の代わりに
ナビゲーションテキストや広告テキストが `content` フィールドに保存されていた。

CNBC の具体例:
- URL: `https://www.cnbc.com/select/reevaluating-the-new-bilt-credit-cards/`
- 保存内容: "Find the best credit card for you..." (373 文字のナビゲーション)
- 実際の記事: 20,312 文字

## 議論のサマリー

### 根本原因の特定

2層の問題が存在していた:

**問題1: trafilatura の戻り値型の変更**

`article_extractor.py` の `bare_extraction()` 呼び出し箇所で
`isinstance(raw_result, dict)` のみをチェックしていたが、
trafilatura の新バージョンは `dict` ではなく `Document` オブジェクトを返すため、
このチェックが常に `False` となり全記事が lxml fallback に落ちていた。

**問題2: lxml fallback 結果を content として保存**

`_rss_fetcher.py` と `unified.py` の `content_map` で、
lxml fallback 結果（`extraction_method="fallback"`）も content として保存していた。
lxml fallback はナビゲーションや広告テキストを抽出することがあるため不適切。

### 修正内容

**修正1: `src/rss/services/article_extractor.py`**

`bare_extraction()` の戻り値処理を拡張:
```python
# 旧: dict のみ対応
if isinstance(raw_result, dict):
    extracted_text = raw_result.get("text") or None
    extracted_meta = raw_result

# 新: Document オブジェクトにも対応
if isinstance(raw_result, dict):
    extracted_text = raw_result.get("text") or None
    extracted_meta = raw_result
elif raw_result is not None and hasattr(raw_result, "text"):
    extracted_text = getattr(raw_result, "text", None) or None
    extracted_meta = {
        "title": getattr(raw_result, "title", None),
        # ... その他フィールド
    }
```

**修正2: `src/news_scraper/_rss_fetcher.py` と `src/news_scraper/unified.py`**

`content_map` で trafilatura 結果のみを保存:
```python
# 旧: fallback 結果も保存
content_map = {r.url: r.text for r in extracted}

# 新: trafilatura のみ保存、fallback は None
content_map = {
    r.url: r.text if r.extraction_method.startswith("trafilatura") else None
    for r in extracted
}
```

### 修正後の動作確認

全9ソースで trafilatura による本文抽出が確認された:

| ソース | 確認内容 |
|--------|----------|
| ars_technica | trafilatura 抽出成功 |
| techcrunch | trafilatura 抽出成功 |
| zero_hedge | trafilatura 抽出成功 |
| federal_reserve | trafilatura 抽出成功 |
| hacker_news | trafilatura 抽出成功 |
| the_verge | trafilatura 抽出成功 |
| cnbc | trafilatura 抽出成功 |
| kabutan | trafilatura 抽出成功 |
| reuters_jp | trafilatura 抽出成功 |

テスト結果は NAS (`/Volumes/personal_folder/scraped/`) に保存済み。

## 決定事項

1. **lxml fallback 結果は content として保存しない**:
   - `_rss_fetcher.py` と `unified.py` の `content_map` を修正
   - `extraction_method` が `"trafilatura"` で始まる場合のみ保存
   - fallback は `None` として扱う

2. **trafilatura Document オブジェクト対応**:
   - `article_extractor.py` で `hasattr(raw_result, "text")` による分岐を追加
   - 旧バージョン（dict）・新バージョン（Document）どちらにも対応

## アクションアイテム

- [x] JETRO `--include-content` 動作確認（完了） (優先度: 高)
- [ ] `scripts/dedup_scraped.py` 実装（重複排除スクリプト） (優先度: 中)
- [ ] `scrape_jetro.py` と `scrape_finance_news.py --sources jetro` の統合検討 (優先度: 低)
- [ ] `config/launchd/com.note-finance.scrape-news.plist` をソース管理から削除するか判断 (優先度: 低)

## 次回の議論トピック

- `scripts/dedup_scraped.py` 実装（NAS 保存済みデータの重複排除）
- 既存の NAS データ（修正前に保存されたもの）の再取得要否判断
