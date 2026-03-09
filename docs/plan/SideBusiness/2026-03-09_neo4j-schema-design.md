# 議論メモ: Neo4jスキーマ設計 - AI知見発見のための4層アーキテクチャ

**日付**: 2026-03-09
**参加**: ユーザー + AI

## 背景・コンテキスト

現在のNeo4jデータベース（約900ノード、2000+リレーション）を分析し、AIが自動的に新しい知見を発見するための改善設計を行った。

### 現状の問題点

1. **Claimがタイトルのコピペ**: 686件のClaimの`content`がソース記事タイトルそのまま。構造化された主張になっていない
2. **センチメント・時系列がゼロ**: トレンド発見が不可能
3. **Entityが平面的**: Sector/Industry階層なし。セクター横断分析不可
4. **ドメイン間が断絶**: Source/Claim系と金融知識系(Concept, FinancialProduct)がほぼ未接続
5. **知見蓄積の場所がない**: Insight/Narrativeノードが不在

## 設計: 4層アーキテクチャ

```
Layer 3: 知見発見層
  [Insight] ← DERIVED_FROM ← [Narrative] → CONTENT_OPPORTUNITY → [CandidateTheme]
  [Signal]  → DETECTED_IN  → [EntitySnapshot]

Layer 2: 時系列・集約層
  [EntitySnapshot] → FOR_ENTITY → [Entity]
  [TopicSnapshot]  → IN_PERIOD  → [TimePeriod] → NEXT → [TimePeriod]

Layer 1: 構造化メタデータ層
  [Entity] → BELONGS_TO_SECTOR → [Sector]
  [Entity] → BELONGS_TO_INDUSTRY → [Industry] → PART_OF → [Sector]
  [Claim] + sentiment + claim_type (拡張プロパティ)

Layer 0: 基盤データ層（既存）
  [Source] → MAKES_CLAIM → [Claim] → ABOUT → [Entity]
  [Source] → TAGGED → [Topic]
```

## Phase 1: Claim品質 + Entity強化

### Claim プロパティ拡張

| プロパティ | 型 | 説明 |
|-----------|-----|------|
| `sentiment` | FLOAT | -1.0(弱気)〜+1.0(強気) |
| `magnitude` | FLOAT | 主張の強さ 0〜1.0 |
| `claim_type` | STRING | 12種に細分化 |
| `metrics` | MAP | 抽出された数値 |
| `extracted_at` | DATETIME | 再構造化日時 |

**claim_type一覧**: bullish / bearish / earnings_beat / earnings_miss / guidance_up / guidance_down / policy_hawkish / policy_dovish / sector_rotation / risk_event / technical / fundamental

### Sector / Industry ノード（新規）

```cypher
MERGE (s:Sector {sector_id: "sec-technology"})
SET s.name = "Technology", s.name_ja = "テクノロジー"

MERGE (i:Industry {industry_id: "ind-semiconductors"})
SET i.name = "Semiconductors", i.name_ja = "半導体"
MERGE (i)-[:PART_OF]->(s)

// Entity接続
MATCH (e:Entity {ticker: "NVDA"})
MERGE (e)-[:BELONGS_TO_INDUSTRY]->(i)
MERGE (e)-[:BELONGS_TO_SECTOR]->(s)
```

### Entity間リレーション

- `(:Entity)-[:RELATED_ENTITY {type: "competitor"|"supplier"|"subsidiary"}]->(:Entity)`

## Phase 2: 時系列構造

### TimePeriod

```
{period_id: "2026-W10", start_date, end_date, granularity: "week"|"month"}
(:TimePeriod)-[:NEXT]->(:TimePeriod)
```

### EntitySnapshot（核心ノード）

```
{snapshot_id: "snap-META-2026-W10",
 avg_sentiment, sentiment_stddev, claim_count,
 bullish_count, bearish_count, bullish_ratio,
 trend: "improving"|"stable"|"deteriorating",
 prev_sentiment, sentiment_change}
```

リレーション: `→ FOR_ENTITY → Entity`, `→ IN_PERIOD → TimePeriod`

### TopicSnapshot

```
{snapshot_id, mention_count, avg_sentiment, trending, momentum}
```

### Claim時間接続

`(:Claim)-[:CLAIMED_IN]->(:TimePeriod)`

## Phase 3: 知見発見レイヤー

### Narrative

```
{narrative_id, name, description,
 status: "emerging"|"established"|"declining"|"contradicted",
 evidence_count, confidence}
```

リレーション:
- `→ CONTAINS_CLAIM → Claim`
- `→ INVOLVES → Entity`
- `→ EVOLVES_INTO → Narrative`
- `→ CONTRADICTS → Narrative`
- `→ CONTENT_OPPORTUNITY → CandidateTheme`

### Insight

```
{insight_id, content,
 insight_type: "trend_change"|"correlation"|"anomaly"|"consensus_shift"|"emerging_theme"|"cross_sector",
 confidence, actionability: "high"|"medium"|"low",
 validated, user_rating}
```

### Signal

```
{signal_id,
 signal_type: "sentiment_reversal"|"volume_spike"|"consensus_break"|"new_narrative"|"cross_sector_divergence",
 severity, description, status: "active"|"expired"|"confirmed"|"invalidated"}
```

## クロスドメイン接続

| リレーション | 効果 |
|-------------|------|
| `Source → MENTIONS_CONCEPT → Concept` | 693記事と金融概念を接続 |
| `Source → MENTIONS_PRODUCT → FinancialProduct` | 記事と金融商品を接続 |
| `Narrative → CONTENT_OPPORTUNITY → CandidateTheme` | 市場テーマ→記事テーマ |
| `Insight → ARTICLE_IDEA → CandidateTheme` | AI知見→記事アイデア |
| `CandidateTheme → MARKET_SIGNAL → EntitySnapshot` | 記事テーマの市場裏付け |

## 実装優先度

| # | 施策 | インパクト | コスト |
|---|------|-----------|--------|
| 1 | Claim sentiment付与 | 高 | 低 |
| 2 | TimePeriod導入 | 高 | 低 |
| 3 | Sector/Industry追加 | 中 | 低 |
| 4 | EntitySnapshot週次計算 | 高 | 中 |
| 5 | Narrative検出 | 高 | 高 |
| 6 | クロスドメイン接続 | 中 | 低 |
| 7 | Insight自動生成 | 最高 | 高 |
| 8 | Signal検出 | 中 | 中 |

## パイプライン概要

```
[週次バッチ]
  1. 新規Source収集 → LLMでClaim構造化+sentiment付与
  2. TimePeriod ノード MERGE
  3. EntitySnapshot / TopicSnapshot 集約計算
  4. Narrative クラスタリング (LLM)
  5. Signal 検出 (ルールベース + LLM)
  6. Insight 生成 (全データ統合 → LLM)
```

## 決定事項

1. Neo4jを4層アーキテクチャに拡張する
2. 実装優先順位: Claim sentiment → TimePeriod → Sector/Industry → EntitySnapshot → Narrative → クロスドメイン → Insight → Signal
3. Claimのclaim_typeを12種に細分化、sentiment/magnitudeを追加

## アクションアイテム

- [ ] Phase 1: 既存686件のClaimをLLMバッチ処理でsentiment/claim_type/metricsを付与 (優先度: 高)
- [ ] Phase 1: 72件のEntityにsector/industry/entity_typeを付与し、Sector/Industryノードを作成 (優先度: 高)
- [ ] Phase 2: TimePeriodノード(週次/月次)を生成し、既存ClaimをCLAIMED_INリレーションで接続 (優先度: 高)
- [ ] Phase 2: EntitySnapshot/TopicSnapshotの週次バッチ集計パイプラインを構築 (優先度: 中)
- [ ] Phase 3: Narrative/Insight/Signalノードの生成ロジックとパイプラインを実装 (優先度: 中)
- [ ] クロスドメイン: Source→Concept/FinancialProduct, Narrative→CandidateTheme の自動リンクを実装 (優先度: 中)

## 次回の議論トピック

- Claim再構造化のLLMプロンプト設計
- Narrative検出のクラスタリングアルゴリズム選定
- Insight生成の品質保証メカニズム（バリデーション＋ユーザーフィードバックループ）

## Neo4j保存先

- Discussion: `disc-2026-03-09-neo4j-schema-design`
- Decision: `dec-2026-03-09-001`, `dec-2026-03-09-002`, `dec-2026-03-09-003`
- ActionItem: `act-2026-03-09-001` 〜 `act-2026-03-09-006`
