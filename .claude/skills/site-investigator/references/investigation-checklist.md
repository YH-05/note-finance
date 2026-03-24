# サイト調査チェックリスト

各 Phase で確認すべき項目の詳細リスト。
SKILL.md の調査プロトコルに沿って、漏れなく調査するためのリファレンス。

全て browser-use CLI 2.0（Bash 経由）で実行する。検証フェーズでは Playwright MCP に切り替え可能。

**重要**: 全コマンドの先頭に `source ~/.browser-use-env/bin/activate &&` が必要。

## Phase 1: 初回アクセス・概要把握

### 基本情報

- [ ] ページタイトル（`browser-use get title`）
- [ ] ページ種別: 一覧 / 個別記事 / トップ / ランディング / SPA
- [ ] 言語: HTML `lang` 属性、コンテンツの言語
- [ ] レスポンシブ対応: viewport meta の有無

### CMS / フレームワーク検出

```bash
browser-use eval 'JSON.stringify({
  wordpress: !!document.querySelector("meta[name=\"generator\"][content*=\"WordPress\"]") || !!document.querySelector("link[href*=\"wp-content\"]"),
  nextjs: !!document.getElementById("__next") || !!document.querySelector("script[src*=\"_next\"]"),
  nuxtjs: !!document.getElementById("__nuxt") || !!document.querySelector("[data-n-head]"),
  gatsby: !!document.getElementById("___gatsby"),
  hugo: !!document.querySelector("meta[name=\"generator\"][content*=\"Hugo\"]"),
  wix: !!document.querySelector("meta[name=\"generator\"][content*=\"Wix\"]"),
  shopify: !!document.querySelector("meta[name=\"shopify\"]") || !!document.querySelector("link[href*=\"cdn.shopify.com\"]")
})'
```

### 障害物の処理

- [ ] Cookie 同意バナー → `click <index>`（state で「Accept」「同意」ボタンの index を確認）
- [ ] ニュースレター登録ポップアップ → `click <index>`（「閉じる」「×」ボタン）
- [ ] 年齢確認ダイアログ → 必要に応じて処理
- [ ] チャットウィジェット → 邪魔なら閉じる

## Phase 2: メタ情報

### RSS フィード検出チェックリスト

- [ ] `<link type="application/rss+xml">` の存在（`eval` で検出）
- [ ] `<link type="application/atom+xml">` の存在（`eval` で検出）
- [ ] `/feed` パスへのアクセス（`open` で確認）
- [ ] `/rss` パスへのアクセス
- [ ] `/feed.xml` パスへのアクセス
- [ ] `/atom.xml` パスへのアクセス
- [ ] `/blog/feed` パスへのアクセス（ブログがサブパスの場合）

### サイトマップ検出チェックリスト

- [ ] `/sitemap.xml` の存在（`open` + `get html` で確認）
- [ ] `/sitemap_index.xml` の存在
- [ ] `/sitemap/` ディレクトリの存在
- [ ] robots.txt 内の `Sitemap:` ディレクティブ
- [ ] サイトマップの形式: XML / テキスト / インデックス

### robots.txt 解析項目

- [ ] `User-agent` ルールの対象
- [ ] `Disallow` ルール一覧
- [ ] `Allow` ルール（例外許可）
- [ ] `Crawl-delay` の値
- [ ] `Sitemap` URL の指定

### meta タグ収集項目

- [ ] `og:title`, `og:description`, `og:image`（OGP）
- [ ] `twitter:card`, `twitter:title`（Twitter Card）
- [ ] `canonical` URL
- [ ] `generator`（CMS 検出用）
- [ ] `robots`（noindex, nofollow）
- [ ] `description`

## Phase 3: 一覧ページ構造

### 繰り返し要素の特定

`state` の出力で以下のパターンを探す（優先度順）:

1. `<article>` 要素の繰り返し（同じ構造が複数）
2. `<a>` リンクのパターン（記事タイトルのリンク群）
3. index 番号が連続する同種の要素

さらに `get html --selector` で詳細構造を確認:

```bash
browser-use get html --selector "article:first-of-type"
browser-use get html --selector "ul.post-list"
```

### 各アイテム内の要素

- [ ] タイトル: 通常 `h2` or `h3` 内のリンク
- [ ] URL: タイトルリンクの `href`
- [ ] 日付: `<time>` 要素、`datetime` 属性
- [ ] サムネイル: `<img>` 要素、`src` / `data-src`
- [ ] 著者: `.author`, `[rel="author"]`
- [ ] 概要/抜粋: `.excerpt`, `.summary`, `<p>` 要素
- [ ] カテゴリ: カテゴリリンク、バッジ

### ページネーション方式

| 方式 | 検出方法 |
|------|----------|
| Numbered | `state` で `?page=`, `/page/N/` 形式のリンクを発見 |
| Next/Prev | `state` で「次へ」「Next」「→」ボタンを発見 |
| Infinite Scroll | `scroll down` 後に `state` で要素数が増加 |
| Load More | `state` で「もっと見る」「Load More」ボタンを発見 |
| None | 1 ページに全件表示 |

### セレクタ検証スクリプト

```bash
browser-use eval 'JSON.stringify((function() {
  function validate(selectors) {
    var results = {};
    for (var name in selectors) {
      var els = document.querySelectorAll(selectors[name]);
      results[name] = { count: els.length, sample: els[0] ? els[0].textContent.trim().substring(0, 100) : null };
    }
    return results;
  }
  return validate({ article: "article.post-card", title: "article.post-card h2 a", date: "article.post-card time" });
})())'
```

## Phase 4: 個別コンテンツページ

### 必須要素

- [ ] タイトル: `get html --selector "h1"`
- [ ] 本文コンテナ: `get html --selector "article"` または `get html --selector ".entry-content"`
- [ ] 公開日: `get html --selector "time"`
- [ ] 著者名: `get html --selector "[rel=author]"`

### オプション要素

- [ ] 更新日: 公開日とは別の日付
- [ ] カテゴリ: リンク形式のカテゴリ名
- [ ] タグ: タグクラウドまたはリスト
- [ ] アイキャッチ画像: 記事上部の大きな画像
- [ ] 関連記事: 記事下部のリンクリスト
- [ ] コメント欄: コメントセクションの有無
- [ ] SNS シェアボタン: シェア UI の有無
- [ ] 目次: ページ内リンクの目次

### ペイウォール/ログイン壁検出

```bash
browser-use eval 'JSON.stringify({
  paywallOverlay: !!document.querySelector("[class*=\"paywall\"], [class*=\"subscribe\"], [id*=\"paywall\"]"),
  loginModal: !!document.querySelector("[class*=\"login-modal\"], [class*=\"signin\"], [class*=\"auth-wall\"]"),
  readMore: !!document.querySelector("[class*=\"read-more-gate\"], [class*=\"premium-content\"]"),
  bodyLength: document.querySelector("article")?.textContent?.length || 0
})'
```

## Phase 5: 動的挙動

### SPA フレームワーク検出

- [ ] React: `[data-reactroot]`, `#__next`, `._reactRootContainer`
- [ ] Vue: `[data-v-]`, `#__nuxt`, `.__vue_root`
- [ ] Angular: `[ng-version]`, `[_nghost]`
- [ ] Svelte: `[class*="svelte-"]`

### lazy load パターン

- [ ] `<img loading="lazy">`: ネイティブ lazy load
- [ ] `<img data-src="...">`: カスタム lazy load
- [ ] `<img class="lazyload">`: lazysizes 等のライブラリ
- [ ] `background-image` の遅延読み込み

### パフォーマンス情報

```bash
browser-use eval 'JSON.stringify({
  protocol: performance.getEntriesByType("navigation")[0]?.nextHopProtocol,
  domContentLoaded: Math.round(performance.getEntriesByType("navigation")[0]?.domContentLoadedEventEnd),
  loadComplete: Math.round(performance.getEntriesByType("navigation")[0]?.loadEventEnd),
  transferSize: Math.round(performance.getEntriesByType("navigation")[0]?.transferSize / 1024) + "KB"
})'
```

## 検証フェーズ（Playwright MCP）

Phase 1-5 完了後、実装に移る際にセレクタの詳細検証が必要な場合は
Playwright MCP ツールに切り替える。

### MCP 切り替え後の検証パターン

```
# 1. browser-use セッションを閉じる
browser-use close

# 2. MCP でページにアクセス
mcp__playwright__browser_navigate(url="...")

# 3. セレクタをインタラクティブに検証
mcp__playwright__browser_evaluate(expression="document.querySelectorAll('...').length")

# 4. ページ遷移を確認
mcp__playwright__browser_click(element="...", ref="...")

# 5. 遷移後の構造確認
mcp__playwright__browser_snapshot()
```
