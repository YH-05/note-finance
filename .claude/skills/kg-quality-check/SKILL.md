---
name: kg-quality-check
description: |
  research-neo4j (bolt://localhost:7688) のナレッジグラフ品質を計測・評価するスキル。
  7カテゴリの定量指標に加え、Claude Code 自身が LLM-as-Judge として accuracy 評価と
  創発的発見ポテンシャル（Emergent Discovery）評価を実行する。
  スナップショット保存・前回比較・アラート・Markdownレポート生成を一括で行う。
  「KG品質」「グラフ品質」「ナレッジグラフ計測」「品質チェック」「品質ダッシュボード」
  「accuracy評価」「品質スコア」「KGスコア」「創発的発見」「仮説構築」
  と言われたら必ずこのスキルを使うこと。
  Use PROACTIVELY when the user asks about knowledge graph quality, data quality metrics,
  or after bulk data ingestion to verify quality.
---

# kg-quality-check

research-neo4j のナレッジグラフ品質を計測し、Claude Code が LLM-as-Judge として
Fact/Claim の accuracy と創発的発見ポテンシャルを直接評価するスキル。

## 処理フロー

```
Phase 1: 6カテゴリ計測（Python スクリプト）
    |  scripts/kg_quality_metrics.py --skip-accuracy --save-snapshot
    |  structural / completeness / consistency / timeliness / finance_specific / discoverability
    |
Phase 2: accuracy 評価（Claude Code LLM-as-Judge）
    |  research-neo4j から Fact/Claim をサンプリング（MCP Cypher）
    |  Claude Code が3軸で評価（Factual / Grounding / Temporal）
    |  評価結果をキャッシュに書き込み
    |
Phase 3: 創発的発見ポテンシャル評価（Claude Code LLM-as-Judge）
    |  5つの Cypher プローブでグラフ構造を探索
    |  Claude Code が発見・仮説を試行し、4軸で自己評価
    |  結果を JSON レポートに保存
    |
Phase 4: 統合スナップショット再計測
    |  キャッシュ済み accuracy を含む全7カテゴリ再計測
    |  前回スナップショットとの比較
    |  アラート評価
    |
Phase 5: レポート出力
    定量スコア + 創発的発見レポート + 改善提案をユーザーに提示
```

## Phase 1: 6カテゴリ計測

accuracy 以外の6カテゴリを Python スクリプトで計測する。

```bash
uv run python scripts/kg_quality_metrics.py \
    --skip-accuracy \
    --save-snapshot \
    --report data/processed/kg_quality/report_$(date +%Y%m%d).md
```

## Phase 2: accuracy 評価（LLM-as-Judge）

ANTHROPIC_API_KEY が不要な Claude Code 直接評価方式。

### 2.1 Fact/Claim サンプリング

`mcp__neo4j-research__research-read_neo4j_cypher` で20件サンプリング:

```cypher
MATCH (f)
WHERE NOT 'Memory' IN labels(f)
AND (f:Fact OR f:Claim)
AND f.content IS NOT NULL
OPTIONAL MATCH (f)<-[:STATES_FACT|MAKES_CLAIM]-(c:Chunk)
OPTIONAL MATCH (c)<-[:CONTAINS_CHUNK]-(s:Source)
RETURN
    coalesce(f.fact_id, f.claim_id, elementId(f)) AS fact_id,
    f.content AS content,
    labels(f) AS node_labels,
    s.title AS source_title,
    s.url AS source_url,
    toString(s.fetched_at) AS source_fetched_at
ORDER BY rand()
LIMIT 20
```

### 2.2 3軸評価

各 Fact/Claim を以下の3軸で評価する（各 0.0-1.0）:

| 軸 | 重み | 評価基準 |
|---|---:|---|
| Factual Correctness | 40% | 内容が事実として正しいか。具体的数値・固有名詞が含まれるほど高評価 |
| Source Grounding | 30% | Source ノードとリンクされているか。URL・タイトルが存在するか |
| Temporal Validity | 30% | 情報が現在も有効か。歴史的データは高、日次ニュースは低 |

**評価の目安**:
- **0.8-1.0**: 具体的データ、ソースリンクあり、時間的に有効
- **0.5-0.7**: まあまあ正確、ソース不明、中程度の時間的価値
- **0.2-0.4**: 曖昧・主観的、ノイズ（広告・HTML断片・タイトルのみ）
- **0.0-0.1**: 明らかに不正確または完全にノイズ

### 2.3 キャッシュ書き込み

評価結果を `data/processed/kg_quality/accuracy_cache.json` に書き込む:

```python
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

def content_hash(c):
    return hashlib.sha256(c.encode('utf-8')).hexdigest()[:16]

cache = {}
now = datetime.now(tz=timezone.utc).isoformat()
for fact in evaluated_facts:
    key = content_hash(fact['content'])
    overall = fact['fc'] * 0.4 + fact['sg'] * 0.3 + fact['tv'] * 0.3
    cache[key] = {
        'fact_id': fact['fact_id'],
        'factual_correctness': fact['fc'],
        'source_grounding': fact['sg'],
        'temporal_validity': fact['tv'],
        'overall': round(overall, 3),
        'reasoning': fact['reasoning'],
        'evaluated_at': now,
    }

p = Path('data/processed/kg_quality/accuracy_cache.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
```

Bash ツールで Python ワンライナーとして実行する。

## Phase 3: 創発的発見ポテンシャル評価（Emergent Discovery）

KG の真の価値は「個別ソースの読解だけでは得られない、グラフ構造から浮かび上がる
新しい洞察や仮説を AI が構築できるか」にある。Phase 3 では Claude Code が
5つの構造プローブを実行し、実際に発見・仮説構築を試行して自己評価する。

### 3.1 構造プローブ（5つの Cypher クエリ）

以下の5つのプローブを `mcp__neo4j-research__research-read_neo4j_cypher` で順に実行する。

**Probe A: クロスドメイン・ブリッジ** — 異なる entity_type の Entity が Fact を共有するパターン

```cypher
MATCH (e1:Entity)<-[:RELATES_TO]-(f:Fact)-[:RELATES_TO]->(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2) AND NOT 'Memory' IN labels(f)
AND e1.entity_type <> e2.entity_type
AND elementId(e1) < elementId(e2)
RETURN e1.name + ' (' + e1.entity_type + ')' AS entity1,
       e2.name + ' (' + e2.entity_type + ')' AS entity2,
       count(DISTINCT f) AS shared_facts,
       collect(DISTINCT f.content)[..2] AS sample_content
ORDER BY shared_facts DESC LIMIT 10
```

**Probe B: 間接接続パス** — 直接つながっていないが、2ホップで到達可能な Entity ペア

```cypher
MATCH (e1:Entity)-[:RELATES_TO]-(f1)-[:RELATES_TO]-(bridge:Entity)-[:RELATES_TO]-(f2)-[:RELATES_TO]-(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2) AND NOT 'Memory' IN labels(bridge)
AND e1 <> e2 AND e1 <> bridge AND e2 <> bridge
AND e1.entity_type <> e2.entity_type
AND NOT EXISTS { MATCH (e1)-[:RELATES_TO]-(:Fact)-[:RELATES_TO]-(e2) }
RETURN e1.name AS from_entity, e1.entity_type AS from_type,
       bridge.name AS via_bridge, bridge.entity_type AS bridge_type,
       e2.name AS to_entity, e2.entity_type AS to_type
ORDER BY rand() LIMIT 5
```

**Probe C: Stance 対立** — 同一 Entity に対する異なる見解・評価の存在

```cypher
MATCH (s:Stance)-[:ON_ENTITY]->(e:Entity)
WHERE NOT 'Memory' IN labels(s) AND NOT 'Memory' IN labels(e)
WITH e, collect({type: s.stance_type, content: s.summary}) AS stances, count(s) AS cnt
WHERE cnt >= 2
RETURN e.name AS entity, cnt AS stance_count, stances[..4] AS sample_stances
ORDER BY cnt DESC LIMIT 5
```

**Probe D: Insight / information_gap** — 既存の分析的発見とギャップ

```cypher
MATCH (i:Insight)
WHERE NOT 'Memory' IN labels(i)
RETURN i.insight_type AS type, i.content AS content
ORDER BY i.insight_type, rand()
LIMIT 10
```

**Probe E: Topic クラスタ間ブリッジ** — 異なる Topic カテゴリにまたがる Entity

```cypher
MATCH (e:Entity)<-[:RELATES_TO]-(f)-[:TAGGED]->(t:Topic)
WHERE NOT 'Memory' IN labels(e) AND NOT 'Memory' IN labels(f) AND NOT 'Memory' IN labels(t)
AND t.category IS NOT NULL
WITH e, collect(DISTINCT t.category) AS categories, count(DISTINCT t) AS topic_count
WHERE size(categories) >= 2
RETURN e.name AS entity, e.entity_type AS type, categories, topic_count
ORDER BY topic_count DESC LIMIT 10
```

### 3.2 発見・仮説構築の試行

プローブ結果を読み、以下を**実際に試行**する（最低3件）:

1. **クロスドメイン仮説**: Probe A/B の結果から、異なるドメインの Entity 間の
   因果関係や波及効果の仮説を1つ以上構築する
   - 例: 「原油価格(commodity) → インドネシア経常収支(macro) → テレコムARPU(company)」

2. **矛盾・緊張の発見**: Probe C/D の結果から、同一テーマで矛盾する
   Fact/Claim/Stance を特定し、その含意を分析する
   - 例: 「Bull/Bear が分かれる根拠の構造的差異」

3. **知識ギャップ発見**: Probe D/E の結果から、グラフに欠けている
   接続や情報を特定し、調査すべき問いを生成する
   - 例: 「規制(regulatory)と企業戦略(strategy)をつなぐ Fact が欠落」

### 3.3 4軸自己評価

試行した発見・仮説について、以下の4軸で自己評価する（各 0.0-1.0）:

| 軸 | 重み | 評価基準 |
|---|---:|---|
| Cross-Domain Bridging | 30% | 異なるドメインの Entity/Topic を横断する洞察を生成できたか。個別ソースの読解では得られない「グラフならでは」の発見か |
| Hypothesis Novelty | 25% | 構築した仮説は非自明か。既存 Insight の再発見ではなく、新しい問いや因果構造を提示できたか |
| Evidence Density | 25% | 仮説を支える Fact/Claim/FinancialDataPoint の量は十分か。薄い根拠に基づく推測ではなく、複数のエビデンスで裏付けられているか |
| Actionability | 20% | 発見が実際の投資判断やリサーチ方向性に影響を与え得るか。「面白いが使えない」発見ではなく、次のアクションを導くか |

**評価の目安**:
- **0.8-1.0**: 3ドメイン以上をまたぐ仮説、十分なエビデンス、明確なアクション
- **0.5-0.7**: 2ドメイン横断、中程度のエビデンス、方向性は示せる
- **0.2-0.4**: 単一ドメイン内の発見、エビデンス不足、アクション不明
- **0.0-0.1**: 発見なし、または自明な再発見のみ

### 3.4 結果保存

評価結果を `data/processed/kg_quality/discovery_report_YYYYMMDD.json` に保存:

```json
{
  "timestamp": "2026-03-19T...",
  "probes_summary": {
    "cross_domain_pairs": 10,
    "indirect_paths": 5,
    "stance_entities": 3,
    "insights_existing": 23,
    "multi_topic_entities": 8
  },
  "discoveries": [
    {
      "type": "cross_domain_hypothesis",
      "title": "仮説タイトル",
      "description": "詳細な記述",
      "entities_involved": ["Entity1", "Entity2"],
      "supporting_evidence": ["Fact/Claim の要約"],
      "evidence_count": 5
    }
  ],
  "scores": {
    "cross_domain_bridging": 0.7,
    "hypothesis_novelty": 0.6,
    "evidence_density": 0.5,
    "actionability": 0.6,
    "overall": 0.63
  },
  "improvement_suggestions": [
    "Source Grounding 強化で仮説の信頼性向上",
    "CONTRADICTS リレーション追加で矛盾検出力向上"
  ]
}
```

## Phase 4: 統合スナップショット再計測

キャッシュ済み accuracy を含む全7カテゴリで再計測:

```bash
uv run python scripts/kg_quality_metrics.py \
    --save-snapshot \
    --compare latest \
    --alert \
    --report data/processed/kg_quality/report_$(date +%Y%m%d).md
```

## Phase 5: レポート出力

結果をユーザーに提示する。以下を含める:

1. **Overall Score と Rating**（A/B/C/D）
2. **7カテゴリのスコア表**
3. **前回比較**（改善/悪化カテゴリ）
4. **CheckRules 違反サマリー**
5. **accuracy 評価の特記事項**（ノイズデータ、Source Grounding の弱点等）
6. **創発的発見レポート**:
   - 発見した仮説（3件以上）
   - 4軸スコアと総合評価
   - グラフ構造の弱点と改善提案
7. **改善提案**（定量 + 創発的発見の両面から）

## 使用する MCP サーバー

| MCP サーバー | 用途 |
|-------------|------|
| `mcp__neo4j-research__research-read_neo4j_cypher` | Fact/Claim サンプリング, 構造プローブ |

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `scripts/kg_quality_metrics.py` | 品質計測メインスクリプト |
| `scripts/kg_accuracy_judge.py` | accuracy 評価モジュール（API版、参考用） |
| `scripts/kg_quality_alert.py` | アラート・Issue自動作成 |
| `data/config/kg_accuracy_config.yaml` | accuracy 評価設定 |
| `data/processed/kg_quality/` | スナップショット・キャッシュ・発見レポート保存先 |

## MUST / SHOULD / NEVER

### MUST
- Phase 2 の accuracy 評価は Claude Code が直接 MCP 経由で Fact を取得し評価すること
- Phase 3 の5つの構造プローブを全て実行し、最低3件の発見・仮説を試行すること
- 発見・仮説は4軸で自己評価し、discovery_report JSON に保存すること
- 評価結果はキャッシュファイルに書き込み、Phase 4 でスクリプトが読み取れるようにすること

### SHOULD
- 評価時にノイズデータ（広告・HTML断片・タイトルのみ）を特記すること
- Source Grounding が低い場合はリレーション補完を提案すること
- 前回の discovery_report と比較し、発見能力のトレンドを報告すること
- 構築した仮説が既存 Insight と重複する場合はその旨を明記すること

### NEVER
- ANTHROPIC_API_KEY に依存する API 呼び出しを行ってはならない
- accuracy 評価をスキップしてはならない（このスキルの核心機能）
- 構造プローブなしに発見スコアを付けてはならない（データ駆動が原則）
