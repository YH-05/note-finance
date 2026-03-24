---
name: site-investigator
description: >
  新しいサイトのスクレイピング前調査スキル。browser-use CLI 2.0 でサイトにアクセスし、
  ページ構造・セレクタ・ページネーション・RSS/サイトマップ・動的挙動を自動解析して
  JSON + Markdown レポートを生成する。
  ハイブリッド方式: 調査は browser-use CLI（トークン効率優先）、検証は Playwright MCP。
  「サイト調査」「サイト構造を調べて」「スクレイピング前に構造を確認」「このURLの構造を解析」
  「セレクタを特定して」「ページネーションの仕組みを調べて」「RSSがあるか確認」
  と言われたら必ずこのスキルを使うこと。
  新しいサイトへのスクレイピング実装を始める前にプロアクティブに使用すること。
---

# site-investigator スキル

未知のサイトを体系的に調査し、スクレイピングに必要な構造情報をまとめるスキル。

**ハイブリッド方式**:
- **Phase 1-5（調査）**: browser-use CLI 2.0 を Bash 経由で使用（トークン効率優先）
- **検証フェーズ（オプション）**: Playwright MCP でセレクタの詳細テスト

## 前提条件

- browser-use CLI がインストール済みであること
  - インストール: `curl -fsSL https://browser-use.com/cli/install.sh | bash`
  - venv: `~/.browser-use-env/`
- Playwright MCP が Claude Code に設定済みであること（検証フェーズ用、オプション）

## 使い方

```
/site-investigator https://example.com/blog
```

引数としてサイトの URL を受け取り、5 Phase の調査を実行する。

## browser-use CLI 基本コマンド

Phase 1-5 では全て Bash 経由で CLI コマンドを実行する。
browser-use はデーモンアーキテクチャ（~50ms レイテンシ）でセッションを維持する。

**重要**: 全コマンドの先頭に venv のアクティベーションが必要:

```bash
source ~/.browser-use-env/bin/activate && browser-use <command>
```

### ナビゲーション

```bash
browser-use open <url>              # URL にアクセス（ブラウザ起動 + ナビゲーション）
browser-use back                    # 履歴を戻る
browser-use scroll down             # 下にスクロール
browser-use scroll up               # 上にスクロール
browser-use scroll down --amount 1000  # ピクセル指定スクロール
```

### ページ状態の取得

```bash
browser-use state                   # URL, タイトル, クリック可能要素一覧（index付き）
browser-use screenshot <path>.png   # スクリーンショット保存
browser-use screenshot --full <path>.png  # フルページスクリーンショット
browser-use get title               # ページタイトル
browser-use get html                # 全 HTML
browser-use get html --selector "h1"  # セレクタ指定で HTML 取得
browser-use get text <index>        # 要素テキスト取得
browser-use get attributes <index>  # 要素の全属性取得
```

### インタラクション

```bash
browser-use click <index>           # index で要素をクリック（state の出力から取得）
browser-use type "text"             # フォーカス要素にテキスト入力
browser-use input <index> "text"    # 要素を選択してテキスト入力
browser-use keys "Enter"            # キー送信
browser-use select <index> "value"  # ドロップダウン選択
```

### JavaScript 実行

```bash
browser-use eval 'document.title'                    # 単純な式
browser-use eval 'JSON.stringify({...})'             # オブジェクトは JSON.stringify 必須
browser-use eval 'document.querySelectorAll("a").length'  # DOM クエリ
```

### 待機

```bash
browser-use wait selector ".loading" --state hidden  # 要素消滅待機
browser-use wait text "Success"                      # テキスト出現待機
browser-use wait selector "h1" --timeout 5000        # タイムアウト指定
```

### セッション管理

```bash
browser-use --session NAME open <url>   # 名前付きセッション
browser-use sessions                    # アクティブセッション一覧
browser-use close                       # 現在セッションを閉じる
browser-use close --all                 # 全セッション終了
```

### state の出力例

```
viewport: 1710x1107
page: 1710x3200
scroll: (0, 0)
Example Blog - Latest Posts
[0]<a />  Home
[1]<a />  About
[2]<a />  Contact
[3]<article />
  [4]<a />  Article Title 1
  [5]<time />  2026-03-20
[6]<article />
  [7]<a />  Article Title 2
  [8]<time />  2026-03-19
[9]<a />  Next Page →
```

`[N]` が index。`click <index>` でクリックできる。

## 調査プロトコル（5 Phase）

各 Phase を順番に実行する。Phase 間で得た情報を蓄積しながら進める。
詳細なチェック項目は `references/investigation-checklist.md` を参照。

ファイル保存先のベースディレクトリ: `.tmp/site-reports/{domain}/`

### Phase 1: 初回アクセス・概要把握

**目的**: サイトの第一印象を掴み、基本情報を収集する。

1. ブラウザを開いて対象 URL にアクセス:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use open {url}
   ```

2. スクリーンショットを保存:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use screenshot .tmp/site-reports/{domain}/screenshots/phase1-home.png
   ```

3. ページ状態を取得:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use state
   ```
   - `state` の出力からページ種別・クリック可能要素を把握

4. 出力から以下を判定:
   - ページ種別（一覧 / 単体記事 / トップページ / SPA）
   - 言語（日本語 / 英語 / 他）
   - CMS/フレームワーク推定（WordPress, Next.js, etc.）

5. Cookie 同意バナーやポップアップがあれば:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use click <index>
   ```
   （index は `state` 出力の「Accept」「同意」ボタンの番号）

**判定ロジック**: `state` の出力で `<article>` 要素の繰り返しがあれば一覧ページ、
単一の長い `<article>` なら個別記事ページ、と判断する。

### Phase 2: メタ情報の収集

**目的**: スクレイピングの最適手段（RSS / サイトマップ / 直接）を判断する材料を集める。

1. **RSS フィード検出**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify(Array.from(document.querySelectorAll("link[type=\"application/rss+xml\"], link[type=\"application/atom+xml\"]")).map(f => ({ href: f.href, title: f.title })))'
   ```
   - 見つからない場合、以下のパスを順に試す:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use open {base_url}/feed
   source ~/.browser-use-env/bin/activate && browser-use open {base_url}/rss
   source ~/.browser-use-env/bin/activate && browser-use open {base_url}/feed.xml
   ```

2. **サイトマップ検出**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use open {base_url}/sitemap.xml
   source ~/.browser-use-env/bin/activate && browser-use get html
   ```
   - 404 なら `/sitemap_index.xml`, `/sitemap/` も試す

3. **robots.txt 確認**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use open {base_url}/robots.txt
   source ~/.browser-use-env/bin/activate && browser-use get html
   ```
   - Disallow ルール、Crawl-delay、Sitemap 指定を抽出

4. **meta タグ収集**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use open {url}
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify(Array.from(document.querySelectorAll("meta")).map(m => ({ name: m.name || m.getAttribute("property"), content: m.content })))'
   ```

### Phase 3: 一覧ページの構造解析

**目的**: 記事一覧のセレクタとページネーション方式を特定する。

Phase 1 で一覧ページと判定された場合（または一覧ページに遷移して）実行。

1. ページ状態から繰り返し構造を発見:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use open {list_page_url}
   source ~/.browser-use-env/bin/activate && browser-use state
   ```
   - `state` 出力で同じ構造の `<article>`, `<a>` が並んでいるパターンを探す
   - 各アイテム内のタイトル（リンク）、日付、サムネイル、著者を特定

2. セレクタの検証:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify({ count: document.querySelectorAll("article.post-card").length, sample: document.querySelector("article.post-card")?.textContent?.substring(0, 100) })'
   ```

3. 特定要素の HTML を直接取得:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use get html --selector "nav.pagination"
   source ~/.browser-use-env/bin/activate && browser-use get html --selector "article:first-of-type"
   ```

4. ページネーション方式の特定:
   - `state` 出力で `Next`, `次へ`, `→` 等のリンクを探す
   - 方式を判定:
     - **numbered**: `?page=2` や `/page/2/` 形式のリンク
     - **next/prev**: 「次へ」「前へ」ボタン
     - **infinite scroll**: スクロールで追加読み込み
     - **load more**: 「もっと見る」ボタン
   - infinite scroll の検出:
     ```bash
     source ~/.browser-use-env/bin/activate && browser-use scroll down
     source ~/.browser-use-env/bin/activate && browser-use state
     ```
     （スクロール後に新しい要素が増えていれば infinite scroll）

5. URL パターンの分析:
   - 記事リンクの href から URL パターンを抽出
   - 例: `/blog/{slug}`, `/articles/{id}`, `/{year}/{month}/{slug}`

### Phase 4: 個別コンテンツページの構造解析

**目的**: 記事ページの各要素のセレクタを特定する。

1. Phase 3 で見つけた記事リンクの 1 つをクリック:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use click <index>
   ```

2. 記事ページの状態を取得:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use state
   source ~/.browser-use-env/bin/activate && browser-use screenshot .tmp/site-reports/{domain}/screenshots/phase4-article.png
   ```

3. 主要要素の HTML を取得:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use get html --selector "h1"
   source ~/.browser-use-env/bin/activate && browser-use get html --selector "article"
   source ~/.browser-use-env/bin/activate && browser-use get html --selector "time"
   source ~/.browser-use-env/bin/activate && browser-use get html --selector "[rel=author]"
   ```

4. 以下の要素を特定:
   - **タイトル**: 通常 `h1` 要素
   - **本文**: `article`, `div.content`, `div.entry-content` 等のコンテナ
   - **公開日**: `time` 要素、`datetime` 属性
   - **著者**: `a[rel="author"]`, `.author` 等
   - **カテゴリ/タグ**: カテゴリリンク、タグクラウド
   - **関連記事**: 記事下部のリンクリスト
   - **コメント欄**: 有無の確認

5. ペイウォール/ログイン壁の検出:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify({ paywallOverlay: !!document.querySelector("[class*=\"paywall\"], [class*=\"subscribe\"], [id*=\"paywall\"]"), loginModal: !!document.querySelector("[class*=\"login-modal\"], [class*=\"signin\"]"), bodyLength: document.querySelector("article")?.textContent?.length || 0 })'
   ```

### Phase 5: 動的挙動の検出

**目的**: JavaScript 依存度と API エンドポイントを把握する。

1. **SPA / CSR 判定**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify({ hasReact: !!document.querySelector("[data-reactroot], #__next"), hasVue: !!document.querySelector("[data-v-], #__nuxt"), hasAngular: !!document.querySelector("[ng-version], [_nghost]"), bodyTextLength: document.body.innerText.length })'
   ```

2. **lazy load 検出**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify({ lazyImages: document.querySelectorAll("img[loading=\"lazy\"], img[data-src]").length, totalImages: document.querySelectorAll("img").length })'
   ```

3. **パフォーマンス情報**:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use eval 'JSON.stringify({ protocol: performance.getEntriesByType("navigation")[0]?.nextHopProtocol, domContentLoaded: Math.round(performance.getEntriesByType("navigation")[0]?.domContentLoadedEventEnd), transferSize: Math.round(performance.getEntriesByType("navigation")[0]?.transferSize / 1024) + "KB" })'
   ```

4. ブラウザを閉じる:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use close
   ```

## 検証フェーズ（オプション）

Phase 1-5 完了後、ユーザーがセレクタの詳細検証を求めた場合や、
実装状況がわかってきた段階で Playwright MCP に切り替えて詳細テストを行う。

### 切り替え手順

1. browser-use セッションが開いていれば閉じる:
   ```bash
   source ~/.browser-use-env/bin/activate && browser-use close
   ```

2. Playwright MCP でページにアクセス:
   - `mcp__playwright__browser_navigate` で対象ページに遷移

### 検証項目

1. **セレクタの正確性テスト**:
   - `mcp__playwright__browser_evaluate` で `querySelectorAll` を実行
   - 要素数とテキスト内容を確認

2. **ページネーションの動作確認**:
   - `mcp__playwright__browser_click` で実際にページ遷移を確認
   - 遷移後の `mcp__playwright__browser_snapshot` で構造が一貫しているか検証

3. **動的コンテンツの読み込み確認**:
   - `mcp__playwright__browser_snapshot` でスクロール後の状態を確認
   - `mcp__playwright__browser_network_requests` で API レスポンスを詳細検査

4. **スクレイピングコードの動作テスト**:
   - 実際のセレクタでデータ抽出できるか `mcp__playwright__browser_evaluate` で検証

## レポート生成

全 Phase 完了後、調査結果を JSON にまとめてレポート生成スクリプトを実行する。

### 手順

1. 調査結果を `.tmp/site-investigation-{domain}-{timestamp}.json` に保存
2. レポート生成:
   ```bash
   uv run python .claude/skills/site-investigator/scripts/generate_site_report.py \
     --input .tmp/site-investigation-{domain}-{timestamp}.json \
     --output-dir .tmp/site-reports/{domain}/
   ```
3. 出力:
   - `.tmp/site-reports/{domain}/report.json` — 構造化データ（後続スクリプト用）
   - `.tmp/site-reports/{domain}/report.md` — 人間が読むレポート
   - `.tmp/site-reports/{domain}/screenshots/` — スクリーンショット

### 入力 JSON スキーマ

調査結果は以下の構造で保存する:

```json
{
  "url": "https://example.com/blog",
  "investigated_at": "2026-03-21T10:00:00+09:00",
  "site_overview": {
    "type": "blog | news | ecommerce | portfolio | other",
    "technology": "WordPress | Next.js | Hugo | unknown",
    "language": "ja | en | ...",
    "has_rss": true,
    "rss_urls": ["https://example.com/feed"],
    "has_sitemap": true,
    "sitemap_url": "https://example.com/sitemap.xml",
    "robots_txt": {
      "exists": true,
      "disallow_rules": ["/wp-admin/"],
      "crawl_delay": null
    },
    "requires_login": false,
    "has_paywall": false
  },
  "list_page": {
    "url": "https://example.com/blog",
    "selectors": {
      "article_container": "article.post-card",
      "title": "article.post-card h2 a",
      "link": "article.post-card h2 a",
      "date": "article.post-card time",
      "author": "article.post-card .author",
      "thumbnail": "article.post-card img",
      "summary": "article.post-card .excerpt"
    },
    "items_per_page": 10,
    "pagination": {
      "type": "numbered | next_prev | infinite_scroll | load_more | none",
      "next_selector": "a.next",
      "url_pattern": "?page={n}"
    },
    "url_pattern": "/blog/{slug}"
  },
  "article_page": {
    "sample_url": "https://example.com/blog/sample-post",
    "selectors": {
      "title": "h1.entry-title",
      "body": "div.entry-content",
      "date": "time.published",
      "author": "span.author-name",
      "category": "a[rel='category']",
      "tags": "a[rel='tag']",
      "related_articles": ".related-posts a",
      "comments": "#comments"
    }
  },
  "dynamic_behavior": {
    "is_spa": false,
    "framework": null,
    "has_infinite_scroll": false,
    "has_lazy_load": true,
    "api_endpoints": [],
    "requires_js_rendering": false
  },
  "recommendations": {
    "best_approach": "rss | sitemap | direct_scraping | api",
    "fallback_approach": "sitemap | direct_scraping",
    "rate_limit_suggestion": "1 req/sec",
    "notes": ["特記事項"]
  }
}
```

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| サイト到達不可 | エラー報告して終了 |
| Cookie 同意で操作困難 | スクリーンショット撮影 → 手動対応を提案 |
| ログイン必須 | Phase 1 でその旨を報告、認証情報の提供を求める |
| SPA で state が薄い | `eval` で DOM を直接読む、`get html` でセレクタ指定取得 |
| タイムアウト | `wait` コマンドで明示的に待機、3回失敗で報告 |
| browser-use CLI が利用不可 | Playwright MCP にフォールバック（全 Phase を MCP で実行） |

## 注意事項

- robots.txt の Disallow ルールを尊重すること
- 短時間に大量のリクエストを送らないこと（Phase 全体で 10-20 リクエスト程度）
- 個人情報やログイン情報をレポートに含めないこと
- スクリーンショットは調査目的のみに使用すること
