---
name: skill-expert
description: Claude Code スキルの設計・実装・検証のナレッジベース。スキル作成時のガイドライン、テンプレート、検証ルールを提供。skill-creator エージェントが参照する。
allowed-tools: Read
---

# Skill Expert

Claude Code スキルの設計・実装・検証に関するナレッジベーススキルです。

## 目的

このスキルは以下を提供します：

- **設計原則**: 高品質なスキルを作成するための設計ガイドライン
- **テンプレート**: 標準的なスキル構造のテンプレート
- **検証ルール**: フロントマターと内容の品質検証基準
- **ベストプラクティス**: プロアクティブ使用、ナレッジベース、ワークフロー型の使い分け

## リソース

詳細ガイドと参照資料:

| ファイル | 内容 |
|---------|------|
| `guide.md` | 設計原則・ナレッジベース構成・検証ルール |
| `template.md` | スキル SKILL.md テンプレート構造 |
| `improvement-template.md` | スキル改善提案テンプレート（Evidence → Issues → Changes → Rollback → Verification） |

## スキルタイプ

### 1. ナレッジベース型

特定ドメインのベストプラクティス・ガイドラインを提供。
`allowed-tools: Read` のみ使用。

```markdown
---
name: my-knowledge-skill
description: ...
allowed-tools: Read
---
```

### 2. ワークフロー型

複数ステップの処理を実行するアクション型スキル。
必要なツールを明示的に許可。

```markdown
---
name: my-workflow-skill
description: ...
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task
---
```

## フロントマター必須フィールド

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `name` | ✅ | スキルのスラッグ（kebab-case） |
| `description` | ✅ | 一行の説明（トリガー判定に使用） |
| `allowed-tools` | ✅ | 使用許可ツールのリスト |

## 完了条件

- [ ] `guide.md` を参照して設計原則を確認
- [ ] `template.md` のテンプレートに従って実装
- [ ] フロントマター必須フィールドが全て揃っている
- [ ] スキルタイプ（ナレッジベース/ワークフロー）が明確
