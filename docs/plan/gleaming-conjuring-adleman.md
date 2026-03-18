# CNBC スクレイピング失敗の原因分析と対策プラン

## Context

2026-03-18 の `finance-news` ワークフロー実行で、512記事中 CNBC の記事が大量に「Body text too short or empty」エラーで失敗した。失敗は **100% CNBC ドメインに集中**しており、他サイト（BBC, TechCrunch, OpenAI 等）は正常に抽出できている。

## 原因分析

### 根本原因: CNBC は JavaScript レンダリングで記事本文を配信

CNBC は React/Next.js ベースの SPA であり、記事本文が JavaScript で動的にレンダリングされる。静的 HTML には本文が含まれない。

### 失敗の流れ

```
1. trafilatura.fetch_url() → 静的 HTML 取得
   → extracted length: 0 (algorithm) ← 本文が DOM にない

2. httpx + lxml フォールバック → 同じ静的 HTML を再取得
   → //*[contains(@id, 'article')] セレクタで 150-257 文字のみ抽出
   → これは記事の description スニペットのみ

3. RSS article_extractor → SUCCESS 判定（MIN_CONTENT_LENGTH=100 を超過）

4. News pipeline TrafilaturaExtractor → FAILED 判定
   → text_length < min_body_length(200) のため "Body text too short or empty"
```

### 数値的証拠

| 指標 | 値 |
|------|-----|
| RSS フィード数 | 30 |
| 収集記事総数 | 512 |
| Extraction failed 件数 | 100 エントリ（ユニーク URL 約50件、リトライ含む重複あり） |
| 失敗ドメイン | **100% cnbc.com** |
| CNBC フォールバック抽出テキスト長 | 153-257 文字（description スニペットのみ） |
| 非 CNBC フォールバック抽出テキスト長 | 2,000-66,000 文字（本文取得成功） |
| min_body_length 閾値 | 200 文字（`data/config/news-collection-config.yaml`） |

### コードパスの問題

`src/news/extractors/trafilatura.py:570-578` で、RSS extractor が SUCCESS を返した場合に text_length < 200 なら即座に FAILED を返している。この時点で **Playwright フォールバックが試行されていない**可能性がある。

## 対策案

### 案 A: Playwright フォールバックの確実な発火（推奨）

Playwright フォールバックは設定上 `enabled: true` だが、コードパス上で RSS extractor が SUCCESS（text >= 100）を返した際に、news pipeline 層で short text → FAILED のパスに入ると Playwright が試行されない。この分岐を修正し、text < min_body_length の場合に Playwright フォールバックを試行するようにする。

**修正ファイル**: `src/news/extractors/trafilatura.py`

```python
# 現状（L570-578）: SUCCESS だが短すぎる → 即 FAILED
if result.status == RssExtractionStatus.SUCCESS:
    if result.text is None or len(result.text) < self._min_body_length:
        return ExtractedArticle(..., FAILED, "Body text too short or empty")

# 修正案: Playwright フォールバックを試行してから判定
if result.status == RssExtractionStatus.SUCCESS:
    if result.text is None or len(result.text) < self._min_body_length:
        if self._playwright_enabled:
            playwright_result = await self._extract_with_playwright(article)
            if playwright_result and len(playwright_result.body_text or "") >= self._min_body_length:
                return playwright_result
        return ExtractedArticle(..., FAILED, "Body text too short or empty")
```

### 案 B: CNBC 専用セレクタの追加

`src/rss/services/article_extractor.py` の `ARTICLE_SELECTORS` に CNBC 固有のセレクタを追加。ただし CNBC は JS レンダリングのため、静的 HTML セレクタでは根本的解決にならない。**案 A と併用する場合のみ有効**。

```python
ARTICLE_SELECTORS = [
    # CNBC 専用（Playwright 経由でのみ有効）
    "//*[contains(@class, 'ArticleBody-articleBody')]",
    "//*[@data-module='ArticleBody']",
    # 既存セレクタ...
]
```

### 案 C: JS 必須ドメインリストの導入

`news-collection-config.yaml` に `playwright_required_domains` を追加し、該当ドメインは最初から Playwright で取得する。trafilatura → fallback の無駄な試行をスキップできる。

```yaml
extraction:
  playwright_fallback:
    enabled: true
    playwright_required_domains:
      - cnbc.com
```

### 案 D: CNBC をブロック対象に追加（暫定策）

`blocked_domains` に cnbc.com を追加し、RSS summary のみを利用する。本文抽出は諦め、要約ベースでの Issue 作成に切り替える。

## 推奨アプローチ

**案 A + 案 C の組み合わせ**

1. **案 A**: `trafilatura.py` の短テキスト判定後に Playwright フォールバックを試行する修正（根本修正）
2. **案 C**: CNBC 等の JS 必須ドメインは最初から Playwright を使う最適化（効率化）

### 実装順序

1. `src/news/extractors/trafilatura.py` — Playwright フォールバック分岐を修正
2. `src/news/config/models.py` — `playwright_required_domains` 設定を追加
3. `data/config/news-collection-config.yaml` — CNBC を Playwright 必須ドメインに追加
4. テスト: CNBC 記事 URL で抽出テスト

### 検証方法

```bash
# 単体テスト
uv run pytest tests/news/unit/extractors/test_trafilatura.py -v

# CNBC 記事の抽出テスト（手動）
uv run python -c "
import asyncio
from news.extractors.trafilatura import TrafilaturaExtractor
# CNBC テスト URL で抽出テスト
"

# 統合テスト（少数記事で workflow 実行）
uv run python -m news.scripts.finance_news_workflow --dry-run --limit 10
```
