# Skill Improvement Proposal Template

skill-analytics の分析データに基づいてスキルの改善提案を作成するためのテンプレート。
skill-creator のステップ 6（改善提案モード）で使用する。

## テンプレート構造

改善提案は以下の 5 セクションで構成する。

---

## 1. Evidence（実行データ）

SkillRun の定量データを記載する。`skill-analytics` クエリの結果をそのまま引用すること。

```markdown
### Evidence

**対象スキル**: `{skill_name}`
**集計期間**: {start_date} - {end_date}
**総実行数**: {total_runs}

| 指標 | 値 | 閾値 | 判定 |
|------|-----|------|------|
| 失敗率 | {fail_rate}% | > 15% | {PASS/FAIL} |
| 平均フィードバックスコア | {avg_score} | < 0.6 | {PASS/FAIL} |
| 平均実行時間 | {avg_duration_ms} ms | - | 参考 |
| タイムアウト率 | {timeout_rate}% | - | 参考 |

**エラータイプ分布**:

| エラータイプ | 件数 | 割合 |
|-------------|------|------|
| {error_type_1} | {count} | {pct}% |
| {error_type_2} | {count} | {pct}% |

**カスケード障害**: {あり/なし}
- {parent_skill} -> {skill_name}: {occurrence} 件
```

### 記載ルール

- 全ての数値は `skill-analytics` のクエリ結果から取得すること
- 主観的評価や推測は記載しない
- 閾値の判定は機械的に行う（失敗率 > 15% or フィードバックスコア < 0.6 で FAIL）

---

## 2. Issues（問題の特定）

Evidence から特定された具体的な問題を列挙する。

```markdown
### Issues

#### Issue 1: {問題タイトル}

- **重大度**: Critical / High / Medium / Low
- **根拠**: {Evidence セクションのどのデータに基づくか}
- **影響範囲**: {影響を受けるスキル/ワークフロー}
- **発生パターン**: {いつ/どの条件で発生するか}

#### Issue 2: {問題タイトル}

...
```

### 重大度の基準

| 重大度 | 基準 |
|--------|------|
| Critical | 失敗率 > 30% or カスケード障害を引き起こしている |
| High | 失敗率 > 15% or フィードバックスコア < 0.4 |
| Medium | フィードバックスコア < 0.6 or 実行時間が平均の 2 倍以上 |
| Low | 軽微なエラーパターン、改善余地あり |

---

## 3. Proposed Changes（改善案）

各 Issue に対する具体的な変更内容を記載する。

```markdown
### Proposed Changes

#### Change 1: {変更タイトル}（→ Issue 1 対応）

- **変更対象**: `{file_path}`
- **変更種別**: 修正 / 追加 / 削除 / リファクタリング
- **変更内容**:
  - {具体的な変更の説明 1}
  - {具体的な変更の説明 2}
- **期待される効果**: {定量的な改善目標}
  - 失敗率: {current}% -> {target}%
  - フィードバックスコア: {current} -> {target}

#### Change 2: {変更タイトル}（→ Issue 2 対応）

...
```

### 変更案の制約

- 1 つの Change は 1 つの Issue に対応すること（1:1 マッピング）
- 期待される効果は定量的に記載すること
- スキルの SKILL.md フロントマター（name, description, allowed-tools）の変更は慎重に行うこと
- 大規模な構造変更は複数の小さな Change に分割すること

---

## 4. Rollback Criteria（ロールバック基準）

改善適用後にロールバックが必要となる条件を定義する。

```markdown
### Rollback Criteria

**評価期間**: 改善適用後 {N} 回の実行（推奨: 5 回以上）

#### 自動ロールバック条件（いずれか 1 つで発動）

- [ ] 失敗率が改善前より 10% ポイント以上悪化
- [ ] フィードバックスコアが改善前より 0.15 以上低下
- [ ] 新しいエラータイプが 2 種類以上出現
- [ ] カスケード障害が新規に発生

#### ロールバック手順

1. `git log --oneline -5` で改善コミットのハッシュを特定
2. `git revert {commit_hash}` でリバートコミットを作成
3. `skill-analytics` で変更前のベースラインに戻ったことを確認

#### ロールバック後のアクション

- ロールバック理由を Issue コメントに記録
- 改善提案を再検討し、段階的な適用を計画
```

---

## 5. Verification（検証計画）

改善の効果を測定するための検証計画を定義する。

```markdown
### Verification

#### ベースライン

改善適用前の直近 10 件の SkillRun データを記録する。

```cypher
WITH datetime() AS now
MATCH (sr:SkillRun {skill_name: '{skill_name}'})
WHERE sr.start_at <= now
WITH sr ORDER BY sr.start_at DESC LIMIT 10
RETURN sr.skill_run_id AS id,
       sr.status AS status,
       sr.duration_ms AS duration,
       sr.feedback_score AS score,
       toString(sr.start_at) AS started
```

| 指標 | ベースライン値 |
|------|---------------|
| 失敗率 | {baseline_fail_rate}% |
| 平均フィードバックスコア | {baseline_avg_score} |
| 平均実行時間 | {baseline_avg_duration} ms |

#### 検証実行

改善適用後、最低 5 回のスキル実行を行い、以下を記録する。

#### Keep/Rollback 判定

| 判定 | 条件 |
|------|------|
| **Keep** | 失敗率が 20% ポイント以上低下 **OR** フィードバックスコアが 0.1 以上向上 |
| **Rollback** | Keep 条件を満たさない **OR** ロールバック基準に該当 |

#### 比較クエリ

```cypher
// 改善前後の比較（改善適用日時を {amend_datetime} に設定）
WITH datetime('{amend_datetime}') AS amend_at
MATCH (sr:SkillRun {skill_name: '{skill_name}'})
WITH sr,
     CASE WHEN sr.start_at < amend_at THEN 'before' ELSE 'after' END AS period
WITH period,
     count(sr) AS total,
     sum(CASE WHEN sr.status IN ['failure', 'timeout'] THEN 1 ELSE 0 END) AS failures,
     avg(sr.feedback_score) AS avg_score,
     avg(sr.duration_ms) AS avg_duration
RETURN period,
       total,
       failures,
       round(toFloat(failures) / total * 100, 1) AS fail_rate_pct,
       round(avg_score, 2) AS avg_feedback_score,
       round(avg_duration, 0) AS avg_duration_ms
ORDER BY period
```
```

---

## 使用例

### 例: save-to-graph スキルの改善提案

```markdown
## 1. Evidence

**対象スキル**: `save-to-graph`
**集計期間**: 2026-02-18 - 2026-03-18
**総実行数**: 45

| 指標 | 値 | 閾値 | 判定 |
|------|-----|------|------|
| 失敗率 | 17.8% | > 15% | FAIL |
| 平均フィードバックスコア | 0.72 | < 0.6 | PASS |
| 平均実行時間 | 3200 ms | - | 参考 |
| タイムアウト率 | 2.2% | - | 参考 |

## 2. Issues

#### Issue 1: Neo4j 接続タイムアウトによる間欠的失敗

- **重大度**: High
- **根拠**: 失敗 8 件中 5 件が neo4j_connection エラー
- **影響範囲**: save-to-graph, pdf-to-knowledge（カスケード）
- **発生パターン**: Docker コンテナ再起動直後に集中

## 3. Proposed Changes

#### Change 1: 接続リトライロジックの追加（→ Issue 1 対応）

- **変更対象**: `.claude/skills/save-to-graph/SKILL.md`
- **変更種別**: 追加
- **変更内容**:
  - Neo4j 接続失敗時のリトライガイダンスを追加（3 回、指数バックオフ）
  - 接続確認ステップをワークフロー冒頭に追加
- **期待される効果**:
  - 失敗率: 17.8% -> 5% 以下

## 4. Rollback Criteria

- 失敗率が 27.8% 以上に悪化 → ロールバック
- 新しいエラータイプが出現 → ロールバック

## 5. Verification

| 指標 | ベースライン | 目標 |
|------|-------------|------|
| 失敗率 | 17.8% | < 5% |
| 平均実行時間 | 3200 ms | 変化なし |

Keep 条件: 失敗率が -20% ポイント以上低下 → 目標: 17.8% -> -2.2% (0%)
```
