---
description: Neo4j の Claim ノードに claim_type/sentiment/magnitude を付与する
argument-hint: [--limit <N>] [--dry-run] [--resume]
---

# /restructure-claims - Claim 再構造化コマンド

Neo4j に蓄積された Claim ノード（現在すべて `claim_type: "analysis"`）を
AI エージェントが12種の claim_type + sentiment + magnitude に分類し直す。

## 背景

- dec-schema-003: Claim再構造化の合意
- act-schema-001: Phase 1 実装タスク
- 現状686件すべてが `claim_type: "analysis"` で未分類

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --limit | 0 (全件) | 処理件数を制限（テスト用） |
| --dry-run | false | 分類結果を表示するがNeo4jに書き込まない |
| --resume | false | classified_at が既に付与されたClaimをスキップ |

## 使用例

```bash
# テスト: 10件だけ分類してNeo4jに書き込む
/restructure-claims --limit 10

# ドライラン: 分類結果を確認するだけ
/restructure-claims --limit 5 --dry-run

# 全件処理（中断可能、--resume で再開）
/restructure-claims

# 前回の続きから再開
/restructure-claims --resume
```

## 処理フロー

```
Phase 1: Claim 取得
    | mcp__neo4j-cypher__note-finance-read_neo4j_cypher で Claim + Source を取得
    | --resume 時は classified_at IS NULL のもののみ
    |
Phase 2: バッチ分類
    | 20件ずつバッチにまとめて分類
    | 各バッチで以下を判定:
    |   - claim_type (12種から1つ)
    |   - sentiment (-1.0〜1.0)
    |   - magnitude (0.0〜1.0)
    |
Phase 3: Neo4j 書き戻し
    | mcp__neo4j-cypher__note-finance-write_neo4j_cypher で MATCH + SET
    | classified_at タイムスタンプも付与
    |
Phase 4: サマリー報告
    | claim_type 別の件数集計を表示
    | sentiment の分布を表示
```

## claim_type 定義（12種）

dec-schema-003 に基づく:

| claim_type | 説明 | sentiment傾向 |
|------------|------|--------------|
| bullish | 株/市場/セクターへの強気見通し | +0.3〜+1.0 |
| bearish | 株/市場/セクターへの弱気見通し | -1.0〜-0.3 |
| earnings_beat | 決算が予想を上回った | +0.3〜+0.8 |
| earnings_miss | 決算が予想を下回った | -0.8〜-0.3 |
| guidance_up | フォワードガイダンスの上方修正 | +0.3〜+0.7 |
| guidance_down | フォワードガイダンスの下方修正 | -0.7〜-0.3 |
| policy_hawkish | 金融引き締めシグナル | -0.5〜+0.1 |
| policy_dovish | 金融緩和シグナル | +0.1〜+0.5 |
| sector_rotation | セクター間の資金移動 | -0.3〜+0.3 |
| risk_event | 地政学/規制/システミックリスク | -0.8〜-0.1 |
| technical | チャートパターン/テクニカル分析 | -0.5〜+0.5 |
| fundamental | バリュエーション/財務分析 | -0.5〜+0.5 |

## 分類ルール

各Claimの分類時、以下の情報を考慮する:

1. **Claim content**: 主な分類根拠
2. **Source title**: 文脈の補助情報
3. **Entity names**: 関連企業/指標（ABOUTリレーション経由）

### 分類の優先順位

1. earnings_beat / earnings_miss → 決算関連キーワードがある場合
2. guidance_up / guidance_down → ガイダンス/フォーキャスト言及
3. policy_hawkish / policy_dovish → 金利/FRB/中央銀行関連
4. risk_event → 地政学/規制/制裁/危機
5. sector_rotation → セクター/資金移動
6. bullish / bearish → 一般的な市場見通し
7. technical / fundamental → 分析手法に関する言及

## Cypher クエリ

### Phase 1: Claim 取得

```cypher
// 未分類 Claim の取得（--resume 時）
MATCH (s:Source)-[:MAKES_CLAIM]->(c:Claim)
WHERE c.classified_at IS NULL
OPTIONAL MATCH (c)-[:ABOUT]->(e:Entity)
WITH s, c, collect(DISTINCT e.name) AS entity_names
RETURN c.claim_id AS claim_id,
       c.content AS content,
       s.title AS source_title,
       s.source_type AS source_type,
       entity_names
ORDER BY s.collected_at DESC
LIMIT $limit
```

### Phase 3: 書き戻し

```cypher
// バッチ更新（UNWIND パターン）
UNWIND $batch AS item
MATCH (c:Claim {claim_id: item.claim_id})
SET c.claim_type = item.claim_type,
    c.sentiment = item.sentiment,
    c.magnitude = item.magnitude,
    c.classified_at = datetime()
RETURN count(c) AS updated
```

## 実行手順（エージェント向け）

### Step 1: パラメータ解析

引数を解析して limit / dry_run / resume を設定。

### Step 2: Claim 取得

`mcp__neo4j-cypher__note-finance-read_neo4j_cypher` で Claim を取得。

- --resume: `WHERE c.classified_at IS NULL` を追加
- --limit N: `LIMIT N` を追加

### Step 3: バッチ分類ループ

20件ずつのバッチに分割し、各バッチについて:

1. Claim の content / source_title / entity_names を一覧にする
2. 12種の claim_type 定義と照合して分類
3. sentiment (-1.0〜1.0) と magnitude (0.0〜1.0) を判定
4. 結果を JSON 配列として構造化

**分類時の注意**:
- content がタイトルのコピーの場合が多い（source_title と同一）→ タイトルから判断
- Entity情報も考慮する（例: "Fed" → policy系, "Tesla" + "earnings" → earnings系）
- 不明な場合は fundamental をデフォルトに

### Step 4: Neo4j 書き戻し

--dry-run でなければ `mcp__neo4j-cypher__note-finance-write_neo4j_cypher` で更新。

UNWIND パターンでバッチ書き込み:
```cypher
UNWIND $batch AS item
MATCH (c:Claim {claim_id: item.claim_id})
SET c.claim_type = item.claim_type,
    c.sentiment = item.sentiment,
    c.magnitude = item.magnitude,
    c.classified_at = datetime()
RETURN count(c) AS updated
```

### Step 5: サマリー報告

処理完了後、以下を表示:
- 処理件数
- claim_type 別の件数分布
- sentiment の平均/最小/最大
- エラーがあった場合はその件数

## 前提条件

1. Neo4j が起動中であること
2. `mcp__neo4j-cypher__note-finance-*` MCP ツールが利用可能であること

## 関連

- dec-schema-001〜003: Neo4j 4層アーキテクチャ設計
- act-schema-001: Claim sentiment 付与タスク
- act-schema-002: Entity sector/industry 付与タスク
- scripts/restructure_claims.py: Python版（API Key要、CLI実行用）
