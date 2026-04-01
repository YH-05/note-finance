# Cypher クエリ タイムアウト インシデントレポート

**発生日**: 2026-04-01  
**対象インスタンス**: research-neo4j（bolt://localhost:7688）  
**ステータス**: 解決済み（クエリ書き換えで回避）

---

## 1. インシデント概要

TLKMリサーチメモのKGデータ補完作業中、Factノード取得クエリがタイムアウトで失敗した。

**エラーメッセージ**:
```
Neo4j Error: {neo4j_code: Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration}
The transaction has not completed within the timeout specified at its start by the client.
```

---

## 2. 失敗クエリと成功クエリの比較

### ❌ タイムアウトしたクエリ

```cypher
MATCH (e:Entity)-[:ABOUT]-(f:Fact)
WHERE e.entity_key IN [
  'Telkom Indonesia::company',
  'TLKM (Telkom Indonesia)::company',
  'PT Telkom Indonesia (Persero) Tbk::company'
]
RETURN f.content, f.created_at, f.source_url, f.fact_type
ORDER BY f.created_at DESC
LIMIT 30
```

### ✅ 成功したクエリ

```cypher
MATCH (f:Fact)-[:ABOUT]->(e:Entity)
WHERE e.name = 'Telkom Indonesia' AND e.ticker = 'TLKM IJ'
RETURN f.content, f.created_at, f.source_url
ORDER BY f.created_at DESC
LIMIT 30
```

---

## 3. 根本原因分析

### 原因1: リレーション方向の未指定（主因）

| 記法 | 挙動 | スキャン対象 |
|------|------|------------|
| `-[:ABOUT]-`（無方向） | 両方向を探索 | Fact・Claim・Chunk・FinancialDataPoint・Source → Entity **すべて** |
| `-[:ABOUT]->`（有方向） | 一方向のみ | Fact → Entity のみ |

`ABOUT` リレーションは5,343件存在し（`overview.md` §5参照）、接続先ノードはFact以外にもClaim・FinancialDataPointが含まれる。無方向クエリはこれら全種類を候補として展開するため、フィルタリング前のスキャン対象が大幅に増加する。

### 原因2: スタートノードの選択ミス

タイムアウトしたクエリは `(e:Entity)` から出発し、そこから `ABOUT` を辿ってFactを探索する設計。これはEntityノード（1,647件）を先に絞り込んでからFactを展開する意図だが、**Entityノードにマッチした後にABOUTリレーションを全展開**するためFactが多い場合に重くなる。

成功クエリは `(f:Fact)` からスタートし、`ABOUT` を辿ってEntityでフィルタリングする。Factノード（3,103件）は少なく、かつ方向付きリレーションで早期刈り込みが効く。

### 原因3: `entity_key` IN句 × 3値

`entity_key` にはUNIQUE制約（インデックスあり）が存在するが、IN句で3値を指定した場合、Neo4jは各値に対して個別にインデックスルックアップを行い、3エンティティ分のABOUTリレーションを展開後にマージする。成功クエリの `e.name = '...' AND e.ticker = '...'` は単一エンティティを確実に特定するため展開数が少ない。

---

## 4. 技術詳細: スキャン量の見積もり

```
タイムアウトクエリの展開パス:
  Entity（3件マッチ）
    × ABOUT双方向（推定: Fact方向5,343 + 逆方向も含む）
    × Fact候補展開
  → ORDER BY created_at（インデックスなし） → タイムアウト

成功クエリの展開パス:
  Fact（3,103件）
    -[:ABOUT]→ Entity（RANGE index on name, UNIQUE index on ticker）
    WHERE フィルタ → 早期刈り込み
  → ORDER BY created_at DESC
  → LIMIT 30
```

`created_at` プロパティは Fact ノードに RANGE インデックスなし（`overview.md` §6参照）。ORDER BY のコストも積み上がった。

---

## 5. 再発防止: Cypher クエリ設計チェックリスト

### 5-1. 必須: リレーション方向を必ず明示する

```cypher
-- ❌ 禁止（無方向）
MATCH (a)-[:ABOUT]-(b)

-- ✅ 推奨（有方向）
MATCH (a)-[:ABOUT]->(b)
MATCH (a)<-[:ABOUT]-(b)
```

このKGにおける ABOUT リレーションの正方向:

| from | → | to |
|------|---|-----|
| Fact | ABOUT | Entity系 |
| Claim | ABOUT | Entity系 |
| FinancialDataPoint | ABOUT | Entity系 |
| Source | ABOUT | Entity系 |

### 5-2. スタートノードを「選択性が高い側」から始める

| パターン | 推奨 | 理由 |
|---------|------|------|
| 特定エンティティの全Fact取得 | `Fact -[:ABOUT]→ Entity` | Factが少なく方向が明確 |
| 特定ソースの全Claim取得 | `Source -[:MAKES_CLAIM]→ Claim` | Sourceから出発が自然 |
| エンティティ間の影響関係 | `Entity -[:INFLUENCES]→ Entity` | 件数が少ない（1,637件） |

### 5-3. 複数エンティティをIN句で指定する場合はLIMITを先に置く

```cypher
-- 改善案: IN句使用時はサブクエリで先に絞り込む
MATCH (e:Entity)
WHERE e.entity_key IN ['A::company', 'B::company', 'C::company']
WITH e
MATCH (f:Fact)-[:ABOUT]->(e)
RETURN f.content, f.created_at
ORDER BY f.created_at DESC
LIMIT 30
```

### 5-4. `ORDER BY` に使うプロパティを確認する

インデックスのないプロパティでのORDER BYは、全件ソートのコストが発生する。
`created_at`（Fact）はRANGEインデックスなし → LIMITが早期に効かない場合は重くなる。

現在インデックスのあるプロパティ（Factノード）:
- `fact_id`（UNIQUE）
- `fact_type`（RANGE）
- `as_of_date`（RANGE）
- `source_url`（RANGE）

---

## 6. 今後の改善提案

| 提案 | 優先度 | 内容 |
|------|--------|------|
| Fact.created_at にRANGEインデックス追加 | 中 | `ORDER BY created_at DESC` を効率化 |
| クエリルール更新 | 高 | `.claude/rules/neo4j-query-construction.md` に「リレーション方向必須」を明記 |
| Claim.created_at にRANGEインデックス追加 | 低 | 同様の問題を予防 |

---

## 7. 関連ドキュメント

| ドキュメント | 場所 |
|------------|------|
| Cypher クエリ構築ルール | `.claude/rules/neo4j-query-construction.md` |
| リレーション一覧・件数 | `docs/research-neo4j/overview.md` §5 |
| インデックス・制約一覧 | `docs/research-neo4j/overview.md` §6 |
| インシデント発生作業 | `equity_research/TLKM_IJ/research_memo/ir_meeting_prep_20260401.md` |
