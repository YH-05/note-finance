---
description: 新規プロジェクトを作成（GitHub Project + project.md）
skill-preload: project-management
---

# /new-project - 新規プロジェクト作成

> **スキル参照**: `.claude/skills/project-management/SKILL.md`

GitHub Project と `project.md` を新規作成します。
パッケージ開発（`@src/*`）と軽量プロジェクトの両モードに対応。

## 使用例

```bash
# パッケージ開発（project.md から）
/new-project @src/my_package/docs/project.md

# 軽量プロジェクト（名前指定）
/new-project "認証システムの実装"

# タイプ指定
/new-project --type workflow "週次レポート改善"
```

## 処理内容

`project-management` スキルに従い：

1. プロジェクトタイプを判定（package / general）
2. `docs/project/project-{N}/project.md` を生成
3. GitHub Project を作成
4. 初期 Issue を登録

## 注意事項

- プロジェクト番号は自動採番（既存プロジェクト数 + 1）
- `@src/` パスを指定した場合はパッケージモードで動作
- GitHub Project 作成には `GITHUB_TOKEN` が必要
