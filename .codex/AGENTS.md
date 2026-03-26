# AGENTS.md

> **Note**: プロジェクト共通の指示は `../AGENTS.md` を参照してください。  
> このファイルは Codex 固有の設定のみを記載しています。

## Codex Integration (`.codex/`)

| ディレクトリ / ファイル | 内容 |
|------------------------|------|
| `AGENTS.md` | Codex 固有の運用ルール |

現状、このリポジトリでは Codex 向けの専用ディレクトリは `./.codex/` 配下のみを使用する。共通ワークフロー・スキル・プロジェクト背景はルートの `AGENTS.md` と既存ディレクトリ（`.agents/`, `.claude/`, `.gemini/` など）を参照すること。

## 対応方針

- まずルートの `AGENTS.md` を優先して参照する
- プラットフォーム固有の差分のみこのファイルに追記する
- 既存のプロジェクト構造・テンプレート・スクリプトを優先して再利用する

## 制約事項

- `template/` は変更・削除禁止
- ファイル・ディレクトリを削除する際は `rm` ではなく `trash/` に移動すること
- `trash/` はユーザーが定期的に確認・削除する

## Obsidian 操作ルール

Obsidian を操作する際は `obsidian` コマンド（`/Applications/Obsidian.app/Contents/MacOS/obsidian`）のみを使用すること。ファイルの読み書きや検索等も `obsidian` CLI 経由で行う。
