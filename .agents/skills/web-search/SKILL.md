---
name: web-search
description: |
  Web検索ツールの選択ガイド。Tavily MCP・Gemini Search・WebSearch・Fetchの使い分け基準を提供するナレッジベース。
  Use PROACTIVELY when Web検索、情報収集、リサーチ、ニュース検索、URL取得を行う場面。
allowed-tools: Read
---

# web-search スキル

Web検索ツールの選択ガイド。Tavily MCP・Gemini Search・その他ツールの使い分け基準を提供する。
Web検索を行う全スキル・エージェント・コマンドが参照するナレッジベース。

## ツール一覧

| ツール | 種別 | コスト | 速度 | 日本語 | 構造化データ |
|--------|------|--------|------|--------|-------------|
| Tavily MCP | MCP Server | 有料API | 速い | 弱い | JSON構造 |
| Gemini Search | スキル（CLI） | 無料 | 遅い | 強い | テキスト |
| WebSearch | ビルトイン | 有料 | 速い | 普通 | テキスト |
| mcp__fetch__fetch | MCP Server | 無料 | 速い | - | HTML/テキスト |
| WebFetch | ビルトイン | 無料 | 速い | - | HTML/テキスト |

## 選択フローチャート

```
Web検索が必要
    │
    ├─ 自動パイプライン / ワークフロー内？
    │   ├─ YES → 構造化データが必要？
    │   │         ├─ YES ──→ Tavily MCP（tavily_search）
    │   │         └─ NO ───→ Tavily MCP or Gemini Search
    │   └─ NO
    │
    ├─ 日本語コンテンツ中心？
    │   ├─ YES ──→ Gemini Search
    │   └─ NO
    │
    ├─ 深いリサーチ（自動サブクエリ展開）？
    │   ├─ YES ──→ Tavily MCP（tavily_research）
    │   └─ NO
    │
    ├─ 特定URLの本文取得？
    │   ├─ YES ──→ Tavily MCP（tavily_extract）or mcp__fetch__fetch
    │   └─ NO
    │
    ├─ コスト節約が優先？
    │   ├─ YES ──→ Gemini Search
    │   └─ NO
    │
    └─ 上記いずれでもない ──→ Tavily MCP（デフォルト）
```

## Tavily MCP

### ツール群

| ツール | 用途 |
|--------|------|
| `mcp__tavily__tavily_search` | 通常のWeb検索。構造化されたJSON結果を返す |
| `mcp__tavily__tavily_research` | 深掘りリサーチ。サブクエリを自動生成して多角的に調査 |
| `mcp__tavily__tavily_extract` | 指定URLから本文を抽出。`mcp__fetch__fetch` より精度が高い |
| `mcp__tavily__tavily_crawl` | 指定URLのサイトをクロール |
| `mcp__tavily__tavily_map` | サイトマップを取得 |

### 強み

- **構造化結果**: JSON形式で返るため、パースやフィルタリングが容易
- **並列呼び出し**: 複数クエリを同時に実行可能（ToolSearch でロード後）
- **関連度スコア**: 結果に関連度スコアが付き、重要度でフィルタリング可能
- **AI特化設計**: RAG/LLM用途に最適化された結果を返す
- **多機能**: search / research / extract / crawl / map と用途別ツールが豊富

### 弱み

- **有料API**: クォータを消費する（コスト意識が必要）
- **日本語カバレッジ**: Googleに比べてインデックスが小さく、日本語サイトのカバレッジが弱い
- **国内ニュース**: 日経・東洋経済・SBI証券等の日本語金融メディアの取得精度が低い

### 適用場面

1. **ワークフロー内の自動処理**: `finance-news-workflow`, `generate-market-report` 等のパイプライン
2. **並列検索が必要な場面**: 複数カテゴリ（指数・MAG7・セクター）を同時検索
3. **英語圏の金融情報**: CNBC, Bloomberg, Reuters, SEC filing 等
4. **URL本文抽出**: 記事本文の取得（`tavily_extract`）
5. **深掘りリサーチ**: テーマを多角的に調査（`tavily_research`）

### 使用例

```python
# ToolSearch でロード（必須）
ToolSearch(query="+tavily search")

# 通常検索
mcp__tavily__tavily_search(query="S&P 500 weekly performance", max_results=5)

# 深掘りリサーチ
mcp__tavily__tavily_research(query="NVIDIA AI demand outlook 2026")

# URL本文抽出
mcp__tavily__tavily_extract(urls=["https://www.cnbc.com/..."])
```

---

## Gemini Search

### 実行方法

```bash
# Bash ツール経由で実行
gemini --prompt "WebSearch: <検索クエリ>"
```

### 強み

- **Googleインデックス**: 世界最大の検索インデックスを使用
- **日本語に強い**: Google は日本で検索シェア90%超。国内サイトのカバレッジが圧倒的
- **要約・合成**: Gemini が結果を読み解いて要約して返す → 読みやすい
- **無料**: 現時点でAPI課金なし
- **自然言語クエリ**: 質問形式のクエリにも対応

### 弱み

- **速度**: Bash経由のCLI起動 → オーバーヘッドが大きい（5-15秒/クエリ）
- **構造化困難**: テキスト出力 → JSONパースや自動処理に不向き
- **並列化困難**: Bash コマンドの並列実行は制約がある
- **結果の再現性**: Gemini の要約が毎回異なる可能性

### 適用場面

1. **日本語金融ニュース**: 日経・東洋経済・ブルームバーグ日本版・SBI証券等
2. **対話的な調査**: 「〇〇について教えて」式の自然な調査
3. **手動リサーチ**: `/gemini-search` コマンドで対話的に使用
4. **コスト節約**: Tavily クォータを温存したい場面
5. **Google固有情報**: Google Finance, Google トレンド等

### 使用例

```bash
# 日本語金融ニュース検索
gemini --prompt "WebSearch: 日銀 金利政策 2026年3月 最新"

# 特定トピックの深掘り
gemini --prompt "WebSearch: 新NISA つみたて投資枠 人気ファンド 2026"

# 英語でも使用可能
gemini --prompt "WebSearch: Federal Reserve rate decision March 2026"
```

---

## 使い分け判定基準

### 基準1: 言語とソース

| 検索対象 | 推奨ツール | 理由 |
|---------|-----------|------|
| 日本語金融メディア | Gemini Search | Googleの日本語インデックスが圧倒的 |
| 英語金融メディア | Tavily MCP | AI最適化された構造化結果 |
| 両方（bilingual） | 併用 | 英語→Tavily、日本語→Gemini |

### 基準2: 処理の自動化度

| 自動化レベル | 推奨ツール | 理由 |
|-------------|-----------|------|
| 完全自動（パイプライン内） | Tavily MCP | JSON構造、並列化、プログラマティック |
| 半自動（エージェント判断あり） | どちらでも可 | 状況に応じて選択 |
| 手動（ユーザー対話） | Gemini Search | 自然な質問形式、無料 |

### 基準3: 速度と品質

| 優先事項 | 推奨ツール | 理由 |
|---------|-----------|------|
| 速度優先 | Tavily MCP | 1-3秒/クエリ |
| 品質優先（日本語） | Gemini Search | より広いカバレッジ |
| 品質優先（英語） | Tavily MCP | AI特化の結果品質 |

### 基準4: コスト

| コスト方針 | 推奨ツール | 理由 |
|-----------|-----------|------|
| コスト意識なし | Tavily MCP | 速度・構造化で優位 |
| コスト節約 | Gemini Search | 無料 |
| 最適バランス | 併用 | Tavily をパイプラインに温存、手動調査は Gemini |

---

## プロジェクト内の利用パターン

### パターン1: 週次マーケットレポート（`generate-market-report`）

```
Phase 3: ニュース検索
├── 1st: RSS MCP（登録済み33フィード、最速）
├── 2nd: Tavily MCP（Web全体検索、構造化結果）
├── 3rd: Gemini Search（バックアップ）
└── 4th: mcp__fetch__fetch（特定URL取得）
```

**推奨改善**: Phase 3 の日本語ニュース部分を Gemini Search に切り替え

### パターン2: 投資リサーチ（`investment-research`）

```
マルチソース検索:
├── WebSearch（メイン）
├── RSS MCP（登録済みフィード）
├── Reddit MCP（コミュニティ議論）
└── SEC Edgar MCP（個別銘柄）
```

**推奨**: 日本語テーマは Gemini Search をメインに、英語テーマは Tavily を使用

### パターン3: トピック発掘（`topic-discovery`）

```
トレンドリサーチ（8-12回）:
├── 市場トレンド: 3回 → Tavily or Gemini
├── セクター動向: 2回 → Tavily
├── AI・テクノロジー: 2回 → Tavily
├── 日本市場: 2回 → Gemini Search（日本語コンテンツ）
└── コンテンツギャップ: 1-3回 → Gemini Search（note.com 分析）
```

### パターン4: 金融ニュース収集（`finance-news-workflow`）

```
テーマ別収集:
├── 英語テーマ（index, stock, ai）→ Tavily MCP
└── 日本語テーマ（macro JP, sector JP）→ Gemini Search
```

---

## フォールバック戦略

```
Tavily MCP 利用不可時:
  ToolSearch で Tavily ロード失敗
    → Gemini Search にフォールバック
    → それも失敗 → WebSearch（ビルトイン）

Gemini Search 利用不可時:
  gemini CLI 未インストール / エラー
    → Tavily MCP にフォールバック
    → それも失敗 → WebSearch（ビルトイン）

特定URL取得のフォールバック:
  tavily_extract → mcp__fetch__fetch → WebFetch
```

## ToolSearch でのロード

各ツールは使用前に ToolSearch でロードが必要:

```python
# Tavily MCP
ToolSearch(query="+tavily search")

# Gemini Search（スキルプリロード or Bash で直接実行）
# スキルの場合: skill-preload: gemini-search
# 直接実行: Bash("gemini --prompt 'WebSearch: ...'")

# Fetch MCP
ToolSearch(query="+fetch")
```

## 関連リソース

| リソース | パス |
|---------|------|
| Gemini Search スキル | `.agents/skills/gemini-search/SKILL.md` |
| Gemini Search コマンド | `.agents/commands/gemini-search.md` |
| 検索テンプレート | `.agents/resources/search-templates/` |
| 投資リサーチ検索戦略 | `.agents/skills/investment-research/references/search-strategy.md` |
| トピック発掘検索戦略 | `.agents/skills/topic-discovery/references/search-strategy.md` |
| マーケットレポート | `.agents/commands/generate-market-report.md` |
