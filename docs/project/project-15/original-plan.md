# 日本株ニュース HTMLスクレイパー追加

## Context

`rss-presets-jp.json` に日本株ニュースソースを追加する際、RSS非提供の3サイト（株探・ロイター日本語版・みんかぶ）をカバーするためHTMLスクレイパーを `src/news_scraper/` に追加する。既存の CNBC/NASDAQ スクレイパーと同じ `collect_news()` インターフェースに従い、`unified.py` の `SOURCE_REGISTRY` に統合する。

## 対象サイト

| サイト | 方式 | 難易度 | 優先度 |
|--------|------|--------|--------|
| 株探 (`kabutan.jp`) | httpx + lxml (SSR, テーブルHTML) | 低 | 最高 |
| ロイター日本語版 (`jp.reuters.com`) | httpx + lxml (SSR/SPA混合) | 中 | 高 |
| みんかぶ (`minkabu.jp`) | Playwright + lxml (SPA) | 高 | 中 |

## ファイル構成

### 新規作成 (7ファイル)

```
src/news_scraper/
├── _html_utils.py        # 共通HTMLパースユーティリティ
├── kabutan.py             # 株探スクレイパー
├── reuters_jp.py          # ロイター日本語版スクレイパー
└── minkabu.py             # みんかぶスクレイパー

tests/news_scraper/unit/
├── test_html_utils.py
├── test_kabutan.py
├── test_reuters_jp.py
└── test_minkabu.py
```

### 変更 (2ファイル)

| ファイル | 変更内容 |
|---------|---------|
| `src/news_scraper/types.py:32` | `SourceName` Literal に `"kabutan"`, `"reuters_jp"`, `"minkabu"` 追加 |
| `src/news_scraper/unified.py:40-57` | `SOURCE_REGISTRY` に3ソースの遅延インポートラッパー追加 |

## 設計詳細

### 共通ユーティリティ `_html_utils.py`

```python
def fetch_html(url, config, headers=None) -> str    # httpx GET + timeout + User-Agent
def parse_html(html_content) -> HtmlElement          # lxml.html.fromstring
def extract_text(element, xpath) -> str | None       # XPath テキスト抽出
def extract_attr(element, xpath, attr) -> str | None # XPath 属性抽出
def resolve_relative_url(relative, base) -> str      # urljoin ラッパー
def rate_limit_sleep(config) -> None                 # request_delay 分 sleep
```

### kabutan.py（株探）

- **URL**: `https://kabutan.jp/news/marketnews/`
- **HTML構造**: `<tr>` テーブル行 → `td[1]`=日時, `td[2]`=タイプ, `td[last()]//a`=タイトル+URL
- **日付パース**: `MM/DD HH:MM` (JST) → UTC変換、年は推定
- **レート制限**: `config.request_delay` (デフォルト1.0s)
- **ヘッダー**: ブラウザ風 User-Agent + `Accept-Language: ja`

```python
def collect_news(config=None) -> list[Article]:
    # 1. fetch_html(KABUTAN_NEWS_URL)
    # 2. parse_html → XPath で <tr> 行を取得
    # 3. 各行から _row_to_article() で Article 生成
    # 4. max_articles_per_source で制限
```

### reuters_jp.py（ロイター日本語版）

- **URL**: `https://jp.reuters.com/markets/`, `/business/`
- **robots.txt**: AI系ボット制限あり → ブラウザ風 User-Agent 使用
- **HTML構造**: `<article>` or `div.story-card` 内の `<a>` + `<h3>` + `<time>`
- **レート制限**: 推奨 2.0s
- **SPA対応**: 初回は httpx + lxml のみ。記事0件なら警告ログ（Playwright拡張は将来）

```python
def collect_news(config=None, sections=None) -> list[Article]:
    # 1. 各セクション並列取得 (ThreadPoolExecutor)
    # 2. HTML パース → 記事カード抽出
    # 3. SSR不足時は警告ログ
```

### minkabu.py（みんかぶ）

- **URL**: `https://minkabu.jp/news`
- **SPA**: JavaScript必須 → Playwright で DOM レンダリング
- **ページネーション**: 無限スクロール → scroll + wait パターン
- **Graceful degradation**: Playwright未インストール時は空リスト + 警告ログ

```python
def collect_news(config=None) -> list[Article]:
    # 1. config.use_playwright チェック
    # 2. Playwright でページ取得 → scroll で追加読み込み
    # 3. page.content() → lxml パース
    # 4. max_articles_per_source で制限
```

### unified.py 変更

```python
# 遅延インポートラッパー追加（既存パターン踏襲）
def _collect_kabutan(config): ...
def _collect_reuters_jp(config): ...
def _collect_minkabu(config): ...

SOURCE_REGISTRY = {
    "cnbc": _collect_cnbc,
    "nasdaq": _collect_nasdaq,
    "kabutan": _collect_kabutan,       # NEW
    "reuters_jp": _collect_reuters_jp, # NEW
    "minkabu": _collect_minkabu,       # NEW
}
```

**デフォルト sources は `["cnbc", "nasdaq"]` のまま変更しない**（既存動作を壊さない）。日本ソースは `sources=["kabutan"]` のように明示指定で使用。

## 再利用する既存コード

| 用途 | ファイル |
|------|---------|
| 型定義 | `src/news_scraper/types.py` — Article, ScraperConfig, deduplicate_by_url |
| ロギング | `src/news_scraper/_logging.py` — get_logger() |
| パターン参考 | `src/news_scraper/nasdaq.py` — httpx.Client, ThreadPoolExecutor, _row_to_article |
| 統合 | `src/news_scraper/unified.py` — SOURCE_REGISTRY, 遅延インポート |

## 実装順序（3 Phase）

### Phase 1: Foundation + 株探（最小リスク・最大価値）

1. `_html_utils.py` + `test_html_utils.py` 作成（TDD）
2. `kabutan.py` + `test_kabutan.py` 作成（TDD）
3. `types.py` に `"kabutan"` 追加
4. `unified.py` に kabutan 登録
5. `make check-all`

### Phase 2: ロイター日本語版

1. `reuters_jp.py` + `test_reuters_jp.py` 作成（TDD）
2. `types.py` に `"reuters_jp"` 追加
3. `unified.py` に reuters_jp 登録
4. `make check-all`

### Phase 3: みんかぶ

1. `minkabu.py` + `test_minkabu.py` 作成（TDD）
2. `types.py` に `"minkabu"` 追加
3. `unified.py` に minkabu 登録
4. `make check-all`

## テスト計画

各スクレイパーのテストは httpx/Playwright を mock して実際のHTTP通信なしで実行。日本語テスト名を使用。

### test_kabutan.py 主要テスト

```
test_正常系_日付文字列をJSTからUTCに変換
test_正常系_テーブル行からArticleを生成
test_正常系_collect_newsがArticleリストを返す (mock httpx)
test_正常系_max_per_sourceで記事数を制限
test_異常系_HTTPエラーで空リストを返す
test_エッジケース_年をまたぐ日付を正しく処理
```

### test_reuters_jp.py 主要テスト

```
test_正常系_ISO8601日付をパース
test_正常系_HTMLから記事カードを抽出
test_正常系_複数セクションを並列収集
test_異常系_JS要求ページで空リストと警告
```

### test_minkabu.py 主要テスト

```
test_正常系_レンダリング済みHTMLから記事を抽出
test_正常系_collect_newsがArticleリストを返す (mock Playwright)
test_異常系_Playwright未インストールで空リスト
```

## 検証方法

```bash
# 自動テスト
uv run pytest tests/news_scraper/ -v

# 型チェック + lint + format
make check-all

# 手動スモークテスト（Phase別）
uv run python -c "
from news_scraper.unified import collect_financial_news
from news_scraper.types import ScraperConfig
config = ScraperConfig(max_articles_per_source=5)
df = collect_financial_news(sources=['kabutan'], config=config)
print(f'Kabutan: {len(df)} articles')
for a in df:
    print(f'  {a.published} | {a.title[:50]}')
"
```

## リスクと対策

| リスク | 対策 |
|--------|------|
| 株探のHTML構造変更 | XPathセレクタをモジュール定数化。記事0件時に警告ログ |
| ロイターがスクレイピングブロック | ブラウザ風UA + 2s遅延。空リストで graceful degradation |
| ロイターのSPA部分が取得不可 | 初回はSSRのみ実装。将来Playwright拡張可能な設計 |
| みんかぶの無限スクロール | scroll回数を max_articles_per_source で制限。タイムアウト保護 |
| Playwright未インストール | try/except ImportError で空リスト返却 |
| 日本語日付パースのエッジケース | 包括的テスト + fallback to datetime.now(UTC) |
