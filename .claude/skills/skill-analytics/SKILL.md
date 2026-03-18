---
name: skill-analytics
description: |
  research-neo4j (bolt://localhost:7688) 上の SkillRun ノードを分析し、スキル実行の頻度・失敗率・実行時間・エラーパターン・カスケード障害・KGノード生産性を Markdown テーブルで出力するスキル。
  Use PROACTIVELY when the user asks about skill performance, failure rates, error trends, or observability dashboards.
allowed-tools: Read, Bash, Grep, Glob
---

# skill-analytics

research-neo4j (bolt://localhost:7688) に蓄積された `Memory:SkillRun` ノードを分析し、スキル実行状況を Markdown テーブルレポートとして出力するスキル。

## 目的

このスキルは以下を提供します：

- **実行頻度分析**: スキルごとの実行回数推移
- **失敗率分析**: スキルごとの失敗率とステータス分布
- **実行時間分析**: 週次バケットでの平均実行時間トレンド
- **エラー分析**: error_type 別の発生件数
- **カスケード障害検出**: INVOKED_SKILL リレーションを辿った親子障害パターン
- **KG ノード生産性**: スキル実行あたりの KG ノード生産量

## いつ使用するか

### プロアクティブ使用（自動で検討）

以下の状況では、ユーザーが明示的に要求しなくても参照：

1. **スキルの品質を確認したい場合**
   - 「スキルの失敗率は？」
   - 「最近エラーが多いスキルは？」

2. **パフォーマンス調査**
   - 「実行が遅いスキルは？」
   - 「スキルの実行時間トレンドを見たい」

3. **障害分析**
   - 「カスケード障害のパターンは？」
   - 「エラータイプ別の内訳は？」

### 明示的な使用

- 「skill-analytics を実行して」
- 「スキルの分析レポートを出して」

## 前提条件

1. **research-neo4j が起動していること**
   ```bash
   # 接続テスト
   cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
     -a "bolt://localhost:7688" "RETURN 1"
   ```

2. **SkillRun データが蓄積されていること**
   - `scripts/skill_run_tracer.py` でスキル実行が記録済みであること

## ワークフロー

```
Phase 1: 接続確認 ─── Neo4j 疎通テスト
    |
Phase 2: クエリ実行 ─── 6 クエリ群を順次実行
    |
Phase 3: レポート生成 ─── Markdown テーブルに整形して出力
```

## Phase 1: 接続確認

```bash
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7688}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"

cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "MATCH (sr:SkillRun) RETURN count(sr) AS total_runs"
```

**エラー時**: 接続失敗メッセージを表示して処理中断。

## Phase 2: クエリ実行

6 つのクエリ群を順次実行する。各クエリの詳細は `queries.md` を参照。

| # | クエリ名 | 概要 |
|---|---------|------|
| 1 | スキル実行頻度 | 過去 30 日のスキル別実行回数・成功率 |
| 2 | スキル別失敗率 | 失敗率が高いスキルのランキング |
| 3 | 平均実行時間トレンド | 週次バケットでの実行時間推移 |
| 4 | エラータイプ別発生数 | error_type ごとの件数と代表的なエラーメッセージ |
| 5 | カスケード失敗パターン | INVOKED_SKILL を辿った親子障害の検出 |
| 6 | KG ノード生産性 | スキル実行あたりの KG ノード生産量 |

## Phase 3: レポート生成

クエリ結果を Markdown テーブルに整形し、以下の構造で出力する。

```markdown
# Skill Analytics Report

**集計期間**: {start_date} - {end_date}
**総実行数**: {total_runs}

## 1. スキル実行頻度（過去 30 日）
| スキル名 | 実行回数 | 成功 | 失敗 | 成功率 |
|----------|---------|------|------|--------|
| ...      | ...     | ...  | ...  | ...    |

## 2. 失敗率ワースト
| スキル名 | 総実行 | 失敗数 | 失敗率 | 主なエラータイプ |
|----------|--------|--------|--------|-----------------|
| ...      | ...    | ...    | ...    | ...             |

## 3. 平均実行時間トレンド（週次）
| 週 | 平均実行時間 | 中央値 | 最大値 | 実行数 |
|----|-------------|--------|--------|--------|
| ...| ...         | ...    | ...    | ...    |

## 4. エラータイプ別発生数
| エラータイプ | 件数 | 代表エラーメッセージ |
|-------------|------|---------------------|
| ...         | ...  | ...                 |

## 5. カスケード失敗パターン
| 親スキル | 子スキル | 親ステータス | 子ステータス | 発生回数 |
|----------|---------|-------------|-------------|---------|
| ...      | ...     | ...         | ...         | ...     |

## 6. KG ノード生産性
| スキル名 | 実行回数 | Source | Entity | Claim | Fact | 合計ノード | ノード/実行 |
|----------|---------|--------|--------|-------|------|-----------|------------|
| ...      | ...     | ...    | ...    | ...   | ...  | ...       | ...        |
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --days | 30 | 集計対象日数 |
| --top | 10 | 各ランキングの表示件数 |
| --query | all | 特定クエリのみ実行（1-6 のカンマ区切り） |

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| NEO4J_URI | bolt://localhost:7688 | research-neo4j の Bolt URI |
| NEO4J_USER | neo4j | Neo4j ユーザー名 |
| NEO4J_PASSWORD | (必須) | Neo4j パスワード |

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| Neo4j 接続失敗 | 接続情報を確認。docker ps で research-neo4j コンテナが起動しているか確認 |
| SkillRun ノード未検出 | `scripts/skill_run_tracer.py` でスキル実行を記録してからリトライ |
| クエリタイムアウト | --days を短くして対象期間を絞る |

## 関連リソース

| リソース | パス |
|---------|------|
| クエリ集 | `.claude/skills/skill-analytics/queries.md` |
| SkillRun トレーサー | `scripts/skill_run_tracer.py` |
| スキーママイグレーション | `scripts/migrate_skill_run_schema.py` |
| Neo4j 制約・インデックス | `docker/research-neo4j/init/01-constraints-indexes.cypher` |
| KG スキーマ定義 | `data/config/knowledge-graph-schema.yaml` |

## 完了条件

- [ ] Neo4j 接続が成功する
- [ ] 6 クエリ群が全て正常実行できる
- [ ] Markdown テーブルレポートが出力される
