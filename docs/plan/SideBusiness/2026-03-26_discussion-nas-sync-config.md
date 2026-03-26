# 議論メモ: NAS設定ファイル同期仕組み実装 & Claude Code設定ファイル調査

**日付**: 2026-03-26
**参加**: ユーザー + Claude

## 背景・コンテキスト

複数PC間でnote-financeプロジェクトの設定ファイルを同期したいというニーズ。
NAS（`/Volumes/personal_folder`、SMBマウント）を中継点として使用する方針。

## 議論のサマリー

### 1. git未追跡ファイルの棚卸し

`git ls-files --others --directory` で調査した結果、
`.playwright-mcp/`、`__pycache__/`、`.DS_Store` 等は既に `.gitignore` で管理済みと確認。
`.playwright-cli/` はスクリプトではなくPlaywrightセッションログであり、`scripts/` への移動は不要。

### 2. settings.jsonとsettings.local.jsonの違い

| 項目 | settings.json | settings.local.json |
|------|--------------|---------------------|
| git管理 | 追跡される | 追跡されない |
| 用途 | プロジェクト共有設定 | ローカル個人設定 |
| 優先順位 | 低（Projectスコープ） | 高（Localスコープ） |

`permissions.allow` 等の配列値はマージ（連結）される。スカラー値は上位スコープが勝つ。
`deny` に入っているものは `settings.local.json` の `allow` で解除不可。

### 3. NAS同期仕組みの実装

以下を作成:

| ファイル | 内容 |
|---------|------|
| `scripts/sync_nas.sh` | rsyncベースのpush/pull両対応スクリプト |
| `.claude/settings.local.json` | SessionEnd hookでauto push追加 |
| `.claude/skills/sync-nas/SKILL.md` | /sync-nasスキル定義 |
| `.claude/commands/sync-nas.md` | /sync-nasコマンド |

**NAS保存先**: `/Volumes/personal_folder/Projects/finance/note-finance-sync/`

**同期対象**:
- `.env`
- `.mcp.json`
- `.claude/settings.json`
- `data/config/`

## 決定事項

1. NAS同期はrsyncベースのシェルスクリプトで実装。SessionEnd hookで自動push、`/sync-nas`コマンドで手動pull。
2. `.claude/settings.local.json` はNAS同期対象外（マシン固有設定のため手動セットアップが必要）。
3. git未追跡ファイルは全て.gitignoreで既管理済み。追加対応不要。

## アクションアイテム

- [ ] 他PCでのNAS同期セットアップ（NASマウント → pull → settings.local.jsonにhook追記）（優先度: 中）
- [ ] 他PCでのpull動作検証（優先度: 低）

## 次回の議論トピック

- 特になし（実装完了）

## 参考情報

- NASマウント: `//Yuki@100.70.5.35/personal_folder` (SMBfs)
- ログ: `/tmp/sync-nas.log`
- hookはバックグラウンド実行（`&`）なのでセッション終了をブロックしない
