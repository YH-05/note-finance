# Agent Expert ガイド

## 設計原則

### 1. 単一責任

各エージェントは一つの明確な責任を持つ。
複数の責任を持つ場合は、オーケストレーターとスペシャリストに分割する。

### 2. プロアクティブ使用の定義

エージェントの `description` には、いつ自動起動すべきかを明記する。

```markdown
description: PRの変更コードのセキュリティ脆弱性（OWASP A01-A05）を検証するサブエージェント
```

### 3. エージェント間協調パターン

#### Agent Teams（並列実行）

```python
Task(subagent_type="agent-a", ...)
Task(subagent_type="agent-b", ...)
# 両エージェントが並列実行される
```

#### シーケンシャル実行

```python
result_a = Task(subagent_type="agent-a", ...)
# result_a の結果を使って
Task(subagent_type="agent-b", prompt=f"...{result_a}...")
```

#### Human Feedback ゲート

```python
result = Task(subagent_type="researcher", ...)
user_input = AskUserQuestion("確認してください")
Task(subagent_type="implementer", prompt=f"...{user_input}...")
```

## エージェントカテゴリ

### content（コンテンツ生成）

記事執筆、批評、修正などコンテンツ関連タスク。
slugプレフィックス: `finance-`, `article-`, `experience-`, `csa-`, `exp-`

### pr-review（PRレビュー）

コード品質、セキュリティ、テストカバレッジの検証。
slugプレフィックス: `pr-`

### weekly-report（週次レポート）

マーケットレポート生成ワークフロー。
slugプレフィックス: `wr-`, `weekly-`

### testing（テスト）

TDD サイクル、テスト設計・実装。
slugプレフィックス: `test-`

### specialized-domains（専門ドメイン）

特定技術領域のエキスパートエージェント。

### project-management（プロジェクト管理）

Issue/Project管理、タスク分解、計画策定。

## データフロー設計

### 一時ファイル経由

```python
# エージェントA → ファイル → エージェントB
with open(".tmp/session-data.json", "w") as f:
    json.dump(data, f)

Task(
    subagent_type="agent-b",
    prompt=f"データを読み込んで処理: .tmp/session-data.json"
)
```

### プロンプト内JSON渡し

```python
Task(
    subagent_type="agent-b",
    prompt=f"""以下のデータを処理してください。

```json
{json.dumps(data, ensure_ascii=False, indent=2)}
```
"""
)
```

## 完了条件の定義

エージェント定義の末尾に明確な完了条件を記載する：

```markdown
## 完了条件

- [ ] 全チェック項目を検証した
- [ ] YAML形式で結果を出力した
- [ ] スコアを算出した
```

## 関連リソース

- スキル設計: `.claude/skills/skill-expert/SKILL.md`
- ワークフロー設計: `.claude/skills/workflow-expert/SKILL.md`
- データ受け渡しルール: `.claude/rules/subagent-data-passing.md`
