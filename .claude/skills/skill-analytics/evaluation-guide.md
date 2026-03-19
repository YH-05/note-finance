# Evaluation Guide（改善効果の評価ループ）

スキル改善（Amend）適用後の効果を定量的に評価し、Keep / Rollback を判定するためのガイド。

## 概要

改善提案（`improvement-template.md` に基づく）を適用した後、以下の 4 ステップ評価ループを実行する。

```
Step 1: ベースライン記録
    |
Step 2: 改善適用 + 実行
    |
Step 3: 比較測定
    |
Step 4: Keep / Rollback 判定
```

---

## Step 1: ベースライン記録

改善適用前の直近 10 件の SkillRun データをベースラインとして記録する。

### ベースライン取得クエリ

```cypher
// 対象スキルの直近 10 件を取得
MATCH (sr:SkillRun {skill_name: $skill_name})
WITH sr ORDER BY sr.start_at DESC LIMIT 10
WITH collect(sr) AS runs
UNWIND runs AS sr
WITH sr ORDER BY sr.start_at ASC
RETURN sr.skill_run_id AS id,
       sr.status AS status,
       sr.duration_ms AS duration_ms,
       sr.feedback_score AS feedback_score,
       sr.error_type AS error_type,
       toString(sr.start_at) AS start_at
```

### ベースライン集計クエリ

```cypher
MATCH (sr:SkillRun {skill_name: $skill_name})
WITH sr ORDER BY sr.start_at DESC LIMIT 10
WITH count(sr) AS total,
     sum(CASE WHEN sr.status IN ['failure', 'timeout'] THEN 1 ELSE 0 END) AS failures,
     avg(CASE WHEN sr.feedback_score IS NOT NULL THEN sr.feedback_score END) AS avg_score,
     avg(sr.duration_ms) AS avg_duration
RETURN total,
       failures,
       round(toFloat(failures) / total * 100, 1) AS fail_rate_pct,
       round(coalesce(avg_score, 0), 2) AS avg_feedback_score,
       round(coalesce(avg_duration, 0), 0) AS avg_duration_ms
```

### 記録フォーマット

ベースラインは以下の形式で記録する（改善提案の Verification セクションに転記）。

```markdown
| 指標 | ベースライン値 | 取得日時 |
|------|---------------|---------|
| 総実行数 | {total} | {datetime} |
| 失敗率 | {fail_rate}% | |
| 平均フィードバックスコア | {avg_score} | |
| 平均実行時間 | {avg_duration} ms | |
```

---

## Step 2: 改善適用 + 実行

### 2a: 改善の適用

1. 改善提案に記載された変更を適用する
2. 変更をコミットする（ロールバック用にコミットハッシュを記録）

```bash
# 変更をコミット
git add -A
git commit -m "amend({skill_name}): {改善内容の要約}"

# コミットハッシュを記録
AMEND_COMMIT=$(git rev-parse HEAD)
echo "Amend commit: $AMEND_COMMIT"
```

### 2b: 検証実行

改善適用後、最低 **5 回** のスキル実行を行う。

- 通常のワークフローで実行すること（テスト用の特別な条件は避ける）
- 各実行の SkillRun が正常に記録されていることを確認する

```cypher
// 改善適用後の実行数を確認
WITH datetime($amend_datetime) AS amend_at
MATCH (sr:SkillRun {skill_name: $skill_name})
WHERE sr.start_at >= amend_at
RETURN count(sr) AS post_amend_runs
```

**最低 5 回に満たない場合**: 追加実行を行うか、評価期間を延長する。

---

## Step 3: 比較測定

ベースラインと改善後のデータを比較する。

### 比較クエリ

```cypher
// 改善前後の指標比較
WITH datetime($amend_datetime) AS amend_at
MATCH (sr:SkillRun {skill_name: $skill_name})
WITH sr,
     CASE WHEN sr.start_at < amend_at THEN 'before' ELSE 'after' END AS period
WITH period,
     count(sr) AS total,
     sum(CASE WHEN sr.status IN ['failure', 'timeout'] THEN 1 ELSE 0 END) AS failures,
     avg(CASE WHEN sr.feedback_score IS NOT NULL THEN sr.feedback_score END) AS avg_score,
     avg(sr.duration_ms) AS avg_duration
RETURN period,
       total,
       failures,
       round(toFloat(failures) / total * 100, 1) AS fail_rate_pct,
       round(coalesce(avg_score, 0), 2) AS avg_feedback_score,
       round(coalesce(avg_duration, 0), 0) AS avg_duration_ms
ORDER BY period
```

### エラータイプ変化の確認

```cypher
// 改善前後のエラータイプ分布を比較
WITH datetime($amend_datetime) AS amend_at
MATCH (sr:SkillRun {skill_name: $skill_name})
WHERE sr.status IN ['failure', 'timeout']
  AND sr.error_type IS NOT NULL
WITH CASE WHEN sr.start_at < amend_at THEN 'before' ELSE 'after' END AS period,
     sr.error_type AS error_type,
     count(sr) AS count
RETURN period, error_type, count
ORDER BY period, count DESC
```

### 比較結果フォーマット

```markdown
| 指標 | 改善前 | 改善後 | 差分 | 判定 |
|------|--------|--------|------|------|
| 失敗率 | {before}% | {after}% | {diff}pp | {IMPROVED/DEGRADED/UNCHANGED} |
| 平均フィードバックスコア | {before} | {after} | {diff} | {IMPROVED/DEGRADED/UNCHANGED} |
| 平均実行時間 | {before} ms | {after} ms | {diff} ms | 参考 |
| 新規エラータイプ | - | {count} 種 | - | {OK/WARNING} |
```

---

## Step 4: Keep / Rollback 判定

### Keep 条件（いずれか 1 つを満たす）

| 条件 | 判定基準 |
|------|---------|
| 失敗率改善 | 失敗率が **20 ポイント以上低下** |
| スコア改善 | フィードバックスコアが **0.1 以上向上** |

**例**:
- 失敗率: 25% -> 5% (= -20pp) → Keep
- スコア: 0.5 -> 0.65 (= +0.15) → Keep

### Rollback 条件（いずれか 1 つで発動）

| 条件 | 判定基準 |
|------|---------|
| 失敗率悪化 | 失敗率が改善前より **10 ポイント以上悪化** |
| スコア悪化 | フィードバックスコアが改善前より **0.15 以上低下** |
| 新規エラー | 改善前に存在しなかったエラータイプが **2 種類以上**出現 |
| カスケード障害 | 改善後に**新規のカスケード障害**が発生 |

### 判定フローチャート

```
改善後データ（5件以上）取得済み？
    ├─ No → 追加実行を待つ
    └─ Yes
        ├─ Rollback 条件に該当？
        │   └─ Yes → Rollback 実行
        └─ No
            ├─ Keep 条件を満たす？
            │   └─ Yes → Keep（改善確定）
            └─ No → 様子見（追加 5 件の実行後に再判定）
```

### Rollback 手順

```bash
# 1. 改善コミットを特定
git log --oneline -10

# 2. リバートコミットを作成
git revert {amend_commit_hash}

# 3. リバート後の状態を確認
git diff HEAD~2..HEAD

# 4. skill-analytics で変更前の状態に戻ったことを確認
```

### Rollback 後のアクション

1. ロールバック理由を GitHub Issue のコメントに記録する
2. 改善提案の Issues セクションを見直し、根本原因の再分析を行う
3. 段階的な改善アプローチを検討する（1 つの Change ずつ適用）

---

## 評価レポートフォーマット

評価完了後、以下の形式でレポートを作成する。

```markdown
# Skill Evaluation Report

**対象スキル**: `{skill_name}`
**改善適用日時**: {amend_datetime}
**評価日時**: {eval_datetime}

## ベースライン

| 指標 | 値 |
|------|-----|
| 総実行数 | {baseline_total} |
| 失敗率 | {baseline_fail_rate}% |
| 平均フィードバックスコア | {baseline_avg_score} |

## 改善後

| 指標 | 値 |
|------|-----|
| 総実行数 | {post_total} |
| 失敗率 | {post_fail_rate}% |
| 平均フィードバックスコア | {post_avg_score} |

## 比較

| 指標 | 改善前 | 改善後 | 差分 |
|------|--------|--------|------|
| 失敗率 | {before}% | {after}% | {diff}pp |
| フィードバックスコア | {before} | {after} | {diff} |

## 判定

**結果**: **{Keep / Rollback / 様子見}**

**理由**: {判定理由}

## アクション

- {次のアクション}
```

---

## カスケード障害の評価

改善対象スキルが他スキルから呼び出されている場合、カスケード影響も評価する。

```cypher
// 改善後のカスケード障害を確認
WITH datetime($amend_datetime) AS amend_at
MATCH (parent:SkillRun)-[:INVOKED_SKILL]->(child:SkillRun {skill_name: $skill_name})
WHERE child.start_at >= amend_at
  AND (parent.status IN ['failure', 'timeout']
       OR child.status IN ['failure', 'timeout'])
RETURN parent.skill_name AS parent_skill,
       parent.status AS parent_status,
       child.status AS child_status,
       count(*) AS occurrence
ORDER BY occurrence DESC
```

---

## 関連リソース

| リソース | パス |
|---------|------|
| 改善提案テンプレート | `.claude/skills/skill-expert/improvement-template.md` |
| skill-analytics クエリ集 | `.claude/skills/skill-analytics/queries.md` |
| skill-creator (Step 6: Amend) | `.claude/agents/skill-creator.md` |
| SkillRun スキーマ | `data/config/knowledge-graph-schema.yaml` |
