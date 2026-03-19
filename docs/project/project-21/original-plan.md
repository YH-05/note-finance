# news_scraper コードベース改善計画

## Context

news_scraper を全6ソース（CNBC, NASDAQ, Kabutan, Reuters JP, Minkabu, JETRO）で実行テストした結果、以下の問題が発見された:

1. **パッケージ衝突**: 外部 `finance` 依存が `news_scraper` モジュールを含み、ローカル `src/news_scraper/` をシャドーイング
2. **スクリプト不具合**: `scrape_finance_news.py` が async 関数を同期呼び出し
3. **JETRO 修正未テスト**: セッション中に追加した新機能（カテゴリクロール、アーカイブクロール）にテストなし
4. **統合インターフェースの欠落**: unified.py が JETRO 固有パラメータを渡せない
5. **NASDAQ API 停止**: 全エンドポイントが 404
6. **Minkabu**: Playwright 必須だがデフォルト無効で 0 件

## Phase 1: パッケージ衝突の解消

### 1a. 外部 finance 依存を quants に切り替え

`finance` パッケージ（`YH-05/finance.git`）が `news_scraper/` をトップレベルに含むため衝突。

**影響調査結果**: `from finance` は3スクリプトの `get_logger` のみ:
- `scripts/validate_neo4j_schema.py:41`
- `scripts/skill_run_tracer.py:49`
- `scripts/migrate_skill_run_schema.py:36`

**変更**:
- `pyproject.toml` line 19: `"finance"` → `"quants"` に変更
- `pyproject.toml` line 160: `finance = { git = "..." }` → `quants = { git = "..." }` に変更
- 上記3スクリプト: `from finance.utils.logging_config` → `from quants.utils.logging_config` に変更
- `uv sync --all-extras` で再インストール → site-packages から `news_scraper/` ディレクトリが消えることを確認

### 1b. スクリプト側で sys.path を保険として設定

**変更**: `scripts/scrape_finance_news.py` 冒頭に追加:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
```

**対象ファイル**:
- `scripts/scrape_finance_news.py`
- `scripts/scrape_jetro.py`

## Phase 2: スクリプト async/sync 修正

`scripts/scrape_finance_news.py` の `main()` 関数が `collect_financial_news()` を同期呼び出ししている。

**変更箇所**: `scripts/scrape_finance_news.py`
- line 361: `df = collect_financial_news(...)` → `df = asyncio.run(collect_financial_news(...))`
- `import asyncio` を追加
- `--sources` choices に全6ソースを追加（現在は cnbc, nasdaq のみ）
- `DEFAULT_SOURCES` を `["cnbc"]` に変更（nasdaq は 404 のため除外）

## Phase 3: 壊れたテストの修正

セッション中の変更で既存テストが壊れている可能性あり。

**変更箇所**: `tests/news_scraper/unit/test_jetro_crawler.py`
- `_build_page_urls` のテスト: URL 末尾が `.html` → `/` に変わっているため、アサーション修正
- JETRO_CATEGORY_URLS が `/biznewstop/` → `/world/` に変わっているため、URL チェック修正

**変更箇所**: `tests/news_scraper/unit/test_jetro.py`
- `collect_news` の `regions` 引数型が `list[str]` → `dict[str, list[str]]` に変わっているため、該当テスト修正

**検証**: `uv run pytest tests/news_scraper/ -v`

## Phase 4: JETRO 新機能のテスト追加

セッション中に追加した5つの関数/メソッドにテストが0件。

### 4a. `_crawled_entry_to_article()` のテスト

**ファイル**: `tests/news_scraper/unit/test_jetro.py` に `TestCrawledEntryToArticle` クラス追加

テストケース（~8件）:
- 有効な CrawledEntry → Article 変換
- title/url 空で None 返却
- content_type が tags に反映
- metadata に feed_source/subcategory が含まれる
- 日本語日付のパース

### 4b. `_extract_entries_by_heading()` のテスト

**ファイル**: `tests/news_scraper/unit/test_jetro_crawler.py` に `TestExtractEntriesByHeading` クラス追加

テストケース（~8件）:
- h2 → div.elem_heading_lv2 → 次の兄弟 div から dt/dd を抽出
- 複数 h2 から異なる content_type を抽出
- 「もっと見る」リンクをスキップ
- 特集セクションの li > a フォールバック
- 外部ドメイン URL のスキップ
- h2 なし HTML で空リスト

HTML フィクスチャ: 実際の JETRO ページ構造を模倣したインライン文字列

### 4c. `_extract_archive_entries()` のテスト

**ファイル**: `tests/news_scraper/unit/test_jetro_crawler.py` に `TestExtractArchiveEntries` クラス追加

テストケース（~6件）:
- `li > div.date + div.title > span > a` 構造からの抽出
- div.date から公開日抽出
- div.title のない li をスキップ
- タイトル空の li をスキップ
- 空 HTML で空リスト

### 4d. `crawl_archive_pages()` のテスト

**ファイル**: `tests/news_scraper/unit/test_jetro_crawler.py` に `TestCrawlArchivePages` クラス追加

テストケース（~6件）:
- 単一ページからエントリ取得
- 複数ページで「次へ」ボタンクリック
- 「次へ」ボタンなしで停止
- max_pages で制限
- ページ読み込み失敗で空リスト

Playwright モック: 既存の `_make_mock_pw_context` パターンを再利用 + locator モック追加

### 4e. `collect_news` Phase 2/3 のテスト

**ファイル**: `tests/news_scraper/unit/test_jetro.py` に `TestCollectNewsPhase2`, `TestCollectNewsPhase3` クラス追加

テストケース（~6件）:
- categories 指定で Phase 2 実行
- ImportError で Playwright 未インストール警告
- archive_pages > 0 で Phase 3 実行
- archive_pages=0 で Phase 3 スキップ
- regions なしで Phase 3 スキップ

**検証**: `uv run pytest tests/news_scraper/ -v --tb=short`

## Phase 5: 統合インターフェース（unified.py）改善

JETRO 固有パラメータ（categories, regions, archive_pages）を unified.py 経由で渡せるようにする。

### 5a. ScraperConfig に source_options を追加

**ファイル**: `src/news_scraper/types.py`
```python
source_options: dict[str, dict[str, Any]] = Field(
    default_factory=dict,
    description="Per-source configuration (e.g., jetro: {categories, regions, archive_pages})",
)
```

### 5b. `_collect_jetro` を更新

**ファイル**: `src/news_scraper/unified.py`
```python
async def _collect_jetro(config: ScraperConfig) -> list[Article]:
    from news_scraper.jetro import collect_news as _collect
    jetro_opts = config.source_options.get("jetro", {})
    return await asyncio.to_thread(
        _collect,
        config=config,
        categories=jetro_opts.get("categories"),
        regions=jetro_opts.get("regions"),
        archive_pages=jetro_opts.get("archive_pages", 0),
    )
```

### 5c. スクリプトに CLI 引数追加

**ファイル**: `scripts/scrape_finance_news.py`
- `--jetro-categories` (nargs="+", choices=["world", "theme", "industry"])
- `--jetro-regions` (type=json.loads)
- `--jetro-archive-pages` (type=int, default=0)
- `--use-playwright` (action="store_true")

### 5d. テスト追加

**ファイル**: `tests/news_scraper/unit/test_unified.py`, `tests/news_scraper/unit/test_types.py`
- source_options のデフォルト空 dict
- jetro source_options が _collect_jetro に渡される

## Phase 6: NASDAQ 非推奨化 & Minkabu ドキュメント

### 6a. NASDAQ

**ファイル**: `src/news_scraper/nasdaq.py`
- `collect_news()` 冒頭に deprecation warning ログ追加
- `# AIDEV-TODO: NASDAQ API returns 404 as of 2026-03` コメント追加

**ファイル**: `src/news_scraper/unified.py`
- `_collect_nasdaq` にログ追加（API 非推奨の旨）

### 6b. Minkabu

**ファイル**: `src/news_scraper/unified.py`
- `_collect_minkabu` で `use_playwright=False` の場合 info ログ追加

---

## 実施順序と依存関係

```
Phase 1 (パッケージ衝突解消)
    ↓
Phase 2 (async 修正) ── Phase 3 (壊れたテスト修正) ← 並列可
    ↓
Phase 4 (新機能テスト追加)
    ↓
Phase 5 (unified 統合) ── Phase 6 (NASDAQ/Minkabu) ← 並列可
```

## 検証手順

1. `uv sync --all-extras` でパッケージ再インストール
2. `uv run python -c "from news_scraper._logging import get_logger"` で衝突解消確認
3. `make check-all` で全テスト通過
4. `uv run python scripts/scrape_finance_news.py --sources cnbc jetro --log-level INFO` で実行確認
5. JETRO アーカイブ: `uv run python scripts/scrape_finance_news.py --sources jetro --jetro-categories world --jetro-regions '{"asia": ["idn"]}' --jetro-archive-pages 2`

## 対象ファイル一覧

| ファイル | Phase | 変更内容 |
|---------|-------|---------|
| `pyproject.toml` | 1a | finance → quants |
| `scripts/validate_neo4j_schema.py` | 1a | import 修正 |
| `scripts/skill_run_tracer.py` | 1a | import 修正 |
| `scripts/migrate_skill_run_schema.py` | 1a | import 修正 |
| `scripts/scrape_finance_news.py` | 1b,2,5c | sys.path + async + CLI引数 |
| `scripts/scrape_jetro.py` | 1b | sys.path |
| `tests/news_scraper/unit/test_jetro_crawler.py` | 3,4b,4c,4d | テスト修正+追加 |
| `tests/news_scraper/unit/test_jetro.py` | 3,4a,4e | テスト修正+追加 |
| `src/news_scraper/types.py` | 5a | source_options 追加 |
| `src/news_scraper/unified.py` | 5b,6a,6b | JETRO passthrough + ログ |
| `src/news_scraper/nasdaq.py` | 6a | deprecation warning |
| `tests/news_scraper/unit/test_unified.py` | 5d | テスト追加 |
| `tests/news_scraper/unit/test_types.py` | 5d | テスト追加 |
