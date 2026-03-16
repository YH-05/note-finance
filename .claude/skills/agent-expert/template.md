# エージェントテンプレート

## スペシャリスト型エージェント

```markdown
---
name: my-agent
description: [エージェントの役割を1文で説明。いつ自動起動するかも含める]
model: sonnet
color: purple
---

# [エージェント名]

[エージェントの概要説明]

## 目的

このエージェントは以下を実行します：

- [タスク1]
- [タスク2]
- [タスク3]

## いつ使用するか

### プロアクティブ使用（自動的に検討）

以下の状況では、ユーザーが明示的に要求しなくても使用を検討：

1. **[ユースケース1]**
   - 「[キーワード]」

### 明示的な使用

- Task toolでsubagent_type="[agent-slug]"を指定された場合

## 処理フロー

1. [ステップ1]
2. [ステップ2]
3. [ステップ3]

## 出力フォーマット

```yaml
[output_key]:
  score: 0
  items:
    - description: "[説明]"
      recommendation: "[推奨事項]"
```

## 完了条件

- [ ] [条件1]
- [ ] [条件2]
```

## オーケストレーター型エージェント

```markdown
---
name: my-lead-agent
description: [ワークフロー全体を制御するリーダーエージェント]
model: opus
color: blue
---

# [エージェント名]

[ワークフローの概要説明]

## ワークフロー

```
Phase 1: [フェーズ名] (subagent-a) ─── [出力]
    |
Phase 2: [フェーズ名] (subagent-b) ─── [出力]
    |
Phase 3: [フェーズ名] (subagent-c) ─── 完了レポート
```

## Agent Team 構成

| メンバー | subagent_type | 役割 |
|---------|---------------|------|
| **subagent-a** | `subagent-a` | [役割] |
| **subagent-b** | `subagent-b` | [役割] |

## 処理コード例

```python
# Phase 1
Task(
    subagent_type="subagent-a",
    description="[説明]",
    prompt="""..."""
)

# Phase 2
Task(
    subagent_type="subagent-b",
    description="[説明]",
    prompt="""..."""
)
```

## 完了条件

- [ ] 全フェーズが正常完了した
- [ ] 完了レポートを表示した
```
