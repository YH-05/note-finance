# research-enrichment スキル実装計画

## Context

research-neo4j（bolt://localhost:7688）にはEntity 1013件、Fact 1518件等のデータがあるが、WealthManagement Fact 0件、主要テック企業（AMD, Broadcom等）のFact空洞20+件、Google/Microsoft鮮度12ヶ月超、SEC EDGAR取得可能なFDP未収集20+件という深刻なギャップがある。creator-enrichmentと同様のループ型自動拡充スキルを構築し、`--until` 指定時刻まで Gap分析→検索→LLM構造化→投入を繰り返すことで、これらのギャップを体系的に埋める。

3回の議論（disc-2026-03-24-research-enrichment-design, disc-2026-03-25-research-enrichment-design, disc-2026-03-25-research-enrichment-detail）で全設計判断が確定済み。

## 作成ファイル一覧

| # | パス | 行数目安 | 目的 |
|---|------|---------|------|
| 1 | `data/config/research-enrichment-config.json` | ~60行 | Gap分析重み・検索設定・RawStore設定 |
| 2 | `.claude/skills/research-enrichment/references/gap-analysis-queries.md` | ~150行 | 4軸Cypherクエリ + 統合スコア算出ロジック |
| 3 | `.claude/skills/research-enrichment/references/search-strategy.md` | ~200行 | 動的ソース選択 + フォールバック + RawStore |
| 4 | `.claude/skills/research-enrichment/references/transform-prompt.md` | ~250行 | LLM構造化プロンプト（web-research入力JSON生成） |
| 5 | `.claude/skills/research-enrichment/SKILL.md` | ~750行 | Phase 0-6 オーケストレーション（メイン） |
| 6 | `.claude/commands/research-enrichment.md` | ~15行 | スラッシュコマンド定義 |

## 実装順序

### Step 1: Config ファイル作成

**ファイル**: `data/config/research-enrichment-config.json`

```json
{
  "version": "1.0",
  "gap_analysis": {
    "weights": { "category": 0.15, "entity": 0.35, "staleness": 0.30, "financial": 0.20 },
    "max_targets_per_cycle": 5,
    "staleness_threshold_days": 90,
    "min_facts_per_topic": 5
  },
  "search": {
    "en_queries_per_target": 2,
    "ja_queries_per_target": 2,
    "reddit_subreddits": ["investing", "stocks", "SecurityAnalysis", "wallstreetbets"],
    "sec_edgar": { "filing_types": ["10-K", "10-Q", "8-K"], "max_filings_per_entity": 3 },
    "alphaxiv": { "max_papers": 3, "categories": ["Technology", "EquityResearch"] },
    "query_templates": {
      "en": ["{entity_name} {ticker} financial analysis {year}", "{entity_name} {sector} outlook {year}"],
      "ja": ["{entity_name} 決算 分析 {year}", "{entity_name} {sector_ja} 動向 {year}"]
    }
  },
  "fallback": { "browser_use_max_urls": 3 },
  "rawstore": { "enabled": true, "exclude_sources": ["sec_edgar", "alphaxiv"] },
  "cycle_settings": { "min_cycle_interval_seconds": 30, "max_consecutive_empty_cycles": 3, "empty_cycle_wait_seconds": 60 }
}
```

### Step 2: Gap分析リファレンス

**ファイル**: `.claude/skills/research-enrichment/references/gap-analysis-queries.md`

内容:
- Q1: カテゴリバランス（ConceptCategory → Topic → Fact、実データ検証済み）
- Q2: Entity空洞（ticker あり & Fact 0件）
- Q3: 鮮度（as_of_date 昇順）
- Q4: 財務データ（sec_cik あり & FDP 0件）
- Q5: 重複排除（直近7日Source URL一覧）
- 統合スコア算出ロジック:
  - category_gap: `1 - min(facts_per_topic / 5, 1.0)`
  - entity_gap: Fact 0件 → 1.0、1件以上 → 0.0
  - staleness: `min(days_since_latest / 90, 1.0)`、Fact 0件 → 1.0
  - financial_gap: FDP 0件 & sec_cik あり → 1.0
  - unified_score = 0.15 * cat + 0.35 * ent + 0.30 * stale + 0.20 * fin
- セッション内ダンピング: 処理済みEntity のスコア × 0.3

### Step 3: 検索戦略リファレンス

**ファイル**: `.claude/skills/research-enrichment/references/search-strategy.md`

内容:
- ターゲット属性→ソース選択マトリクス:
  - 常時: Tavily/WebSearch EN×2 + JA×2 + Reddit
  - ticker あり: SEC EDGAR（`get_recent_filings`, `get_financials`, `get_key_metrics`）
  - Technology/EquityResearch: alphaxiv（`embedding_similarity_search` 優先、`get_paper_content` 2-3件ずつ）
  - description 未登録: Wikipedia（`get_summary`）
- フォールバックチェーン: Tavily → WebSearch → browser-use CLI
- RawStore保存ルール: SEC EDGAR・alphaxiv以外を保存、source_id = `research-{entity_key}`
- raw_items[] 正規化フォーマット（source_url, title, content, source_type, authority_level, target_entity）

### Step 4: Transform プロンプトリファレンス

**ファイル**: `.claude/skills/research-enrichment/references/transform-prompt.md`

内容:
- タスク1: Fact/Claim 2分類（数値・統計→Fact、意見・予測→Claim）
- タスク2: Entity抽出（research-neo4j の entity_type に準拠: company/person/organization/index/sector等）
- タスク3: Topic推定（ConceptCategory ベース）
- タスク4: authority_level 判定（official/analyst/media/blog/social/academic）
- 出力JSON: `emit_research_queue.py --command web-research` 入力仕様に完全準拠
  - sources[].url, sources[].authority_level（必須）
  - facts[].content, facts[].source_url（必須、sources内URLと一致）
  - claims[].content, claims[].claim_type, claims[].sentiment
  - topics[].name, topics[].category
- SEC EDGAR 財務データ直接マッピング（LLMバイパス）: `fact_type: "financial_metric"`, `confidence: 1.0`

**再利用する既存コード**:
- `scripts/emit_research_queue.py` L3646-4078: `_build_wr_sources()`, `_build_wr_facts()`, `_build_wr_claims()` の入力検証ロジックを参照し、必須フィールドをプロンプトに明記

### Step 5: SKILL.md（メイン）

**ファイル**: `.claude/skills/research-enrichment/SKILL.md`

**テンプレート**: `.claude/skills/creator-enrichment/SKILL.md`（724行）をベースに差分適用

#### creator-enrichment からの主要差分

| Phase | creator-enrichment | research-enrichment |
|-------|-------------------|-------------------|
| 0 Init | neo4j-creator MCP | **neo4j-research** + SEC EDGAR + alphaxiv + Wikipedia MCP |
| 1 Gap | ジャンルローテーション | **4軸統合スコア上位3-5件バッチ** |
| 2 Search | ジャンル固定5ステップ | **ターゲット属性ベース動的ソース選択** |
| 3 Transform | Fact/Tip/Story + Entity/Concept | **Fact/Claim + web-research入力JSON** |
| 4 Save | emit_creator_queue_v2.py → /save-to-creator-graph | **entity_linker.py --instance research → emit_research_queue.py → /save-to-research-graph** |
| 4.5 | Cross-Entity RELATES_TO | **なし**（research-neo4j は既にリレーション豊富） |
| 5 Loop | 同構造 | 同構造（--until - 5分ルール同一） |
| 6 Summary | Embedding更新 + 自動修復3種 | **TAGGED retroactive のみ**（Embedding不要） |

#### Phase 4 パイプライン手順（確定）

```bash
# 4-0. Entity Linker
export $(grep -E '^NEO4J_PASSWORD=' .env | xargs) && \
uv run --extra embedding python scripts/entity_linker.py \
  --input .tmp/research-cycle-{cycle_id}.json --instance research

# 4-1. graph-queue JSON 生成
uv run python scripts/emit_research_queue.py \
  --command web-research --input .tmp/research-cycle-{cycle_id}.resolved.json

# 4-2. 投入前チェック（neo4j-write-rules 5項目）
# 4-3. /save-to-research-graph --file .tmp/graph-queue/web-research/gq-*.json
# 4-4. 投入検証Cypher
```

### Step 6: スラッシュコマンド

**ファイル**: `.claude/commands/research-enrichment.md`

SKILL.md + 3つの references を Read して実行開始するエントリポイント。

## 検証方法

### 個別検証

| Step | 検証方法 |
|------|---------|
| 1 Config | `python -c "import json; json.load(open('data/config/research-enrichment-config.json'))"` |
| 2 Gap | Q1-Q4 を `mcp__neo4j-research__research-read_neo4j_cypher` で個別実行 |
| 3 Search | AMD (ticker=AMD, sec_cik=2488, sector=IT) でソース選択マトリクスを手動確認 |
| 4 Transform | サンプル raw_item → LLM → emit入力JSON の必須フィールド照合 |
| 5 SKILL | `--dry-run` で Phase 0-3 実行、`.tmp/research-cycle-*.json` 生成確認 |
| 6 Command | `/research-enrichment --until {now+30m} --dry-run` 実行 |

### フル統合テスト

```bash
/research-enrichment --until {now+30min} --focus-entity "AMD"
```

1サイクル完了後に research-neo4j で確認:
```cypher
MATCH (s:Source) WHERE s.command_source = 'web-research'
AND s.created_at >= datetime() - duration('PT30M')
RETURN count(s) AS new_sources
```

## リスクと対策

| リスク | 対策 |
|--------|------|
| emit_research_queue.py 入力仕様不整合 | transform-prompt.md で必須フィールド（authority_level, source_url照合）を明記 |
| Tavily レート早期消費（5ターゲット×4クエリ=20/cycle） | queries_per_target=2 に抑制、Wikipedia等はWebFetch代替 |
| 同一ターゲット反復選定 | セッション内ダンピング（処理済み × 0.3） |
| コンテキスト肥大化 | raw_items と LLM出力は .tmp/ ファイルに書出し、プロンプトにはサマリーのみ |

## 参照ファイル

| ファイル | 用途 |
|---------|------|
| `.claude/skills/creator-enrichment/SKILL.md` | Phase構造テンプレート（724行） |
| `.claude/skills/creator-enrichment/references/entity-extraction-prompt-v2.md` | LLMプロンプト参考（288行） |
| `scripts/emit_research_queue.py` L3646-4078 | web-research 入力仕様 |
| `scripts/entity_linker.py` | `--instance research` 対応 |
| `.claude/rules/neo4j-write-rules.md` | emit経由必須ルール |
| `docs/plan/SideBusiness/2026-03-25_discussion-research-enrichment-skill-design.md` | 設計議論1（Phase構成確定） |
| `docs/plan/SideBusiness/2026-03-25_discussion-research-enrichment-detail.md` | 設計議論2（スコア重み・Config・Cypher確定） |
| `docs/plan/SideBusiness/2026-03-24_discussion-research-enrichment-design.md` | 初回設計議論（2層アーキテクチャ・4軸・フォールバック） |
