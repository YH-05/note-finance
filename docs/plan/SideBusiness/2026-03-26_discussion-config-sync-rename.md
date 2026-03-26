# 議論メモ: config-sync リネーム & NASパス整理

**日付**: 2026-03-26
**参加**: ユーザー + Claude
**前回**: [NAS設定ファイル同期仕組み実装](2026-03-26_discussion-nas-sync-config.md) / [quantsへの移植](2026-03-26_discussion-quants-nas-sync-port.md)

## 背景・コンテキスト

前回セッションで作成した `sync-nas` スキル/コマンドについて以下の問題が指摘された:

1. **プロジェクト名の誤り**: NASパスが `Projects/finance/note-finance-sync/` となっており、このプロジェクトは `note-finance` であって `finance` ではない
2. **命名の整理**: スキル/コマンド名が `sync-nas` だとNAS固有の実装詳細が露出しており、`config-sync` のほうが意味的に適切
3. **パス構造の簡略化**: `quants-sync/` のようなサブディレクトリ階層が不要

## 決定事項

1. **スキル・コマンド名を `sync-nas` → `config-sync` に変更**（両プロジェクト）
   - 理由: NASという実装詳細ではなく「設定ファイル同期」という機能を名前で表現
   - 旧ファイルは `trash/` へ移動

2. **NASパスをフラット化**
   - note-finance: `Projects/finance/note-finance-sync/` → `Projects/note-finance/`
   - quants: `Projects/quants/quants-sync/` → `Projects/quants/`
   - 理由: プロジェクト名のフォルダを直接使い、サブディレクトリの冗長性を排除

## 実装内容

### note-finance

| ファイル | 変更内容 |
|---------|---------|
| `scripts/sync_nas.sh` | `NAS_SYNC_DIR` → `Projects/note-finance`、`LOG_PREFIX` → `[config-sync]` |
| `.claude/commands/config-sync.md` | 新規作成（旧 `sync-nas.md` → trash） |
| `.claude/skills/config-sync/SKILL.md` | 新規作成（旧 `sync-nas/` → trash） |
| NAS | `Projects/note-finance/` ディレクトリを新規作成 |

### quants

| ファイル | 変更内容 |
|---------|---------|
| `scripts/sync_nas.sh` | `NAS_SYNC_DIR` → `Projects/quants`、`LOG_PREFIX` → `[config-sync]` |
| `.claude/commands/config-sync.md` | 新規作成（旧 `sync-nas.md` → trash） |
| `.claude/skills/config-sync/SKILL.md` | 新規作成（旧 `sync-nas/` → trash） |

## NAS構造（変更後）

```
/Volumes/personal_folder/Projects/
├── note-finance/     ← note-finance用（新規作成）
└── quants/           ← quants用（既存、サブディレクトリを廃止）
```

## アクションアイテム

- [ ] 他PCでの `config-sync` pull 動作検証（優先度: 低）
- [ ] `quants/quants-sync/` の旧データを `quants/` に移行するか確認（優先度: 低）

## 次回の議論トピック

- 特になし（実装完了）
