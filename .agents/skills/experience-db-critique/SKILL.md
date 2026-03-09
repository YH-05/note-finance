---
name: experience-db-critique
description: 体験談DB記事の4観点批評スキル。リアリティ・共感度・埋め込みリンク・文字量バランスの4エージェントを並列スポーンし、統合レポートを生成する。
allowed-tools: Read, Bash, Agent, Glob, Grep
---

# Experience DB Critique Skill

## 目的

体験談DB記事（婚活・副業・資産形成）を4つの観点から並列批評し、
統合された品質レポートを生成する。

## いつ使用するか

### プロアクティブ使用

以下の状況で自動的に使用を検討:

1. **体験談DB記事の初稿完成後**
   - 「記事を批評して」「品質をチェックして」
2. **記事の改訂後の再批評**
   - 「修正したので再チェック」

### 明示的な使用

- 記事執筆フローの批評フェーズで呼び出し

## テーマの判定

記事パスまたはファイル内容からテーマを自動判定する:

| テーマキー | 判定パターン |
|-----------|-------------|
| `konkatsu` | ファイル名に `konkatsu` / 本文に「婚活」「マッチングアプリ」 |
| `sidehustle` | ファイル名に `sidehustle` / 本文に「副業」「クラウドワークス」 |
| `shisan-keisei` | ファイル名に `shisan-keisei` / 本文に「資産形成」「つみたてNISA」 |

判定できない場合はユーザーに確認する。

## プロセス

### ステップ 1: 入力の取得

1. **記事ファイルパスの確認**
   - 引数で渡されるか、カレントディレクトリから `*-pattern-*.md` を探す
2. **記事の読み込み**
3. **テーマの判定**
4. **Neo4j から関連データを取得**（任意）

```cypher
// ExperiencePattern と EmbeddableResource を取得
MATCH (ep:ExperiencePattern)-[:EMBEDS]->(er:EmbeddableResource)
WHERE ep.theme = $theme
RETURN ep, er
```

### ステップ 2: 4エージェント並列スポーン

4つの批評エージェントを**並列**で起動する。

各エージェントに渡すプロンプトの共通構造:

```
以下の体験談DB記事を批評してください。

## テーマ
{theme} （konkatsu / sidehustle / shisan-keisei）

## テーマ固有基準
参照: .claude/resources/experience-db-criteria/themes/{theme}.md

## 記事内容
{記事の全文}

## Neo4j EmbeddableResource データ（embed批評のみ）
{JSON形式のリソースデータ}

JSON形式で結果を出力してください。
```

#### 2.1 リアリティ批評

```yaml
subagent_type: "exp-critic-reality"
description: "体験談リアリティ批評"
prompt: |
  以下の体験談DB記事のリアリティを批評してください。

  ## テーマ
  {theme}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

#### 2.2 共感度批評

```yaml
subagent_type: "exp-critic-empathy"
description: "体験談共感度批評"
prompt: |
  以下の体験談DB記事の共感度を批評してください。

  ## テーマ
  {theme}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

#### 2.3 埋め込みリンク批評

```yaml
subagent_type: "exp-critic-embed"
description: "体験談埋め込みリンク批評"
prompt: |
  以下の体験談DB記事の埋め込みリンクを批評してください。

  ## テーマ
  {theme}

  ## 記事内容
  {article_content}

  ## Neo4j EmbeddableResource データ
  {embed_resources_json}

  JSON形式で結果を出力してください。
```

#### 2.4 文字量バランス批評

```yaml
subagent_type: "exp-critic-balance"
description: "体験談文字量バランス批評"
prompt: |
  以下の体験談DB記事の文字量バランスを批評してください。

  ## テーマ
  {theme}

  ## 記事内容
  {article_content}

  JSON形式で結果を出力してください。
```

### ステップ 3: 結果統合

4エージェントの JSON 結果を統合する。

#### 3.1 スコア統合

```yaml
scores:
  reality: 0      # exp-critic-reality のスコア（0-100）
  empathy: 0      # exp-critic-empathy のスコア（0-100）
  embed: 0        # exp-critic-embed のスコア（0-100）
  balance: 0      # exp-critic-balance のスコア（0-100）

# 加重平均
overall_score:
  reality: 30%
  empathy: 30%
  embed: 15%
  balance: 25%
```

#### 3.2 issue 統合

全エージェントの issues を severity でソートし、統合リストを作成。

#### 3.3 公開可否判定

- reality が F (0-39) → **公開不可**
- empathy が F (0-39) → **公開不可**
- 総合スコア < 60 → **公開非推奨**
- 総合スコア >= 75 → **公開推奨**

### ステップ 4: レポート出力

#### 4.1 ターミナル出力（マークダウン）

```markdown
# 体験談DB批評レポート

## 記事情報
- **ファイル**: {file_path}
- **テーマ**: {theme_label}
- **総文字量**: {wordcount}字

## 総合評価

| 観点 | スコア | グレード |
|------|--------|---------|
| リアリティ | {score}/100 | {grade} |
| 共感度 | {score}/100 | {grade} |
| 埋め込みリンク | {score}/100 | {grade} |
| 文字量バランス | {score}/100 | {grade} |
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
    "theme": "{theme}",
    "theme_label": "{theme_label}"
  },
  "scores": {
    "reality": 0,
    "empathy": 0,
    "embed": 0,
    "balance": 0,
    "overall": 0
  },
  "verdict": "publish_recommended | publish_not_recommended | publish_blocked",
  "details": {
    "reality": { "... exp-critic-reality の完全な出力 ..." },
    "empathy": { "... exp-critic-empathy の完全な出力 ..." },
    "embed": { "... exp-critic-embed の完全な出力 ..." },
    "balance": { "... exp-critic-balance の完全な出力 ..." }
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
                 体験談DB批評 完了
================================================================================

## 結果サマリー
- リアリティ: {score}/100 ({grade})
- 共感度: {score}/100 ({grade})
- 埋め込みリンク: {score}/100 ({grade})
- 文字量バランス: {score}/100 ({grade})
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
| テーマが判定できない | ユーザーに確認 |
| エージェントがJSON以外を返した | パースを試行し、失敗なら該当観点をスキップして報告 |
| Neo4j 接続失敗 | embed 批評の neo4j_consistency を `checked: false` にして続行 |

## エージェント一覧

| エージェント | 役割 | リファレンス（共通） | リファレンス（テーマ固有） |
|------------|------|---------------------|------------------------|
| exp-critic-reality | リアリティ | `reality-standards.md` | `themes/{theme}.md` |
| exp-critic-empathy | 共感度 | `empathy-standards.md` | `themes/{theme}.md` |
| exp-critic-embed | 埋め込みリンク | `embed-standards.md` | `themes/{theme}.md` |
| exp-critic-balance | 文字量バランス | `balance-standards.md` | `themes/{theme}.md` |

## リファレンスファイル

| ファイル | パス |
|---------|------|
| スコアリング方式 | `.claude/resources/experience-db-criteria/scoring-methodology.md` |
| リアリティ基準 | `.claude/resources/experience-db-criteria/reality-standards.md` |
| 共感度基準 | `.claude/resources/experience-db-criteria/empathy-standards.md` |
| 埋め込みリンク基準 | `.claude/resources/experience-db-criteria/embed-standards.md` |
| 文字量バランス基準 | `.claude/resources/experience-db-criteria/balance-standards.md` |
| 婚活テーマ固有 | `.claude/resources/experience-db-criteria/themes/konkatsu.md` |
| 副業テーマ固有 | `.claude/resources/experience-db-criteria/themes/sidehustle.md` |
| 資産形成テーマ固有 | `.claude/resources/experience-db-criteria/themes/shisan-keisei.md` |
| テンプレート | `docs/plan/SideBusiness/体験談DB統一テンプレート_v2.md` |

## 完了条件

- [ ] テーマが正しく判定されている
- [ ] 4つの批評エージェントが並列実行されている
- [ ] 各エージェントが有効な JSON を返している
- [ ] スコアが統合され、総合判定が出ている
- [ ] critique.json が記事と同じディレクトリに保存されている
- [ ] ターミナルにマークダウンレポートが出力されている
- [ ] 改善優先度が提示されている
