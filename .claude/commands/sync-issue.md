---
description: GitHub Issue のコメントから進捗・タスク・仕様変更を同期
skill-preload: issue-sync
---

# /sync-issue - Issue 同期

> **スキル参照**: `.claude/skills/issue-sync/SKILL.md`

Issue コメントから進捗情報・新規タスク・仕様変更を抽出し、`project.md` と GitHub Project に反映します。

## 使用例

```bash
/sync-issue #123
/sync-issue 123
```

## 処理内容

`issue-sync` スキルに従い：

1. 指定 Issue のコメントを取得
2. 進捗情報・新規タスク・仕様変更を AI で抽出
3. 確信度ベースで自動適用 / 手動確認を分岐
4. `project.md` と GitHub Project を更新

## 注意事項

- Issue 番号は `#123` または `123` の形式で指定
- 大きな仕様変更は確認を求めます
- `project.md` が存在しない場合はスキップします
