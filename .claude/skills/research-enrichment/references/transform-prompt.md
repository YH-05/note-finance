# Transform Prompt — research-enrichment Phase 3

`raw_items[]` から `emit_research_queue.py --command web-research` の入力仕様に完全準拠した
JSON を生成する LLM プロンプトテンプレート。SKILL.md Phase 3 から参照される。

> **参照**: `emit_research_queue.py` の `map_web_research()` が実際の入力バリデーションを行う。
> 出力 JSON がこの関数の入力仕様から逸脱すると **KeyError / ValueError でクラッシュする**。

---

## 出力先

```
.tmp/research-cycle-{cycle_id}.json
```

- `cycle_id`: セッション内のサイクル番号（例: `01`, `02`）
- Phase 3 完了後、このファイルを `emit_research_queue.py --command web-research --input` に渡す

---

## LLM プロンプトテンプレート

```
あなたは金融データ構造化の専門家です。
以下の raw_items（Web検索・Reddit等の非構造化テキスト）を、
graph-queue 入力仕様に準拠した JSON に変換してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
重要: authority_level は全 source に【必須】です。
欠損すると emit_research_queue.py が KeyError でクラッシュします。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 入力データ（raw_items）

{raw_items_json}

## ターゲット Entity

- entity_key: {entity_key}
- name: {entity_name}
- ticker: {ticker}
- sector: {sector}

## 変換ルール

### 1. sources[] の構築

各 raw_item を 1 つの source に変換する。

必須フィールド:
- url (str, 必須): raw_item の source_url をそのまま使用
- title (str): raw_item の title
- source_type (str): raw_item の source_type（web / social / news / blog）
- authority_level (str, 【必須】): 以下の6種から判定
  - "official"  — 企業公式サイト、IR、プレスリリース
  - "analyst"   — アナリストレポート、Seeking Alpha、Morningstar
  - "media"     — CNBC、Bloomberg、Reuters、WSJ、日経
  - "blog"      — 個人ブログ、テック系メディア
  - "social"    — Reddit 投稿・コメント
  - "academic"  — 学術論文、arXiv

authority_level 判定基準（URLドメイン）:
→ `references/search-strategy.md` の「authority_level の自動判定」テーブルを参照すること。

### 2. facts[] の構築（検証可能な事実）

数値データ・統計・イベント・公式発表など、客観的に検証可能な記述を抽出する。

**分類基準: Fact = 数値/統計/イベント/公式発表。検証可能かどうかが判断基準。**

必須フィールド:
- content (str, 【必須】): 事実の記述。具体的な数値を含めること
- source_url (str, 【必須】): 抽出元 source の url と【完全一致】すること
- confidence (float): 0.0〜1.0。一次情報=1.0、メディア報道=0.8-0.9、個人分析=0.5-0.7
- fact_type (str): 以下から選択
  - "financial_metric"    — 売上高、利益、PER、ROE 等の財務指標
  - "operational_kpi"     — MAU、出荷台数、契約数等の事業KPI
  - "market_event"        — 上場、M&A、株式分割等のイベント
  - "economic_indicator"  — GDP、CPI、失業率等のマクロ指標
  - "regulatory"          — 規制変更、政策発表
  - "research_finding"    — 学術論文の発見・研究結果
  - "statistic"           — 一般的な統計データ
  - "event"               — その他のイベント・出来事
  - "data_point"          — 上記に該当しない数値データ
- about_entities (list[dict]): 関連 Entity（後述の entity_type 14種で正規化）

### 3. claims[] の構築（意見・予測・分析）

アナリストの見解、市場予測、主観的な評価を抽出する。

**分類基準: Claim = 意見/予測/分析/推奨。主観的判断を含むかどうかが判断基準。**

必須フィールド:
- content (str, 【必須】): 意見・予測の記述
- source_url (str): 抽出元 source の url と一致させること
- claim_type (str): 以下から選択
  - "analyst_opinion"     — アナリストの定性的見解
  - "analyst_forecast"    — 業績予想、目標株価
  - "market_consensus"    — 市場コンセンサス
  - "policy_expectation"  — 政策予想
  - "risk_assessment"     — リスク評価
  - "recommendation"      — 投資推奨（Buy/Hold/Sell）
  - "forecast"            — 一般的な将来予測
  - "analysis"            — 分析・考察
  - "sector_view"         — セクター見通し
- sentiment (str): "positive" | "negative" | "neutral"
- about_entities (list[dict]): 関連 Entity

### 4. topics[] の構築

記事のテーマカテゴリを 1-3 件推定する。

フィールド:
- name (str): トピック名（英語、具体的に）
- category (str): 以下の ConceptCategory 8 種から選択
  - "macro"               → MacroEconomics（マクロ経済）
  - "stock"               → EquityResearch（株式リサーチ）
  - "sector"              → SectorAnalysis（セクター分析）
  - "investment_strategy"  → InvestmentStrategy（投資戦略）
  - "technology"           → Technology（テクノロジー）
  - "wealth"              → WealthManagement（資産形成）
  - "regulation"           → Regulation（規制）
  - "content_planning"     → ContentPlanning（コンテンツ企画）

### 5. Entity 抽出 — entity_type 14 種に正規化

facts[].about_entities と claims[].about_entities で使用する entity_type は、
以下の 14 種の正規型のいずれかに正規化すること。

| entity_type | 説明 | 例 |
|-------------|------|-----|
| company | 企業 | Apple, トヨタ, AMD |
| technology | テクノロジー | AI, 5G, ブロックチェーン |
| organization | 機関 | FRB, IMF, 日銀, SEC |
| person | 人物 | Warren Buffett, 植田和男 |
| index | 株価指数 | S&P 500, TOPIX, Nasdaq |
| indicator | 経済指標 | GDP, CPI, 失業率 |
| instrument | 金融商品 | ETF, 国債, ドル/円 |
| commodity | コモディティ | 原油, 金, 銅 |
| country | 国・地域 | 米国, 日本, EU |
| sector | セクター | 半導体, ヘルスケア |
| concept | 概念 | バリュー投資, QE |
| regulation | 規制・政策 | Basel III, GDPR |
| broker | ブローカー | Goldman Sachs（証券部門） |
| product | プロダクト | iPhone, AWS, MI300X |

**正規化例**:
- "fintech" → "company"
- "central_bank" → "organization"
- "etf" → "instrument"
- "currency" → "instrument"
- "government" → "organization"
- "metric" → "indicator"
- "event" → "concept"

### 6. Fact vs Claim 判定フローチャート

```
記述を読む
  │
  ├── 数値・統計データを含む？
  │   ├── YES → Fact (fact_type: financial_metric / statistic / data_point)
  │   └── NO ↓
  │
  ├── 客観的イベント・出来事？
  │   ├── YES → Fact (fact_type: market_event / event / regulatory)
  │   └── NO ↓
  │
  ├── 公式発表・一次情報？
  │   ├── YES → Fact (fact_type 適宜)
  │   └── NO ↓
  │
  ├── 意見・予測・分析的判断を含む？
  │   ├── YES → Claim (claim_type 適宜)
  │   └── NO ↓
  │
  └── 一般的な記述 → Fact (fact_type: "event" or "data_point")
```

## 出力 JSON フォーマット

```json
{
  "sources": [
    {
      "url": "https://www.cnbc.com/2026/03/20/amd-ai-chip-demand.html",
      "title": "AMD's AI Chip Demand Surges in Q1 2026",
      "source_type": "news",
      "authority_level": "media",
      "publisher": "CNBC"
    },
    {
      "url": "https://www.reddit.com/r/stocks/comments/abc123/amd_q1",
      "title": "AMD Q1 Earnings Discussion",
      "source_type": "social",
      "authority_level": "social",
      "publisher": "Reddit"
    },
    {
      "url": "https://seekingalpha.com/article/amd-valuation-2026",
      "title": "AMD: AI Tailwinds and Valuation",
      "source_type": "web",
      "authority_level": "analyst",
      "publisher": "Seeking Alpha"
    }
  ],
  "facts": [
    {
      "content": "AMD reported Q1 2026 revenue of $7.4 billion, up 35% year-over-year",
      "source_url": "https://www.cnbc.com/2026/03/20/amd-ai-chip-demand.html",
      "confidence": 0.9,
      "fact_type": "financial_metric",
      "about_entities": [
        {"name": "AMD", "entity_type": "company"}
      ]
    },
    {
      "content": "AMD MI300X AI accelerator shipments exceeded 500,000 units in Q1",
      "source_url": "https://www.cnbc.com/2026/03/20/amd-ai-chip-demand.html",
      "confidence": 0.9,
      "fact_type": "operational_kpi",
      "about_entities": [
        {"name": "AMD", "entity_type": "company"},
        {"name": "MI300X", "entity_type": "product"}
      ]
    }
  ],
  "claims": [
    {
      "content": "AMD's data center GPU market share could reach 20% by end of 2026",
      "source_url": "https://seekingalpha.com/article/amd-valuation-2026",
      "claim_type": "analyst_forecast",
      "sentiment": "positive",
      "about_entities": [
        {"name": "AMD", "entity_type": "company"}
      ]
    }
  ],
  "topics": [
    {
      "name": "AMD AI Chip Revenue Growth",
      "category": "stock"
    },
    {
      "name": "AI Semiconductor Market",
      "category": "technology"
    }
  ]
}
```

## 検証チェックリスト（LLM 出力の自己チェック）

出力 JSON を生成した後、以下を必ず検証すること:

- [ ] 全 sources[] に authority_level が存在するか（【必須】、欠損で KeyError）
- [ ] authority_level は 6 種（official / analyst / media / blog / social / academic）のいずれか
- [ ] 全 facts[] に content が存在するか（【必須】）
- [ ] 全 facts[] に source_url が存在するか（【必須】）
- [ ] facts[].source_url が sources[].url のいずれかと【完全一致】するか（不一致で Fact スキップ）
- [ ] claims[].source_url が sources[].url のいずれかと一致するか（不一致で Claim スキップ）
- [ ] entity_type が 14 種の正規型のいずれかに正規化されているか
- [ ] topics[].category が ConceptCategory 8 種に対応する値か
- [ ] facts と claims の分類が正しいか（数値/統計→Fact、意見/予測→Claim）

```

---

## SEC EDGAR / alphaxiv 直接マッピング

SEC EDGAR・alphaxiv の直接マッピングルールは `references/search-strategy.md` の「SEC EDGAR / alphaxiv 直接マッピング（LLM バイパス）」セクションを参照すること。本ファイル（transform-prompt.md）は LLM 構造化の対象である `raw_items[]` のみを扱う。

---

## リスクと対策

| リスク | 重大度 | 対策 |
|--------|:------:|------|
| authority_level 欠損 | **HIGH** | プロンプトで強調表示、検証チェックリストで確認 |
| facts[].source_url と sources[].url の不一致 | **HIGH** | URL 一致ルール明示、検証チェックリストで確認 |
| entity_type が正規型外 | MEDIUM | 14 種の正規化マッピング表を提示 |
| Fact と Claim の誤分類 | MEDIUM | 判定フローチャートを提示 |
| topics[].category が不正 | LOW | ConceptCategory 8 種の選択肢を明示 |

---

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `references/search-strategy.md` | Phase 2 検索戦略・raw_items[] 正規化フォーマット |
| `references/gap-analysis-queries.md` | Phase 1 ギャップ分析クエリ集 |
| `scripts/emit_research_queue.py` | graph-queue JSON 生成（`map_web_research()` が入力仕様を定義） |
| `src/data_pipeline/structurer/extractor.py` | data-pipeline の LLM 抽出プロンプト（参考） |
