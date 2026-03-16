---
description: プロジェクトの整合性を検証・修正（GitHub Project と project.md を同期）
skill-preload: project-management
---

# /project-refine - プロジェクト整合性検証

> **スキル参照**: `.claude/skills/project-management/SKILL.md`

GitHub Project、Issues、`project.md` の間の不整合を検出し修正します。

## 使用例

```bash
# 現在のプロジェクトを検証
/project-refine

# プロジェクトファイルを指定
/project-refine @docs/project/project-21/project.md
```

## チェック内容

- [ ] `project.md` のタスクステータスと GitHub Issue の完了状態の一致
- [ ] GitHub Project のカラム（ステータスフィールド）との整合性
- [ ] 孤立した Issue（project.md に未記載）の検出
- [ ] 完了 Issue が `project.md` で未完了になっていないか

## 処理内容

`project-management` スキルに従い：

1. `project.md` を読み込み
2. GitHub Issue のステータスを取得
3. 不整合を検出・報告
4. 修正内容を確認後に適用
