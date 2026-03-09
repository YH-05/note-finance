---
name: case-study-critique
description: 事例分析型記事の4観点批評スキル。データ正確性・分析の深さ・実用性・構成バランスの4エージェントを並列スポーンし、統合レポートを生成する。
allowed-tools: Read, Bash, Agent, Glob, Grep
---

# Case Study Critique Skill

## 目的

事例分析型記事（テンプレートA/B/C）を4つの観点から並列批評し、
統合された品質レポートを生成する。

## いつ使用するか

### プロアクティブ使用

以下の状況で自動的に使用を検討:

1. **事例分析型記事の初稿完成後**
   - 「記事を批評して」「品質をチェックして」
   - ファイル名に `csa-` プレフィックスがある記事
2. **記事の改訂後の再批評**
   - 「修正したので再チェック」

### 明示的な使用

- 記事執筆フローの批評フェーズで呼び出し

## テンプレートタイプの判定

記事のデータカードまたはファイル名からテンプレートタイプを判定:

| テンプレート | 判定パターン |
|-------------|-------------|
| A | データカードに `記事タイプ: ジャンル別事例分析` |
| B | データカードに `記事タイプ: ジャンル横断共通点分析` |
| C | データカードに `記事タイプ: AI一人スタートアップ事例分析` |

判定できない場合はユーザーに確認する。

## プロセス

### ステップ 1: 入力の取得

1. **記事ファイルパスの確認**
   - 引数で渡されるか、カレントディレクトリから `csa-*.md` を探す
2. **記事の読み込み**
3. **テンプレートタイプの判定**
4. **Neo4j から関連データを取得**（任意）

```cypher
// CaseStudyArticle と関連 SuccessCase を取得
MATCH (a:CaseStudyArticle {article_id: $article_id})-[:ANALYZES]->(sc:SuccessCase)
RETURN a, sc
```

### ステップ 2: 4エージェント並列スポーン

4つの批評エージェントを**並列**で起動する。

各エージェントに渡すプロンプトの共通構造:

```
以下の事例分析型記事を批評してください。

## テンプレートタイプ
{template_type} （A / B / C）

## テンプレート別基準
参照: .claude/resources/case-study-criteria/templates/{template_type}.md

## 記事内容
{記事の全文}

JSON形式で結果を出力してください。
```

#### 2.1 データ正確性批評

```yaml
subagent_type: "csa-critic-data"
description: "事例分析データ正確性批評"
prompt: |
  以下の事例分析型記事のデータ正確性を批評してください。

  ## テンプレートタイプ
  {template_type}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

#### 2.2 分析の深さ批評

```yaml
subagent_type: "csa-critic-analysis"
description: "事例分析の深さ批評"
prompt: |
  以下の事例分析型記事の分析の深さを批評してください。

  ## テンプレートタイプ
  {template_type}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

#### 2.3 実用性批評

```yaml
subagent_type: "csa-critic-actionability"
description: "事例分析の実用性批評"
prompt: |
  以下の事例分析型記事の実用性を批評してください。

  ## テンプレートタイプ
  {template_type}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

#### 2.4 構成バランス批評

```yaml
subagent_type: "csa-critic-structure"
description: "事例分析の構成バランス批評"
prompt: |
  以下の事例分析型記事の構成バランスを批評してください。

  ## テンプレートタイプ
  {template_type}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

### ステップ 3: 結果統合

4エージェントの JSON 結果を統合する。

#### 3.1 スコア統合

```yaml
scores:
  data_accuracy: 0    # csa-critic-data のスコア（0-100）
  analysis_depth: 0   # csa-critic-analysis のスコア（0-100）
  actionability: 0    # csa-critic-actionability のスコア（0-100）
  structure: 0        # csa-critic-structure のスコア（0-100）

# 加重平均
overall_score:
  data_accuracy: 30%
  analysis_depth: 30%
  actionability: 20%
  structure: 20%
```

#### 3.2 issue 統合

全エージェントの issues を severity でソートし、統合リストを作成。

#### 3.3 公開可否判定

- data_accuracy が F (0-39) → **公開不可**
- analysis_depth が F (0-39) → **公開不可**
- 総合スコア < 60 → **公開非推奨**
- 総合スコア >= 75 → **公開推奨**

### ステップ 4: レポート出力

#### 4.1 ターミナル出力（マークダウン）

```markdown
# 事例分析型批評レポート

## 記事情報
- **ファイル**: {file_path}
- **テンプレート**: {template_type} ({template_label})
- **総文字量**: {wordcount}字

## 総合評価

| 観点 | スコア | グレード |
|------|--------|---------|
| データ正確性 | {score}/100 | {grade} |
| 分析の深さ | {score}/100 | {grade} |
| 実用性 | {score}/100 | {grade} |
| 構成バランス | {score}/100 | {grade} |
| **総合** | **{score}/100** | **{grade}** |

**判定**: {公開推奨 / 公開非推奨 / 公開不可}

## 改善が必要な点

### [必須] Critical/High
- {issue}

### [推奨] Medium
- {issue}

### [任意] Low
- {issue}

## 良い点
- {strength}

## 改善優先度
1. {top_priority}
2. {second_priority}
3. {third_priority}
```

#### 4.2 JSON レポート出力

**出力先**: 記事と同じディレクトリに `critique.json` として保存。

```json
{
  "metadata": {
    "generated_at": "YYYY-MM-DD HH:MM:SS",
    "article_path": "{file_path}",
    "template_type": "{template_type}",
    "template_label": "{template_label}",
    "critique_type": "case_study"
  },
  "scores": {
    "data_accuracy": 0,
    "analysis_depth": 0,
    "actionability": 0,
    "structure": 0,
    "overall": 0
  },
  "verdict": "publish_recommended | publish_not_recommended | publish_blocked",
  "details": {
    "data_accuracy": { "... csa-critic-data の完全な出力 ..." },
    "analysis_depth": { "... csa-critic-analysis の完全な出力 ..." },
    "actionability": { "... csa-critic-actionability の完全な出力 ..." },
    "structure": { "... csa-critic-structure の完全な出力 ..." }
  },
  "all_issues": [
    { "... severity でソートされた統合 issues ..." }
  ],
  "improvement_priorities": [
    "最優先で改善すべき点"
  ]
}
```

### ステップ 5: 完了報告

```
================================================================================
                 事例分析型批評 完了
================================================================================

## 結果サマリー
- データ正確性: {score}/100 ({grade})
- 分析の深さ: {score}/100 ({grade})
- 実用性: {score}/100 ({grade})
- 構成バランス: {score}/100 ({grade})
- 総合: {score}/100 ({grade})

## 判定
{verdict}

## 出力ファイル
- JSON: {critique.json のパス}

## 改善優先度（Top 3）
1. {priority_1}
2. {priority_2}
3. {priority_3}

================================================================================
```

## エラーハンドリング

| 状況 | 対処 |
|------|------|
| 記事ファイルが見つからない | エラーメッセージを表示して終了 |
| テンプレートタイプが判定できない | ユーザーに確認 |
| エージェントがJSON以外を返した | パースを試行し、失敗なら該当観点をスキップして報告 |
| Neo4j 接続失敗 | Neo4j 関連チェックをスキップして続行 |

## エージェント一覧

| エージェント | 役割 | リファレンス（共通） | リファレンス（テンプレート固有） |
|------------|------|---------------------|-------------------------------|
| csa-critic-data | データ正確性 | `data-accuracy-standards.md` | `templates/{type}.md` |
| csa-critic-analysis | 分析の深さ | `analysis-depth-standards.md` | `templates/{type}.md` |
| csa-critic-actionability | 実用性 | `actionability-standards.md` | `templates/{type}.md` |
| csa-critic-structure | 構成バランス | `structure-standards.md` | `templates/{type}.md` |

## リファレンスファイル

| ファイル | パス |
|---------|------|
| スコアリング方式 | `.claude/resources/case-study-criteria/scoring-methodology.md` |
| データ正確性基準 | `.claude/resources/case-study-criteria/data-accuracy-standards.md` |
| 分析深度基準 | `.claude/resources/case-study-criteria/analysis-depth-standards.md` |
| 実用性基準 | `.claude/resources/case-study-criteria/actionability-standards.md` |
| 構成バランス基準 | `.claude/resources/case-study-criteria/structure-standards.md` |
| テンプレートA | `.claude/resources/case-study-criteria/templates/A.md` |
| テンプレートB | `.claude/resources/case-study-criteria/templates/B.md` |
| テンプレートC | `.claude/resources/case-study-criteria/templates/C.md` |
| テンプレート定義 | `docs/plan/SideBusiness/事例分析型テンプレート_v1.md` |

## 完了条件

- [ ] テンプレートタイプが正しく判定されている
- [ ] 4つの批評エージェントが並列実行されている
- [ ] 各エージェントが有効な JSON を返している
- [ ] スコアが統合され、総合判定が出ている
- [ ] critique.json が記事と同じディレクトリに保存されている
- [ ] ターミナルにマークダウンレポートが出力されている
- [ ] 改善優先度が提示されている
