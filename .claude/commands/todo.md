---
description: 日次TODOリストの作成・更新・振り返りを管理します。
argument-hint: --start | --update | --end
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

/todo スキルを実行してください。

## 引数: $ARGUMENTS

- `--start`: 朝のルーティン（前日繰り越し＋プロジェクト状況からタスクドリルダウン＋今日のTODO作成）
- `--update`: 日中の更新（タスク追加・完了・メモ）
- `--end`: 終業振り返り（完了/未完了サマリー）
- 引数なし: ユーザーにモード選択を確認

スキル定義: `.claude/skills/todo/SKILL.md` を参照して実行すること。
