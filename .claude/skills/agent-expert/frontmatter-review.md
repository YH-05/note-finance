# フロントマター検証ルール

## 必須フィールドチェック

### チェック項目

| フィールド | 必須 | 検証ルール |
|-----------|------|---------|
| `name` | ✅ | kebab-case（小文字、数字、ハイフンのみ） |
| `description` | ✅ | 1-3行、トリガー条件を含む |
| `model` | ✅ | `inherit`, `sonnet`, `opus`, `haiku` のいずれか |
| `color` | 推奨 | 有効な色名（下記参照） |
| `skills` | 任意 | 配列形式、存在するスキルのみ |
| `tools` | 任意 | 配列形式、有効なツール名のみ |

## 有効な color 値

| 色 | 用途 |
|----|------|
| `gray` | デフォルト・汎用 |
| `blue` | オーケストレーター・リーダー |
| `green` | チームメイト・サポート |
| `purple` | スペシャリスト・専門ドメイン |
| `red` | セキュリティ・クリティカル |
| `yellow` | 警告・注意が必要 |

## name フィールドの規則

```yaml
# 良い例
name: pr-security-code
name: wr-report-publisher
name: test-unit-writer

# 悪い例
name: PRSecurityCode    # PascalCase禁止
name: pr_security_code  # snake_case禁止
name: pr security code  # スペース禁止
```

## description フィールドの規則

```yaml
# 良い例（具体的なトリガー条件を含む）
description: PRのコードセキュリティ（OWASP A01-A05）を検証するサブエージェント

# 悪い例（曖昧）
description: セキュリティをチェックするエージェント
```

## skills フィールドの規則

```yaml
# 良い例
skills: [skill-expert]
skills:
  - coding-standards
  - error-handling

# 悪い例（存在しないスキル）
skills: [non-existent-skill]
```

## 品質チェックリスト

### フロントマター

- [ ] `name` が kebab-case である
- [ ] `description` がトリガー条件を含む
- [ ] `model` が有効な値である
- [ ] `color` が用途に合っている
- [ ] `skills` に列挙したスキルが実際に存在する

### コンテンツ

- [ ] `## 目的` セクションが存在する
- [ ] `## いつ使用するか` セクションが存在する
- [ ] `## 処理フロー` または `## ワークフロー` セクションが存在する
- [ ] `## 完了条件` セクションが存在する
- [ ] 出力フォーマットが定義されている（該当する場合）

### 機能的チェック

- [ ] `subagent_type` の名前が `name` フィールドと一致する
- [ ] 参照するスキルファイルのパスが正確
- [ ] 依存エージェントの `subagent_type` が実在する
