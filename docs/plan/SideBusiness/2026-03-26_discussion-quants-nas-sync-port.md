# 議論メモ: quantsリポジトリへのNAS同期仕組み移植

**日付**: 2026-03-26
**参加**: ユーザー + Claude
**前回**: [NAS設定ファイル同期仕組み実装](2026-03-26_discussion-nas-sync-config.md)

## 背景・コンテキスト

note-financeで実装したNAS同期仕組みをquantsリポジトリでも使用したいという要求。
各リポジトリの設定ファイルを独立して管理しつつ、同じ仕組みで複数PCに同期する。

## 議論のサマリー

note-financeの`sync_nas.sh`をquantsに移植。NASパスとログファイルのみ変更し、
スクリプト本体の構造・ロジックは共通化。

## 実装内容

| ファイル | 変更内容 |
|---------|---------|
| `scripts/sync_nas.sh` | NAS_SYNC_DIRをquants専用パスに変更して新規作成 |
| `.claude/settings.local.json` | SessionEnd hookを追記 |
| `.claude/skills/sync-nas/SKILL.md` | スキル定義を新規作成 |
| `.claude/commands/sync-nas.md` | コマンド定義を新規作成 |

## 決定事項

1. quantsのNAS保存先は`Projects/quants/quants-sync/`に分離（note-financeとは独立）
2. ログファイルは`/tmp/sync-nas-quants.log`に分離（note-financeの`sync-nas.log`と干渉しない）

## アクションアイテム

- なし（実装完了）

## 同期対象（quants）

- `.env`
- `.mcp.json`
- `.claude/settings.json`
- `data/config/`

## NAS構造

```
/Volumes/personal_folder/Projects/
├── finance/
│   └── note-finance-sync/   ← note-finance用
└── quants/
    └── quants-sync/         ← quants用（今回作成）
```
