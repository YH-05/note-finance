# RSS CLI ツール整備計画

## Context

ユーザーは RSS MCP サーバーに依存せず、ターミナルから直接 RSS 操作したい。
調査の結果、**`rss-cli` は既に実装済みで MCP 非依存**であることが判明。
ただし、実用性向上のためいくつかの改善が必要。

## 現状

- `rss-cli` は `src/rss/cli/main.py` で実装済み（Click ベース、7コマンド）
- サービスレイヤー直接使用（FeedManager/FeedFetcher/FeedReader）、MCP 未参照
- `pyproject.toml` L56 に `rss-cli = "rss.cli.main:cli"` 登録済み
- 全コマンドに `--json` オプション対応済み

```
rss-cli (Click CLI)
  ├── add       — フィード登録
  ├── list      — フィード一覧
  ├── update    — フィード更新
  ├── remove    — フィード削除
  ├── fetch     — フィード取得 (--all / --category)
  ├── items     — アイテム一覧 (--limit / --offset)
  ├── search    — アイテム検索 (-q / --fields)
  └── preset apply — プリセット適用
```

## 実装計画

### Phase 1: 依存関係修正（必須）

`click` が optional dependency (`cli` extra) にあるため、`uv sync` だけでは使えない可能性がある。

**ファイル**: `pyproject.toml`
- `click>=8.1.0` を `dependencies`（base）に移動
- `cli` optional group は削除 or 空にする

### Phase 2: QoL 改善

**ファイル**: `src/rss/cli/main.py`

| 改善 | 内容 |
|------|------|
| `--quiet` / `-q` | ログ出力を抑制（`--json` 時は自動適用） |
| `--verbose` / `-v` | DEBUG ログ有効化 |
| `--version` | バージョン表示 |
| `info` コマンド | 単一フィードの詳細表示 |
| `stats` コマンド | フィード数・カテゴリ別集計・最終取得日時 |

### Phase 3: テスト

**ファイル**: `tests/rss/unit/cli/test_main.py`
- 新コマンド（info, stats）のテスト追加
- `--quiet` / `--verbose` / `--version` のテスト追加

## 対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `pyproject.toml` | click を base deps に移動 |
| `src/rss/cli/main.py` | --quiet/--verbose/--version 追加、info/stats コマンド追加 |
| `tests/rss/unit/cli/test_main.py` | 新機能テスト追加 |

## 検証方法

```bash
# 1. 依存関係同期
uv sync

# 2. 基本動作確認
uv run rss-cli --help
uv run rss-cli --version
uv run rss-cli list
uv run rss-cli list --json

# 3. 新コマンド確認
uv run rss-cli info <feed_id>
uv run rss-cli stats --json

# 4. quiet モード確認（ログなし JSON 出力）
uv run rss-cli list --json --quiet

# 5. テスト実行
uv run pytest tests/rss/unit/cli/ -v

# 6. MCP なしで動作確認（MCP サーバー停止状態で全コマンド実行）
```
