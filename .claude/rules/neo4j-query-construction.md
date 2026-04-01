# Neo4j Cypher クエリ構築ルール

## 必須: スキーマ事前取得

**Cypher クエリを構築する前に、必ず対象インスタンスの `*-get_neo4j_schema` でスキーマを取得すること。**

静的ファイル（ルールファイル、スキル内のクエリ例、メモリ等）のスキーマ情報に依存してはならない。
グラフDBは常に更新されるため、静的ファイルは投入時点のスナップショットでしかない。

### 手順

```
1. *-get_neo4j_schema を呼ぶ（APOC apoc.meta.schema 経由）
2. 取得したスキーマからラベル・プロパティ・リレーションを確認
3. データ量に応じて LIMIT を動的に決定
4. クエリを構築・実行
```

### インスタンス別ツール

| インスタンス | ポート | スキーマ取得ツール |
|-------------|--------|-------------------|
| research-neo4j | 7688 | `mcp__neo4j-research__research-get_neo4j_schema` |
| note-neo4j | 7687 | `mcp__neo4j-note__note-get_neo4j_schema` |
| creator-neo4j | 7689 | `mcp__neo4j-creator__creator-get_neo4j_schema` |

## LIMIT ガイドライン

LIMIT は固定値ではなく、**スキーマ取得時のノード数に応じて動的に決定**する。

| データ量 | LIMIT 目安 | 用途例 |
|---------|-----------|--------|
| ~100件 | LIMIT なし | 個別銘柄の Fact/Claim 全量取得 |
| 100~500件 | 200 | 銘柄リサーチ、トピック探索 |
| 500~2000件 | 50~100 | クロス銘柄分析、一覧表示 |
| 2000件超 | 20~50 | 探索的クエリ、サンプリング |

### 用途別の指針

- **銘柄レポート執筆**: 対象銘柄の Fact/Claim/DataPoint は**全量取得**（網羅性優先）
- **探索・発見**: LIMIT 20~50 で概要把握 → 必要に応じて絞り込み
- **品質チェック**: LIMIT 50~100 でサンプリング

## 必須: リレーション方向を必ず明示する

**無方向パターン `-[:REL]-` は禁止。必ず方向を指定すること。**

無方向クエリはリレーションを両方向でスキャンするため、接続先ノード種別が多いリレーション（ABOUT等）では全体スキャンに近いコストが発生しタイムアウトする。

```cypher
-- ❌ 禁止（無方向）
MATCH (e:Entity)-[:ABOUT]-(f:Fact)

-- ✅ 推奨（有方向）
MATCH (f:Fact)-[:ABOUT]->(e:Entity)
```

### research-neo4j の主要リレーション正方向

| リレーション | from → to |
|------------|-----------|
| ABOUT | Fact/Claim/FinancialDataPoint/Source → Entity系 |
| MAKES_CLAIM | Source → Claim |
| STATES_FACT | Entity/Organization → Fact |
| EXTRACTED_FROM | Fact/Claim → Source/Chunk |
| CONTAINS_CHUNK | Source → Chunk |
| HAS_DATAPOINT | Entity → FinancialDataPoint |
| TAGGED | [全ノード] → Topic |

### スタートノードの選び方

特定エンティティのFact/Claim取得は「小さい側（Entity）」ではなく「大きい側（Fact/Claim）」から始めて Entity でフィルタリングする方が高速。

```cypher
-- ✅ Fact側からスタート
MATCH (f:Fact)-[:ABOUT]->(e:Entity)
WHERE e.name = 'Telkom Indonesia' AND e.ticker = 'TLKM IJ'
LIMIT 30
```

> **事例**: 2026-04-01、無方向 `-[:ABOUT]-` + entity_key IN句 × 3値でタイムアウト発生。
> 詳細: `docs/research-neo4j/query_incident_20260401.md`

## 禁止事項

- スキーマ取得なしで「たぶんこのラベルがあるはず」とクエリを書くこと
- 過去の会話やメモリの情報だけでリレーションパスを推測すること
- 全インスタンスに同じ固定 LIMIT を適用すること
- **リレーションを無方向で指定すること**（タイムアウトの主因）

## 例外

以下の場合のみスキーマ取得をスキップしてよい:

- **同一会話内で直前にスキーマを取得済み**（数分以内）
- **`db.labels()` 等のメタクエリ自体**を実行する場合
