# NotebookLM MCP → CLI 移植計画

## Context

NotebookLM の操作は現在、独立リポジトリ `notebooklm-mcp` の MCP サーバー経由で行っている。
しかし MCP サーバーには以下の課題がある:

1. **信頼性問題**: チャット系操作で 30 秒タイムアウトが頻発し、batch_chat はほぼ確実に失敗
2. **管理分散**: 別リポジトリでの管理はメンテナンスコストが高い
3. **柔軟性不足**: MCP プロトコル経由のため、エラーリカバリやバッチ処理の制御が困難

**目標**: `notebooklm-mcp` の browser/services レイヤーを `note-finance` に移植し、Click ベースの CLI ツール `nlm` として提供する。MCP レイヤーは移植しない（CLI のみ）。

### 決定事項

- **CLI のみ** — MCP サーバーレイヤー (`mcp/`) は移植しない。`.mcp.json` の notebooklm エントリも削除
- **エントリポイント名**: `nlm` — 短く打ちやすい
- **既存テスト**: 移植する（browser, services, selectors 等のユニットテスト + CLI テスト新規作成）

---

## Phase 1: コアパッケージの移植

### コピー対象

```
notebooklm-mcp/src/notebooklm/ → note-finance/src/notebooklm/
```

| ファイル | 変更 | 説明 |
|---------|------|------|
| `__init__.py` | なし | パッケージ初期化 |
| `_logging.py` | なし | structlog ロギング |
| `_utils.py` | なし | ユーティリティ |
| `constants.py` | なし | URL, タイムアウト, ステルス設定 |
| `decorators.py` | なし | エラーハンドリングデコレータ |
| `errors.py` | なし | カスタム例外階層 |
| `selectors.py` | なし | CSS セレクタ管理 |
| `types.py` | なし | Pydantic v2 データモデル |
| `validation.py` | なし | セキュリティバリデーション |
| `browser/__init__.py` | なし | |
| `browser/manager.py` | なし | ブラウザライフサイクル管理 |
| `browser/helpers.py` | なし | ページ操作ヘルパー |
| `services/__init__.py` | なし | |
| `services/notebook.py` | なし | ノートブック CRUD |
| `services/source.py` | なし | ソース管理 |
| `services/chat.py` | なし | チャット操作 |
| `services/audio.py` | なし | オーディオ生成 |
| `services/studio.py` | なし | スタジオコンテンツ |
| `services/note.py` | なし | メモ CRUD |
| `services/batch.py` | なし | バッチ操作 |

### 移植しない

- `mcp/` ディレクトリ全体（server.py, tools/*.py）

---

## Phase 2: CLI レイヤーの新規作成

### ファイル構造

```
src/notebooklm/
├── __init__.py
├── _logging.py
├── _utils.py
├── constants.py
├── decorators.py
├── errors.py
├── selectors.py
├── types.py
├── validation.py
├── browser/
│   ├── __init__.py
│   ├── manager.py
│   └── helpers.py
├── services/
│   ├── __init__.py
│   ├── notebook.py
│   ├── source.py
│   ├── chat.py
│   ├── audio.py
│   ├── studio.py
│   ├── note.py
│   └── batch.py
└── cli/                    # ★ 新規作成
    ├── __init__.py
    ├── main.py             # Click グループ & エントリポイント
    ├── _async.py           # async → sync ブリッジ
    ├── _output.py          # Rich/JSON 出力ヘルパー
    ├── notebook_cmd.py     # notebook サブコマンド群
    ├── source_cmd.py       # source サブコマンド群
    ├── chat_cmd.py         # chat サブコマンド群（batch 含む）
    ├── note_cmd.py         # note サブコマンド群
    ├── audio_cmd.py        # audio サブコマンド群
    ├── studio_cmd.py       # studio サブコマンド群
    ├── session_cmd.py      # session 管理
    └── workflow_cmd.py     # 複合ワークフロー
```

### CLI コマンド設計

```bash
# エントリポイント
nlm [--session-file PATH] [--headless/--no-headless] [--json]

# ノートブック管理
nlm notebook list
nlm notebook create TITLE
nlm notebook summary NOTEBOOK_ID
nlm notebook delete NOTEBOOK_ID

# ソース管理
nlm source list NOTEBOOK_ID
nlm source add-text NOTEBOOK_ID --title TITLE --content CONTENT
nlm source add-url NOTEBOOK_ID --url URL
nlm source add-file NOTEBOOK_ID --file FILE_PATH
nlm source details NOTEBOOK_ID SOURCE_ID
nlm source delete NOTEBOOK_ID SOURCE_ID
nlm source rename NOTEBOOK_ID SOURCE_ID --name NEW_NAME
nlm source research NOTEBOOK_ID --mode fast|deep

# チャット（最重要機能）
nlm chat ask NOTEBOOK_ID "質問テキスト"
nlm chat batch NOTEBOOK_ID --file questions.txt [--batch-size 3] [--output-dir DIR]
nlm chat history NOTEBOOK_ID
nlm chat clear NOTEBOOK_ID
nlm chat configure NOTEBOOK_ID --prompt "システムプロンプト"
nlm chat save-to-note NOTEBOOK_ID "質問テキスト"

# メモ管理
nlm note list NOTEBOOK_ID
nlm note create NOTEBOOK_ID --title TITLE --content CONTENT
nlm note get NOTEBOOK_ID NOTE_INDEX
nlm note delete NOTEBOOK_ID NOTE_INDEX

# オーディオ・スタジオ
nlm audio generate NOTEBOOK_ID
nlm studio generate NOTEBOOK_ID --type report|slides|infographic|data_table

# セッション管理
nlm session status
nlm session clear

# ワークフロー（複合操作）
nlm workflow research NOTEBOOK_ID --questions-file FILE [--output-dir DIR]
```

### Async → Sync ブリッジ（`cli/_async.py`）

Services レイヤーは全て async なので、Click の sync コマンドから呼ぶためのブリッジが必要:

```python
"""Async-to-sync bridge for Click commands."""
import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

def run_async(coro_func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
    """Decorator: async function を Click command から同期的に実行する。"""
    @wraps(coro_func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return asyncio.run(coro_func(*args, **kwargs))
    return wrapper
```

### 共有コンテキスト（`cli/main.py`）

```python
from notebooklm.browser.manager import NotebookLMBrowserManager

@click.group()
@click.option("--session-file", type=click.Path(), default=None,
              help="Session file path (default: .notebooklm-session.json)")
@click.option("--headless/--no-headless", default=True,
              help="Run browser in headless mode")
@click.option("--json", "json_output", is_flag=True,
              help="Output as JSON")
@click.pass_context
def cli(ctx, session_file, headless, json_output):
    """nlm — NotebookLM ブラウザ自動化 CLI"""
    ctx.ensure_object(dict)
    ctx.obj["session_file"] = session_file
    ctx.obj["headless"] = headless
    ctx.obj["json_output"] = json_output

# サブグループ登録
cli.add_command(notebook)
cli.add_command(source)
cli.add_command(chat)
cli.add_command(note)
cli.add_command(audio)
cli.add_command(studio)
cli.add_command(session)
cli.add_command(workflow)
```

### BrowserManager のライフサイクル管理

CLI コマンド実行時に BrowserManager を作成し、コマンド終了時に閉じる:

```python
# 各コマンドの共通パターン
@notebook.command()
@click.pass_context
@run_async
async def list_cmd(ctx):
    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        service = NotebookService(manager)
        notebooks = await service.list_notebooks()
        # 出力処理...
    finally:
        await manager.close()
```

### chat batch の実装（最重要機能）

SKILL.md の実証済みパターン（3問バッチ + リロード）を CLI に組み込む:

```python
@chat.command()
@click.argument("notebook_id")
@click.option("--file", "-f", "questions_file", required=True,
              type=click.Path(exists=True))
@click.option("--batch-size", default=3,
              help="Questions per batch before page reload (default: 3)")
@click.option("--output-dir", "-o", default=None, type=click.Path())
@click.option("--json", "json_output", is_flag=True)
@click.pass_context
@run_async
async def batch(ctx, notebook_id, questions_file, batch_size, output_dir, json_output):
    """ファイルから質問を読み込み、バッチ処理で回答を収集する。"""
    # 1. questions.txt を読み込み（1行1質問）
    # 2. batch_size 問ごとに処理
    # 3. バッチ間でページリロード（DOM detachment 防止）
    # 4. 結果を Markdown / JSON で保存
    # 5. Rich progress bar で進捗表示
```

---

## Phase 3: pyproject.toml & ビルド設定

### 変更ファイル: `pyproject.toml`

```diff
 [project.scripts]
+nlm = "notebooklm.cli.main:cli"
 rss-mcp = "rss.mcp.server:main"
 rss-cli = "rss.cli.main:cli"
 ...

 [tool.hatch.build.targets.wheel]
-packages = ["src/rss", "src/news", "src/automation", "src/news_scraper", "src/report_scraper", "src/pdf_pipeline", "src/data_paths"]
+packages = ["src/rss", "src/news", "src/automation", "src/news_scraper", "src/report_scraper", "src/pdf_pipeline", "src/data_paths", "src/notebooklm"]
```

### .mcp.json の変更

- `notebooklm` エントリを削除（CLI に切り替えるため）

### 外部パッケージの除去

```bash
# .venv にインストールされている外部 notebooklm パッケージを除去
# ローカルソース src/notebooklm/ に置き換え
```

---

## Phase 4: テストの移植

### テスト構造

```
tests/notebooklm/
├── conftest.py             # 共通フィクスチャ（移植）
├── unit/
│   ├── browser/
│   │   ├── test_manager.py     # 移植
│   │   └── test_helpers.py     # 移植
│   ├── cli/                    # ★ 新規作成
│   │   ├── test_main.py
│   │   ├── test_notebook_cmd.py
│   │   ├── test_chat_cmd.py
│   │   └── test_output.py
│   ├── test_decorators.py      # 移植
│   ├── test_errors.py          # 移植
│   ├── test_validation.py      # 移植
│   ├── test_selectors.py       # 移植
│   └── test_batch_service.py   # 移植
└── integration/
    └── test_cli_e2e.py         # ★ 新規（CI skip マーカー付き）
```

### CLI テストのパターン

```python
from click.testing import CliRunner
from notebooklm.cli.main import cli

def test_notebook_list_json(mock_browser_manager):
    runner = CliRunner()
    result = runner.invoke(cli, ["notebook", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
```

---

## Phase 5: スキル・ドキュメント更新

| ファイル | 変更内容 |
|---------|---------|
| `.claude/skills/notebooklm-automation/SKILL.md` | MCP → CLI コマンドの使用方法に更新 |
| `.claude/skills/equity-stock-research/SKILL.md` | `nlm` CLI への参照を追加 |
| `.mcp.json` | `notebooklm` エントリを削除 |

---

## 実装順序

| Step | 内容 | 対象ファイル |
|------|------|-------------|
| 1 | `src/notebooklm/` にコアファイルをコピー（browser/, services/, 共通モジュール） | 約 20 ファイル |
| 2 | `src/notebooklm/cli/` を作成（main.py, _async.py, _output.py） | 3 ファイル |
| 3 | notebook_cmd.py を実装 | 1 ファイル |
| 4 | source_cmd.py を実装 | 1 ファイル |
| 5 | chat_cmd.py を実装（batch 含む、最重要） | 1 ファイル |
| 6 | note_cmd.py, audio_cmd.py, studio_cmd.py を実装 | 3 ファイル |
| 7 | session_cmd.py, workflow_cmd.py を実装 | 2 ファイル |
| 8 | pyproject.toml 更新（エントリポイント、ビルド設定） | 1 ファイル |
| 9 | テスト移植（既存）+ CLI テスト新規作成 | 約 12 ファイル |
| 10 | `.mcp.json` から notebooklm 削除、外部パッケージ除去 | 1 ファイル |
| 11 | スキルドキュメント更新 | 2 ファイル |
| 12 | `make check-all` で品質チェック | — |

---

## 検証方法

```bash
# 1. CLI ヘルプ
uv run nlm --help
uv run nlm notebook --help
uv run nlm chat --help

# 2. セッション確認
uv run nlm session status

# 3. ノートブック一覧
uv run nlm notebook list --json

# 4. チャット（単一質問）
uv run nlm chat ask <notebook_id> "テスト質問"

# 5. チャット（バッチ）
uv run nlm chat batch <notebook_id> -f questions.txt --batch-size 3 -o output/

# 6. 品質チェック
make check-all
uv run pytest tests/notebooklm/ -v
```

---

## 重要ファイル一覧

### コピー元（notebooklm-mcp）
- `/Users/yukihata/desktop/notebooklm-mcp/src/notebooklm/` — browser/, services/, 共通モジュール
- `/Users/yukihata/desktop/notebooklm-mcp/tests/notebooklm/` — テスト一式

### 変更・新規作成（note-finance）
- `src/notebooklm/cli/` — CLI レイヤー（新規、10 ファイル）
- `tests/notebooklm/unit/cli/` — CLI テスト（新規）
- `pyproject.toml` — エントリポイント `nlm` 追加、ビルド設定
- `.mcp.json` — notebooklm エントリ削除
- `.claude/skills/notebooklm-automation/SKILL.md` — CLI 参照に更新
