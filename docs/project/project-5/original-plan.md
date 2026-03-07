# note.com 下書き投稿スクリプト実装計画

## Context

記事ワークフロー（`/finance-edit`）で生成される `revised_draft.md` を note.com に下書きとして投稿するプロセスは現在手動。これを Playwright ブラウザ自動化で自動化し、CLI から1コマンドで下書き作成まで完了できるようにする。

## 方針

- **アプローチ**: Playwright ブラウザ自動化（既存の `playwright>=1.49.0` 依存を活用）
- **配置**: `scripts/note_publisher/` パッケージ（`pyproject.toml` の `pythonpath` に `scripts` 含まれておりテスト可能）
- **認証**: 初回は headed ブラウザで手動ログイン → `.note-session.json` にセッション保存 → 以降は自動復元

## ファイル構成

```
scripts/
  publish_to_note.py              # CLI エントリポイント
  note_publisher/
    __init__.py
    types.py                      # Pydantic モデル（ContentBlock, ArticleDraft, PublishResult 等）
    config.py                     # 環境変数・設定読み込み
    markdown_parser.py            # revised_draft.md → ContentBlock[] パーサー
    browser_client.py             # Playwright ブラウザ操作（ログイン・エディタ入力・保存）
    draft_publisher.py            # オーケストレーター（parse → browser → publish）

tests/
  scripts/
    note_publisher/
      __init__.py
      test_markdown_parser.py     # パーサーのユニットテスト（純粋ロジック）
      test_types.py               # モデルバリデーション
      test_config.py              # 設定読み込み
      test_browser_client.py      # Playwright モック
      test_draft_publisher.py     # 統合テスト（モック）
```

## モジュール設計

### 1. `types.py` — 型定義

```python
type BlockType = Literal["heading", "paragraph", "list_item", "blockquote", "image", "separator"]

class ContentBlock(BaseModel):
    block_type: BlockType
    content: str
    level: int | None = None          # 見出しレベル (1-3)
    image_path: Path | None = None    # 画像ブロック用

class ArticleDraft(BaseModel):
    title: str
    body_blocks: list[ContentBlock]
    image_paths: list[Path]
    frontmatter: dict[str, Any]

class PublishResult(BaseModel):
    success: bool
    draft_url: str | None = None
    error_message: str | None = None

class NotePublisherConfig(BaseModel):
    headless: bool = False            # 初回は headed 必須
    storage_state_path: Path = Path(".note-session.json")
    timeout_ms: int = 30_000
    typing_delay_ms: int = 50        # 入力速度（bot 検知回避）
```

### 2. `markdown_parser.py` — Markdown パーサー（テスト最重要）

**責務**: `revised_draft.md` を `ArticleDraft` に変換

- YAML frontmatter 抽出（`title` 取得）
- `## 修正履歴` セクション以降を除外
- Markdown → `ContentBlock` リストへ変換:
  - `# / ## / ###` → heading ブロック
  - 通常テキスト → paragraph ブロック
  - `> ` → blockquote ブロック
  - `- ` → list_item ブロック
  - `---` → separator ブロック
  - Markdown テーブル → `tables/` 内の対応 PNG を image ブロックに置換
- テーブル → 画像変換: `02_edit/tables/` 配下に事前生成済み PNG がある前提。なければ警告ログ

**参照**: 実際の `revised_draft.md`（`articles/asset_management/index-investing-portfolio-allocation/02_edit/revised_draft.md`）

### 3. `browser_client.py` — Playwright ブラウザ操作

**参照パターン**: `src/news/extractors/playwright.py` の async context manager

```python
class NoteBrowserClient:
    async def __aenter__(self) -> NoteBrowserClient: ...
    async def __aexit__(self, ...): ...

    # セッション管理
    async def _restore_session(self) -> bool          # .note-session.json からCookie復元
    async def wait_for_manual_login(self) -> bool      # headed ブラウザでユーザーの手動ログイン待ち
    async def _save_session(self) -> None              # セッション保存
    async def _is_logged_in(self) -> bool              # ログイン状態確認

    # エディタ操作
    async def create_new_draft(self) -> None           # https://note.com/notes/new へ遷移
    async def set_title(self, title: str) -> None      # タイトル入力
    async def insert_block(self, block: ContentBlock) -> None  # ブロック挿入（型ごとにディスパッチ）
    async def upload_image(self, image_path: Path) -> None     # 画像アップロード
    async def save_draft(self) -> str | None           # 下書き保存 → URL 返却
```

**エディタ入力戦略**:
- note.com のエディタは contenteditable な Rich Text Editor
- Markdown ショートカット対応: `## ` で見出し、`> ` で引用ブロック等
- テキスト入力は `page.keyboard.type()` でタイピングシミュレーション
- 画像は `page.set_input_files()` でファイルチューザー経由アップロード
- 各操作間に `typing_delay_ms` の待機を入れ bot 検知を回避

### 4. `draft_publisher.py` — オーケストレーター

```python
class DraftPublisher:
    async def publish(self, article_dir: Path, *, update_meta: bool = True) -> PublishResult:
        # 1. revised_draft.md を locate & parse
        # 2. ブラウザ起動 → セッション復元 or 手動ログイン待ち
        # 3. 新規記事作成ページへ遷移
        # 4. タイトル設定
        # 5. ContentBlock を順次挿入
        # 6. 下書き保存
        # 7. article-meta.json 更新（オプション）
        # 8. PublishResult 返却
```

### 5. `publish_to_note.py` — CLI

```bash
# 基本使用
uv run python scripts/publish_to_note.py articles/asset_management/index-investing-portfolio-allocation/

# オプション
uv run python scripts/publish_to_note.py <article_dir> --dry-run          # パースのみ（投稿しない）
uv run python scripts/publish_to_note.py <article_dir> --no-update-meta   # meta更新スキップ
uv run python scripts/publish_to_note.py --login-only                     # ログイン＆セッション保存のみ
```

## 認証フロー

```
初回:
  headed ブラウザ起動 → note.com/login 表示
  → ユーザーが手動でログイン（メール/SNS/2FA 全対応）
  → ログイン検知 → .note-session.json にCookie保存
  → 以降の操作を自動実行

2回目以降:
  .note-session.json からCookie復元 → headless ブラウザ起動
  → ログイン状態確認 → OK なら自動実行
  → NG（セッション切れ）→ headed に切り替え → 手動ログイン
```

## エラーハンドリング

| コード | 条件 | 対処 |
|--------|------|------|
| E001 | `revised_draft.md` が存在しない | `/finance-edit` の実行を案内して中断 |
| E002 | セッション切れ | headed に切り替えて手動ログイン待ち |
| E003 | エディタ読み込みタイムアウト | リトライ1回 → 失敗で中断 |
| E004 | 画像アップロード失敗 | 警告ログ出力、画像なしで続行 |
| E005 | 下書き保存失敗 | スクリーンショット保存して中断 |

## 設定変更

**.gitignore** に追加:
```
.note-session.json
```

**pyproject.toml**: 変更不要（`playwright` は既存 optional dependency）

## 実装順序（TDD）

| Step | 内容 | テスト |
|------|------|--------|
| 1 | `types.py` — Pydantic モデル定義 | `test_types.py` |
| 2 | `config.py` — 設定読み込み | `test_config.py` |
| 3 | `markdown_parser.py` — Markdown パース（最重要） | `test_markdown_parser.py` |
| 4 | `browser_client.py` — Playwright 操作 | `test_browser_client.py`（AsyncMock） |
| 5 | `draft_publisher.py` — オーケストレーター | `test_draft_publisher.py` |
| 6 | `publish_to_note.py` — CLI | 手動テスト |
| 7 | 実 note.com アカウントで統合テスト | 手動（headed モード） |

## テスト戦略

**ユニットテスト（自動化）**:
- `markdown_parser.py` が最重要 — 純粋ロジックなのでモック不要
  - `test_正常系_frontmatterを正しく抽出できる`
  - `test_正常系_修正履歴を除外できる`
  - `test_正常系_見出しブロックを正しくパースできる`
  - `test_正常系_テーブルを画像ブロックに変換できる`
  - `test_エッジケース_frontmatterがない場合`
  - `test_エッジケース_テーブルPNGが存在しない場合`
- `browser_client.py` — `unittest.mock.AsyncMock` で Playwright をモック（既存テストパターン: `tests/news/unit/extractors/test_playwright.py`）

**統合テスト（手動）**:
- `--dry-run` でパース結果確認
- `--login-only` でセッション保存確認
- 実際の記事で下書き作成→note.com上で内容確認

## 検証方法

1. `make check-all` で品質チェック通過
2. `uv run pytest tests/scripts/note_publisher/ -v` でユニットテスト通過
3. `uv run python scripts/publish_to_note.py <article_dir> --dry-run` でパース結果確認
4. `uv run python scripts/publish_to_note.py --login-only` でセッション保存確認
5. 実際の記事ディレクトリで `uv run python scripts/publish_to_note.py <article_dir>` を実行し、note.com に下書きが作成されることを確認

## 重要な参照ファイル

| ファイル | 用途 |
|----------|------|
| `src/news/extractors/playwright.py` | async context manager パターン |
| `tests/news/unit/extractors/test_playwright.py` | Playwright モックテストパターン |
| `scripts/generate_table_image.py` | scripts/ での Playwright 使用例、CLI パターン |
| `articles/asset_management/index-investing-portfolio-allocation/02_edit/revised_draft.md` | 入力ファイルの実例 |
| `scripts/session_utils.py` | Pydantic モデル・structlog パターン |
