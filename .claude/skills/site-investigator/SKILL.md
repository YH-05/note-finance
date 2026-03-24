---
name: site-investigator
description: >
  新しいサイトのスクレイピング前調査スキル。Playwright CLI でサイトにアクセスし、
  ページ構造・セレクタ・ページネーション・RSS/サイトマップ・動的挙動を自動解析して
  JSON + Markdown レポートを生成する。
  ハイブリッド方式: 調査は Playwright CLI（トークン効率優先）、検証は Playwright MCP。
  「サイト調査」「サイト構造を調べて」「スクレイピング前に構造を確認」「このURLの構造を解析」
  「セレクタを特定して」「ページネーションの仕組みを調べて」「RSSがあるか確認」
  と言われたら必ずこのスキルを使うこと。
  新しいサイトへのスクレイピング実装を始める前にプロアクティブに使用すること。
---

# site-investigator スキル

未知のサイトを体系的に調査し、スクレイピングに必要な構造情報をまとめるスキル。

**ハイブリッド方式**:
- **Phase 1-5（調査）**: Playwright CLI を Bash 経由で使用（トークン効率 ~4x 改善）
- **検証フェーズ（オプション）**: Playwright MCP でセレクタの詳細テスト

## 前提条件

- Playwright CLI が利用可能であること（`npx -y @playwright/cli@latest` で自動インストール）
- Playwright MCP が Claude Code に設定済みであること（検証フェーズ用、オプション）

## 使い方

```
/site-investigator https://example.com/blog
```

引数としてサイトの URL を受け取り、5 Phase の調査を実行する。

## Playwright CLI 基本コマンド

Phase 1-5 では全て Bash 経由で CLI コマンドを実行する。
スナップショットはファイルに保存し、必要な部分のみ Read で読むことでトークンを節約する。

```bash
# ブラウザを開いて URL にアクセス（初回）
npx -y @playwright/cli@latest open <url>

# 同一セッション内で URL 遷移
npx -y @playwright/cli@latest goto <url>

# スナップショットをファイルに保存（コンテキスト外）
npx -y @playwright/cli@latest snapshot --filename <path>.md

# スクリーンショットをファイルに保存
npx -y @playwright/cli@latest screenshot --filename <path>.png

# 要素をクリック（ref はスナップショットから取得）
npx -y @playwright/cli@latest click <ref>

# JavaScript を実行（結果は stdout）
npx -y @playwright/cli@latest eval '<js expression>'

# ネットワークリクエスト一覧
npx -y @playwright/cli@latest network

# ダイアログ操作
npx -y @playwright/cli@latest dialog-accept
npx -y @playwright/cli@latest dialog-dismiss

# ブラウザを閉じる
npx -y @playwright/cli@latest close
```

### スナップショットの効率的な読み方

スナップショットファイルは全体を読む必要はない。
Read ツールの offset/limit パラメータで必要な部分のみ取得する:

```
# 冒頭50行（ナビゲーション構造の把握）
Read: path, limit=50

# 特定セクションを検索
Grep: pattern="article|listitem" in snapshot file
```

### eval の注意点

- 外側はシングルクォート、内側はダブルクォートを使用
- 複雑なオブジェクトは `JSON.stringify()` で文字列化して返す
- 非常に複雑な JS は `.tmp/` にファイル保存して実行を検討

## 調査プロトコル（5 Phase）

各 Phase を順番に実行する。Phase 間で得た情報を蓄積しながら進める。
詳細なチェック項目は `references/investigation-checklist.md` を参照。

ファイル保存先のベースディレクトリ: `.tmp/site-reports/{domain}/`

### Phase 1: 初回アクセス・概要把握

**目的**: サイトの第一印象を掴み、基本情報を収集する。

1. ブラウザを開いて対象 URL にアクセス:
   ```bash
   npx -y @playwright/cli@latest open {url}
   ```

2. スクリーンショットを保存:
   ```bash
   npx -y @playwright/cli@latest screenshot --filename .tmp/site-reports/{domain}/screenshots/phase1-home.png
   ```

3. スナップショットをファイルに保存:
   ```bash
   npx -y @playwright/cli@latest snapshot --filename .tmp/site-reports/{domain}/snapshots/phase1-home.md
   ```

4. スナップショットファイルを Read で読み込み（冒頭100行程度で判定可能）、以下を判定:
   - ページ種別（一覧 / 単体記事 / トップページ / SPA）
   - 言語（日本語 / 英語 / 他）
   - CMS/フレームワーク推定（WordPress, Next.js, etc.）

5. Cookie 同意バナーやポップアップがあれば:
   ```bash
   npx -y @playwright/cli@latest click <ref>
   ```
   （ref はスナップショット内の「Accept」「同意」ボタンの ref 値）

**判定ロジック**: アクセシビリティツリーで `article` 要素の繰り返しがあれば一覧ページ、
単一の長い `article` なら個別記事ページ、と判断する。

### Phase 2: メタ情報の収集

**目的**: スクレイピングの最適手段（RSS / サイトマップ / 直接）を判断する材料を集める。

1. **RSS フィード検出**:
   ```bash
   npx -y @playwright/cli@latest eval '(() => {
     const feeds = document.querySelectorAll("link[type=\"application/rss+xml\"], link[type=\"application/atom+xml\"]");
     return JSON.stringify(Array.from(feeds).map(f => ({ href: f.href, title: f.title })));
   })()'
   ```
   - 見つからない場合、以下のパスを順に試す:
   ```bash
   npx -y @playwright/cli@latest goto {base_url}/feed
   npx -y @playwright/cli@latest goto {base_url}/rss
   npx -y @playwright/cli@latest goto {base_url}/feed.xml
   npx -y @playwright/cli@latest goto {base_url}/atom.xml
   ```

2. **サイトマップ検出**:
   ```bash
   npx -y @playwright/cli@latest goto {base_url}/sitemap.xml
   npx -y @playwright/cli@latest snapshot --filename .tmp/site-reports/{domain}/snapshots/phase2-sitemap.md
   ```
   - 404 なら `/sitemap_index.xml`, `/sitemap/` も試す

3. **robots.txt 確認**:
   ```bash
   npx -y @playwright/cli@latest goto {base_url}/robots.txt
   npx -y @playwright/cli@latest snapshot --filename .tmp/site-reports/{domain}/snapshots/phase2-robots.md
   ```
   - Read でファイルを読み、Disallow ルール、Crawl-delay、Sitemap 指定を抽出

4. **meta タグ収集**:
   ```bash
   npx -y @playwright/cli@latest goto {url}
   npx -y @playwright/cli@latest eval '(() => {
     const metas = document.querySelectorAll("meta");
     return JSON.stringify(Array.from(metas).map(m => ({
       name: m.name || m.getAttribute("property"),
       content: m.content
     })));
   })()'
   ```

### Phase 3: 一覧ページの構造解析

**目的**: 記事一覧のセレクタとページネーション方式を特定する。

Phase 1 で一覧ページと判定された場合（または一覧ページに遷移して）実行。

1. スナップショットから繰り返し構造を発見:
   ```bash
   npx -y @playwright/cli@latest goto {list_page_url}
   npx -y @playwright/cli@latest snapshot --filename .tmp/site-reports/{domain}/snapshots/phase3-list.md
   ```
   - Read でスナップショットを読み、同一構造の `article`, `li`, `div` が並んでいるパターンを探す
   - 各アイテム内のタイトル（リンク）、日付、サムネイル、著者を特定

2. セレクタの検証:
   ```bash
   npx -y @playwright/cli@latest eval '(() => {
     return JSON.stringify({
       count: document.querySelectorAll("article.post-card").length,
       sample: document.querySelector("article.post-card")?.textContent?.substring(0, 100)
     });
   })()'
   ```

3. ページネーション方式の特定:
   - スナップショット内で `navigation` や `pagination` を含む要素を Grep で検索
   - 方式を判定:
     - **numbered**: `?page=2` や `/page/2/` 形式のリンク
     - **next/prev**: 「次へ」「前へ」ボタン
     - **infinite scroll**: スクロールイベントで追加読み込み
     - **load more**: 「もっと見る」ボタン
   - infinite scroll の検出:
     ```bash
     npx -y @playwright/cli@latest eval '(() => {
       return JSON.stringify({
         hasIntersectionObserver: typeof IntersectionObserver !== "undefined",
         scrollListeners: typeof getEventListeners !== "undefined" ? (getEventListeners(window).scroll?.length || 0) : "unknown"
       });
     })()'
     ```

4. URL パターンの分析:
   - 記事リンクの href から URL パターンを抽出
   - 例: `/blog/{slug}`, `/articles/{id}`, `/{year}/{month}/{slug}`

### Phase 4: 個別コンテンツページの構造解析

**目的**: 記事ページの各要素のセレクタを特定する。

1. Phase 3 で見つけた記事リンクの 1 つをクリック:
   ```bash
   npx -y @playwright/cli@latest click <ref>
   ```

2. 記事ページのスナップショットを保存:
   ```bash
   npx -y @playwright/cli@latest snapshot --filename .tmp/site-reports/{domain}/snapshots/phase4-article.md
   ```

3. Read でスナップショットを読み、以下の要素を特定:
   - **タイトル**: 通常 `h1` 要素
   - **本文**: `article`, `div.content`, `div.entry-content` 等のコンテナ
   - **公開日**: `time` 要素、`datetime` 属性
   - **著者**: `a[rel="author"]`, `.author` 等
   - **カテゴリ/タグ**: カテゴリリンク、タグクラウド
   - **関連記事**: 記事下部のリンクリスト
   - **コメント欄**: 有無の確認

4. ペイウォール/ログイン壁の検出:
   ```bash
   npx -y @playwright/cli@latest eval '(() => {
     return JSON.stringify({
       paywallOverlay: !!document.querySelector("[class*=\"paywall\"], [class*=\"subscribe\"], [id*=\"paywall\"]"),
       loginModal: !!document.querySelector("[class*=\"login-modal\"], [class*=\"signin\"], [class*=\"auth-wall\"]"),
       readMore: !!document.querySelector("[class*=\"read-more-gate\"], [class*=\"premium-content\"]"),
       bodyLength: document.querySelector("article")?.textContent?.length || 0
     });
   })()'
   ```

5. セレクタの検証:
   ```bash
   npx -y @playwright/cli@latest eval '(() => {
     const body = document.querySelector("div.entry-content");
     return body ? body.textContent.substring(0, 200) : null;
   })()'
   ```

### Phase 5: 動的挙動の検出

**目的**: JavaScript 依存度と API エンドポイントを把握する。

1. **SPA / CSR 判定**:
   ```bash
   npx -y @playwright/cli@latest eval '(() => {
     return JSON.stringify({
       hasReact: !!document.querySelector("[data-reactroot], #__next"),
       hasVue: !!document.querySelector("[data-v-], #__nuxt"),
       hasAngular: !!document.querySelector("[ng-version], [_nghost]"),
       bodyTextLength: document.body.innerText.length
     });
   })()'
   ```

2. **API エンドポイントの発見**:
   ```bash
   npx -y @playwright/cli@latest network
   ```
   - JSON レスポンスを返す API があれば、直接 API を叩く方がスクレイピングより効率的

3. **lazy load 検出**:
   ```bash
   npx -y @playwright/cli@latest eval '(() => {
     return JSON.stringify({
       lazyImages: document.querySelectorAll("img[loading=\"lazy\"], img[data-src]").length,
       totalImages: document.querySelectorAll("img").length
     });
   })()'
   ```

4. **レート制限の確認**:
   - `network` コマンドの出力からレスポンスヘッダーの `X-RateLimit-*`, `Retry-After` を確認

5. ブラウザを閉じる:
   ```bash
   npx -y @playwright/cli@latest close
   ```

## 検証フェーズ（オプション）

Phase 1-5 完了後、ユーザーがセレクタの詳細検証を求めた場合や、
実装状況がわかってきた段階で Playwright MCP に切り替えて詳細テストを行う。

### 切り替え手順

1. CLI セッションが開いていれば閉じる:
   ```bash
   npx -y @playwright/cli@latest close
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
| SPA で snapshot が薄い | `eval` で DOM を直接読む |
| タイムアウト | 30秒待って再試行、3回失敗で報告 |
| Playwright CLI が利用不可 | Playwright MCP にフォールバック（全 Phase を MCP で実行） |

## 注意事項

- robots.txt の Disallow ルールを尊重すること
- 短時間に大量のリクエストを送らないこと（Phase 全体で 10-20 リクエスト程度）
- 個人情報やログイン情報をレポートに含めないこと
- スクリーンショットは調査目的のみに使用すること
