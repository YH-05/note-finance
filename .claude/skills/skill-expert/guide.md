# Skill Expert ガイド

## 設計原則

### 1. 単一責任

スキルは一つの明確な目的を持つ。複数の目的がある場合は分割を検討。

### 2. プロアクティブ使用の定義

スキルの `description` には、いつ自動的に使用すべきかを明記する。
これにより Claude Code がコンテキストから適切なスキルを選択できる。

```markdown
description: |
  Pythonコード実装時に参照するコーディング規約。
  型ヒント、命名規則、Docstringのパターンを提供。
  コード実装時、レビュー時、リファクタリング時にプロアクティブに使用。
```

### 3. ナレッジベース vs ワークフロー

| 判断基準 | ナレッジベース型 | ワークフロー型 |
|---------|----------------|--------------|
| ファイル変更 | なし | あり |
| 外部API呼び出し | なし | あり |
| 複数ステップ | なし | あり |
| 主な用途 | 参照・ガイドライン | 実行・自動化 |

### 4. 依存関係の明示

他のスキルに依存する場合はフロントマターで宣言：

```yaml
skills: [coding-standards, error-handling]
```

## ナレッジベース型スキルの構成

```
.claude/skills/my-skill/
├── SKILL.md          # エントリーポイント（概要・使用方法）
├── guide.md          # 詳細ガイドライン
└── examples/         # 具体例（任意）
    ├── basic.md
    └── advanced.md
```

## ワークフロー型スキルの構成

```
.claude/skills/my-skill/
├── SKILL.md           # エントリーポイント（ワークフロー定義）
├── guide.md           # 詳細手順
└── templates/         # テンプレートファイル（任意）
    └── output-template.md
```

## 検証ルール

### フロントマター検証

```yaml
# 必須フィールド
name: string          # kebab-case, 一意
description: string   # 1-3行以内、トリガー条件を含む
allowed-tools: list   # 使用するツールのリスト

# オプションフィールド
skills: list          # 依存スキル
```

### 内容検証

- `## 目的` セクションが存在する
- `## いつ使用するか` セクションが存在する（プロアクティブ使用の定義）
- `## 完了条件` セクションが存在する（ワークフロー型のみ）
- コードブロックに適切なシンタックスハイライトがある

### 品質チェックリスト

- [ ] description が具体的でトリガー条件を含む
- [ ] allowed-tools が最小権限の原則に従っている
- [ ] サブファイル（guide.md等）への参照が正確
- [ ] 日本語と技術用語が適切に混在している
- [ ] 使用例が実際のユースケースを反映している

## アンチパターン

### 避けるべき記述

```yaml
# 悪い例: descriptionが曖昧
description: "便利なスキル"

# 良い例: トリガー条件が明確
description: |
  コードレビュー時に使用するチェックリスト。
  PR作成前、コードレビュー実施時にプロアクティブに使用。
```

```yaml
# 悪い例: ツールを過剰に許可
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, AskUserQuestion

# 良い例: 必要最小限
allowed-tools: Read, Bash
```

## 関連リソース

- スキル実装例: `.claude/skills/coding-standards/SKILL.md`
- エージェント設計: `.claude/skills/agent-expert/SKILL.md`
- ワークフロー設計: `.claude/skills/workflow-expert/SKILL.md`
