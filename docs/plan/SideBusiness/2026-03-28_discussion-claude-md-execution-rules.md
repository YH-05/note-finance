# 議論メモ: CLAUDE.md 実行環境・Pythonファイル配置ルール整備

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

CLAUDE.mdに `uv run` 必須ルールやPythonファイルの配置ルールが明文化されていなかった。
また、config-sync（NAS同期）が両プロジェクト（note-finance, quants）で整備済みか不明だった。

## 議論のサマリー

### config-sync 整備状況の確認

両プロジェクトの以下4項目を調査:
- `scripts/sync_nas.sh` — 両方あり
- SessionEnd hook (NAS push) — 両方 `settings.local.json` にあり
- `/config-sync` コマンド — 両方あり
- `config-sync` スキル — 両方あり

初回調査でGlobのパス大文字小文字不一致（`/users/` vs `/Users/`）により
quantsのファイルを見つけられず未登録と誤認したが、再調査で全て完備を確認。

### CLAUDE.md へのルール追加

3つのルールを「実行環境」セクションとしてCLAUDE.mdに追加した。

## 決定事項

1. **uv run 必須**: Pythonスクリプトは必ず `uv run` 経由で実行（素の python/python3 禁止）
2. **Python配置先限定**: `src/`, `scripts/`, `tests/`, `.claude/skills/*/`, `.claude/hooks/` のみ許可
3. **.tmp/ クリーンアップ義務**: アドホックスクリプトは用途完了後に速やかに削除
4. **config-sync 完備確認**: note-finance, quants 両方で全コンポーネント揃っている

## アクションアイテム

（なし — 全て本セッション内で完了済み）

## 参考情報

### config-sync コンポーネント一覧

| 項目 | note-finance | quants |
|------|-------------|--------|
| `scripts/sync_nas.sh` | NAS先: `Projects/note-finance/` | NAS先: `Projects/quants/` |
| SessionEnd hook | `settings.local.json` | `settings.local.json` |
| `/config-sync` コマンド | `.claude/commands/config-sync.md` | `.claude/commands/config-sync.md` |
| `config-sync` スキル | `.claude/skills/config-sync/SKILL.md` | `.claude/skills/config-sync/SKILL.md` |
