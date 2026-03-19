# Neo4j 直書き禁止ルール

research-neo4j へのアドホック Cypher 直書きを禁止し、全データ投入を標準パイプライン経由に限定する。

## 禁止事項

**`research-write_neo4j_cypher` によるノード・リレーションの直接作成は禁止。**

以下の操作を Cypher 直書きで行ってはならない:

- `CREATE (n:Label {...})` によるノード作成
- `MERGE (n:Label {...})` によるノード作成
- `CREATE (a)-[:REL]->(b)` によるリレーション作成
- `MERGE (a)-[:REL]->(b)` によるリレーション作成

### 例外

以下の操作のみ `research-write_neo4j_cypher` の直接使用を許可する:

| 操作 | 例 | 条件 |
|------|-----|------|
| スキーマ操作 | `CREATE CONSTRAINT ...` / `CREATE INDEX ...` | 制約・インデックスの作成・削除 |
| 修復作業 | `MATCH ... SET ...` / `MATCH ... DELETE ...` | ユーザーの明示的承認がある場合のみ |

## 必須パイプライン

全データ投入は以下の2段パイプラインで行うこと:

```
emit_graph_queue.py → /save-to-graph
```

### ステップ1: graph-queue JSON 生成

```bash
uv run python scripts/emit_graph_queue.py --command web-research --input <input.json>
```

入力 JSON から graph-queue 形式の中間 JSON を生成する。

### ステップ2: グラフ投入

```
/save-to-graph <graph-queue.json>
```

graph-queue JSON を読み込み、KG v2 スキーマに準拠したノード・リレーションを一括投入する。

### web-research コマンド

アドホック調査データ（Web検索・論文・レポート等）の標準投入経路。
`emit_graph_queue.py --command web-research` で graph-queue JSON を生成し、`/save-to-graph` で投入する。

## 違反実績（証跡）

過去にアドホック Cypher 直書きで発生した問題の記録。パイプラインを経由しなかったことで、リレーションが欠落した。

| バッチ | 日付 | 件数 | 欠落リレーション |
|---|---|---|---|
| ISATデータ | 3/16 | 80件 | ABOUT(45件) + TAGGED(80件) |
| ASEANデータ | 3/18 | 108件 | EXTRACTED_FROM(73件) + TAGGED(35件) + ABOUT(7件) |
| インドネシア政経 | 3/19 | 35件 | 全欠落 → 事後修正 |

これらの事案では、ノードは作成されたがリレーションが一切作成されず、孤立ノードが大量に発生した。事後の修復作業に多大な工数を要した。

## 読み取りの自由

**`research-read_neo4j_cypher` は制限なし。**

読み取り専用クエリ（`MATCH ... RETURN ...`）は自由に実行してよい。分析・検索・レポート生成等に制約はない。

## 投入前チェックリスト（5項目）

データ投入の実行前に、以下の5項目を全て確認すること:

- [ ] 入力 JSON に `sources[].authority_level` が設定されているか
- [ ] `facts[].source_url` が `sources` 内の URL と一致しているか
- [ ] `emit_graph_queue.py --command web-research` で graph-queue JSON が生成できるか
- [ ] graph-queue JSON の `fact_entity` のリレーションタイプが `RELATES_TO` であるか
- [ ] `/save-to-graph` 実行前に MATCH クエリで対象データ件数を確認したか

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `scripts/emit_graph_queue.py` | graph-queue JSON 生成スクリプト |
| `.claude/rules/neo4j-namespace-convention.md` | Neo4j 名前空間・命名規約 |
