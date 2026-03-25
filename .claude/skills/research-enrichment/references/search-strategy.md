# Search Strategy — research-enrichment Phase 2

ターゲット Entity の属性に基づいてデータソースを動的に選択するマトリクス、
フォールバックチェーン、RawStore 保存ルール、`raw_items[]` 正規化フォーマットを定義する。
SKILL.md Phase 2 から参照される。

> **参照**: Web検索ツール全般の選択基準は `.claude/skills/web-search/SKILL.md` を参照。
> alphaxiv の詳細ルールは `.claude/skills/alphaxiv-search/SKILL.md` を参照。

---

## ソース選択マトリクス

Phase 1（Gap Analysis）で選定されたターゲット Entity の属性に応じて、
実行するデータソースを動的に決定する。

### 常時実行（全 Entity 共通）

| ソース | ツール | クエリ数 | 備考 |
|--------|--------|---------|------|
| Tavily EN | `mcp__tavily__tavily_search` | 2 | 英語 Web 検索（構造化JSON） |
| Tavily JA | `mcp__tavily__tavily_search` | 2 | 日本語 Web 検索（構造化JSON） |
| Reddit | `mcp__reddit__get_subreddit_hot_posts` / `get_subreddit_new_posts` | 1-2 | r/stocks, r/investing, r/SecurityAnalysis 等 |

**合計**: 常時 5-6 クエリ

### 条件付き実行

| 条件 | ソース | ツール | 詳細 |
|------|--------|--------|------|
| `ticker IS NOT NULL` | SEC EDGAR | `mcp__sec-edgar-mcp__get_recent_filings` | 直近 filing 一覧 |
| `ticker IS NOT NULL` | SEC EDGAR | `mcp__sec-edgar-mcp__get_financials` | 財務諸表データ |
| `ticker IS NOT NULL` | SEC EDGAR | `mcp__sec-edgar-mcp__get_key_metrics` | 主要財務指標 |
| sector = `Technology` or `EquityResearch` | alphaxiv | `mcp__alphaxiv__embedding_similarity_search` | 学術論文検索（主軸） |
| sector = `Technology` or `EquityResearch` | alphaxiv | `mcp__alphaxiv__get_paper_content` | 厳選 2-3 件のみ |
| `description IS NULL` or 空文字 | Wikipedia | `mcp__wikipedia__get_summary` | Entity 概要補完 |

### 選択フローチャート

```
Phase 1 でターゲット Entity 選定
    │
    ├── 常時: Tavily EN×2 + JA×2 + Reddit
    │
    ├── ticker あり？
    │   ├── YES → SEC EDGAR 3ツール追加
    │   │         (get_recent_filings, get_financials, get_key_metrics)
    │   └── NO  → スキップ
    │
    ├── sector = Technology or EquityResearch？
    │   ├── YES → alphaxiv 追加
    │   │         (embedding_similarity_search 優先)
    │   └── NO  → スキップ
    │
    └── description 未登録？
        ├── YES → Wikipedia get_summary 追加
        └── NO  → スキップ
```

---

## ソース別詳細ルール

### Tavily（常時実行）

**レート消費抑制**: Tavily はクォータ制の有料 API のため、以下のルールで消費を抑制する。

| ルール | 詳細 |
|--------|------|
| クエリ数上限 | EN×2 + JA×2 = **合計 4 クエリ/Entity** |
| `max_results` | `5`（1クエリあたり最大5件） |
| `include_raw_content` | `false`（本文は不要、snippet で十分） |
| バッチ間インターバル | Entity 間で 1-2秒の待機を推奨 |
| 432 エラー時 | キーローテーション → 全キー枯渇で WebSearch フォールバック |

**クエリ構築**:

```
EN-1: "{entity_name} {ticker} latest news analysis {current_year}"
EN-2: "{entity_name} {sector} outlook earnings {current_year}"
JA-1: "{entity_name_ja} 最新 分析 {current_year}年"
JA-2: "{entity_name_ja} {sector_ja} 業績 見通し"
```

### Reddit（常時実行）

| サブレディット | 対象 |
|---------------|------|
| r/stocks | 個別銘柄の議論 |
| r/investing | 投資戦略・マクロ |
| r/SecurityAnalysis | ファンダメンタル分析 |
| r/wallstreetbets | センチメント・トレンド（ノイズが多いため補助的に） |

Entity の `ticker` がある場合はサブレディット内で ticker をキーワードに絞り込む。
Reddit 投稿はコンテンツ量が限られるため、`get_post_content` での深掘りは重要な投稿 2-3件 に限定する。

### SEC EDGAR（ticker あり時のみ）

**3ツール並列実行**:

| ツール | 引数 | 出力 |
|--------|------|------|
| `get_recent_filings` | `ticker={ticker}` | 直近 filing リスト（10-K, 10-Q, 8-K 等） |
| `get_financials` | `ticker={ticker}` | 収益・利益・BS データ |
| `get_key_metrics` | `ticker={ticker}` | PER, PBR, ROE 等の指標 |

**重要**: SEC EDGAR データは `raw_items[]` に格納せず、**直接マッピング**する（後述「LLM バイパス」参照）。

### alphaxiv（Technology / EquityResearch セクター時のみ）

**必ず `.claude/skills/alphaxiv-search/SKILL.md` のルールに従う。**

| 優先度 | ツール | 並列上限 | 用途 |
|--------|--------|---------|------|
| **1st（主軸）** | `embedding_similarity_search` | 3件同時 | セマンティック検索、Abstract + メタデータ |
| 2nd（厳選） | `get_paper_content` | **2-3件ずつ** | 重要論文の詳細取得 |
| 使わない | `agentic_paper_retrieval` | - | トークン消費が予測不能 |

**検索クエリ例**:

```
embedding_similarity_search(
  query="{entity_name} financial analysis machine learning.
  Papers on {sector} valuation models, earnings prediction,
  and quantitative strategies for {entity_name}."
)
```

**重要**: alphaxiv データは `raw_items[]` に格納せず、**直接マッピング**する（後述「LLM バイパス」参照）。

### Wikipedia（description 未登録 Entity のみ）

| ツール | 引数 | 用途 |
|--------|------|------|
| `get_summary` | `title="{entity_name}"` | Entity の概要テキスト取得 |

取得した summary は Entity の `description` プロパティに SET する。
`raw_items[]` には格納しない（構造化データとして直接利用）。

---

## フォールバックチェーン

Web検索ツールが利用不可・結果不足の場合のフォールバック:

```
1st: Tavily MCP (tavily_search)
 │   └─ 432 エラー → キーローテーション → 全キー枯渇
 │
2nd: WebSearch（ビルトイン）
 │   └─ 結果 0 件 or エラー
 │
3rd: browser-use CLI 2.0
      └─ venv 未存在 or コマンドエラー → 当該クエリをスキップ
```

### フォールバック実行ルール

| 段階 | ツール | 条件 |
|------|--------|------|
| 1st | `mcp__tavily__tavily_search` | デフォルト。API キー利用可能時 |
| 2nd | `WebSearch` | Tavily 全キー枯渇 or Tavily MCP 接続エラー時 |
| 3rd | browser-use CLI | WebSearch も失敗時。`browser_use_available = true` の場合のみ |

**browser-use CLI 実行方法**:

```bash
# 重要: {query} にはシェルメタ文字が含まれる可能性があるため、
# Bash ツールでコマンド構築時は shlex.quote 相当のエスケープを適用すること
source ~/.browser-use-env/bin/activate && browser-use run \
  --task 'Search for: {query}' \
  --max-steps 5
```

---

## RawStore 保存ルール

Phase 2 の検索結果のうち、**SEC EDGAR と alphaxiv 以外**を RawStore に永続化する。

### 保存対象

| ソース | RawStore 保存 | 理由 |
|--------|:------------:|------|
| Tavily | **YES** | Web 検索結果を原文保存 |
| WebSearch | **YES** | フォールバック結果を原文保存 |
| Reddit | **YES** | コミュニティ投稿を原文保存 |
| browser-use CLI | **YES** | フォールバック結果を原文保存 |
| SEC EDGAR | **NO** | 構造化データ → 直接マッピング（LLM バイパス） |
| alphaxiv | **NO** | 構造化データ → 直接マッピング（LLM バイパス） |
| Wikipedia | **NO** | description プロパティに直接 SET |

### source_id 規則

```
source_id = "research-{entity_key}"
```

- `entity_key` は Phase 1 で選定されたターゲットの `entity_key`（例: `amd::company`）
- RawStore のディレクトリ構造: `{base_dir}/research-{entity_key}/{YYYY-MM-DD}/{url_hash}.json`

### 保存実行

```python
from data_pipeline.storage.raw_store import RawStore

store = RawStore()
for item in raw_items:
    store.save_text(
        source_id=f"research-{entity_key}",
        url=item["source_url"],
        title=item["title"],
        raw_text=item["content"],
        collection_method=item["source_type"],
    )
```

---

## raw_items[] 正規化フォーマット

Phase 2 の検索結果を Phase 3（構造化・KG 投入）に渡すための統一フォーマット。

### フィールド定義

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|:----:|------|
| `source_url` | `str` | YES | 元記事・投稿の URL |
| `title` | `str` | YES | 記事タイトル or 投稿タイトル |
| `content` | `str` | YES | 本文テキスト（snippet or 全文） |
| `source_type` | `str` | YES | ソース種別（下表参照） |
| `authority_level` | `str` | YES | 信頼性レベル（下表参照） |
| `target_entity` | `str` | YES | 対象 Entity の `entity_key` |

### source_type 一覧

| source_type | 対応ソース |
|-------------|-----------|
| `web` | Tavily / WebSearch / browser-use CLI |
| `social` | Reddit |
| `news` | Tavily で取得したニュース記事 |
| `blog` | Tavily で取得したブログ記事 |

### authority_level 一覧

| authority_level | 対応ソース | 説明 |
|----------------|-----------|------|
| `media` | 主要ニュースメディア（CNBC, Bloomberg, Reuters 等） | 報道機関 |
| `analyst` | アナリストレポート、投資リサーチ | 専門家分析 |
| `blog` | 個人ブログ、テック系メディア | 非公式分析 |
| `social` | Reddit 投稿・コメント | コミュニティ意見 |
| `official` | 企業公式サイト、IR ページ | 一次情報 |

**authority_level の自動判定**: URL ドメインに基づいて判定する。

| ドメインパターン | authority_level |
|-----------------|----------------|
| `cnbc.com`, `bloomberg.com`, `reuters.com`, `wsj.com` | `media` |
| `seekingalpha.com`, `morningstar.com` | `analyst` |
| `reddit.com` | `social` |
| 企業ドメイン（`ir.*`, `investor.*`） | `official` |
| 上記以外 | `blog` |

### raw_items[] の例

```json
[
  {
    "source_url": "https://www.cnbc.com/2026/03/20/amd-ai-chip-demand.html",
    "title": "AMD's AI Chip Demand Surges in Q1 2026",
    "content": "Advanced Micro Devices reported...",
    "source_type": "news",
    "authority_level": "media",
    "target_entity": "amd::company"
  },
  {
    "source_url": "https://www.reddit.com/r/stocks/comments/abc123/amd_earnings_beat",
    "title": "AMD Earnings Beat - What's Next?",
    "content": "Great quarter for AMD. The AI segment...",
    "source_type": "social",
    "authority_level": "social",
    "target_entity": "amd::company"
  },
  {
    "source_url": "https://seekingalpha.com/article/amd-valuation-2026",
    "title": "AMD: AI Tailwinds and Valuation Analysis",
    "content": "We initiate coverage of AMD with...",
    "source_type": "web",
    "authority_level": "analyst",
    "target_entity": "amd::company"
  }
]
```

---

## SEC EDGAR / alphaxiv 直接マッピング（LLM バイパス）

SEC EDGAR と alphaxiv の出力は既に構造化されているため、
`raw_items[]` を経由せず、Phase 3 の LLM 構造化をバイパスして直接 KG ノード/リレーションにマッピングする。

### SEC EDGAR → FinancialDataPoint

```
get_financials / get_key_metrics の出力
    │
    ├── 各指標 → FinancialDataPoint ノード
    │     ├── metric_id: "{ticker}:{metric_name}:{period}"
    │     ├── value: 数値
    │     ├── unit: "USD" / "ratio" / "%"
    │     └── as_of_date: 期末日
    │
    └── RELATES_TO → 対象 Entity
```

```
get_recent_filings の出力
    │
    └── 各 filing → Source ノード
          ├── source_type: "sec_filing"
          ├── authority_level: "official"
          └── url: filing URL
```

### alphaxiv → Fact / Claim

```
embedding_similarity_search の出力（Abstract）
    │
    ├── 各論文 → Source ノード
    │     ├── source_type: "academic"
    │     ├── authority_level: "academic"
    │     └── url: arXiv URL
    │
    └── Abstract から抽出した知見 → Fact ノード
          └── EXTRACTED_FROM → Source

get_paper_content の出力（詳細、2-3件のみ）
    │
    └── Method / Results → Claim ノード
          └── EXTRACTED_FROM → Source
```

---

## Phase 2 実行フロー（まとめ）

```
Phase 1 出力: ターゲット Entity リスト
    │
    ├── 1. 重複排除リスト取得（Q5: 直近7日の Source URL）
    │
    ├── 2. Entity ごとにソース選択マトリクスを適用
    │     ├── 常時: Tavily EN×2 + JA×2 + Reddit
    │     ├── ticker → SEC EDGAR 3ツール
    │     ├── Technology/EquityResearch → alphaxiv
    │     └── description 未登録 → Wikipedia
    │
    ├── 3. フォールバック付きで検索実行
    │     └── Tavily → WebSearch → browser-use CLI
    │
    ├── 4. raw_items[] 正規化
    │     ├── source_url / title / content / source_type / authority_level / target_entity
    │     └── Q5 リストと照合 → 重複 URL スキップ
    │
    ├── 5. RawStore 保存（SEC EDGAR / alphaxiv 以外）
    │     └── source_id = "research-{entity_key}"
    │
    └── 6. 出力
          ├── raw_items[] → Phase 3（LLM 構造化）へ
          ├── SEC EDGAR データ → Phase 3（直接マッピング、LLM バイパス）へ
          └── alphaxiv データ → Phase 3（直接マッピング、LLM バイパス）へ
```

---

## 検証例: AMD (ticker=AMD, sec_cik=2488, sector=Technology)

| 条件 | 結果 | 実行ソース |
|------|------|-----------|
| 常時実行 | YES | Tavily EN×2, JA×2, Reddit |
| ticker=AMD | YES | SEC EDGAR (get_recent_filings, get_financials, get_key_metrics) |
| sector=Technology | YES | alphaxiv (embedding_similarity_search 優先) |
| description 未登録 | 要確認 | Wikipedia get_summary（description が NULL/空なら実行） |

**期待される合計ソース数**: 5-6（常時）+ 3（SEC EDGAR）+ 1-3（alphaxiv）= **9-12 ソース**

---

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `references/gap-analysis-queries.md` | Phase 1 ギャップ分析クエリ集（Q5 重複排除含む） |
| `.claude/skills/web-search/SKILL.md` | Web 検索ツール選択基準 |
| `.claude/skills/alphaxiv-search/SKILL.md` | alphaxiv MCP ルール（並列制御・トークン節約） |
| `src/data_pipeline/storage/raw_store.py` | RawStore 実装 |
| `scripts/emit_research_queue.py` | graph-queue JSON 生成（Phase 3 以降） |
