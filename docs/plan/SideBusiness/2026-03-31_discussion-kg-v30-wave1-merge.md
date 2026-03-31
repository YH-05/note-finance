# 議論メモ: KG v3.0 YAML SSoT整備 Wave1 マージ完了

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

PR #294 「[Wave1] knowledge-graph-schema.yaml を v3.0 に更新（YAML SSoT整備）」(branch: `feature/prj105`) のマージ作業。
CIのpyrightエラー22件と単体テスト失敗1件を修正してからマージした。

## 議論のサマリー

### CIエラーの特定と修正

#### 1. pyrightエラー22件（reportInvalidTypeForm × 21件）

**原因**: `tests/unit/test_tavily_mcp/test_server.py` で `unittest.mock.patch` をtype annotationとして使用していた。
`patch` は関数であり型ではないため `reportInvalidTypeForm` エラーが21件発生。

**修正**:
```python
# Before
from unittest.mock import patch
def test_xxx(self, mock_post: patch, mock_pool: patch) -> None:

# After
from unittest.mock import MagicMock, patch
def test_xxx(self, mock_post: MagicMock, mock_pool: MagicMock) -> None:
```

#### 2. pyrightエラー1件（reportMissingImports）

**原因**: `tests/news_scraper/unit/test_scrape_jetro.py` が削除済みの `scripts/scrape_jetro.py` を参照しようとしていた。

**修正**: `pyproject.toml` の `[tool.pyright]` の `exclude` リストに追加。
テスト本体の修正は独立Issueで対応予定。

#### 3. 単体テスト失敗（assert 1 == 0）

**原因**: `tests/news_scraper/unit/test_scrape_finance_news.py` の `test_正常系_新しいディレクトリは削除しない` がハードコード日付 `2026-02-28` を使用していた。
今日(2026-03-31)時点では31日前となり `max_age_days=30` を超えて削除対象と判定されてしまった。

**修正**:
```python
# Before
recent_dir = tmp_path / "2026-02-28"

# After
today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
recent_dir = tmp_path / today_str
```

### マージコンフリクト

mainブランチが先行していたため `test_server.py` でコンフリクト発生。
HEAD (MagicMock修正版) vs origin/main (元のpatch版) → MagicMock版を採用して解決。

### マージ完了

- PR #294 マージ日時: 2026-03-31T01:24:06Z
- マージ方法: squash merge
- クローズされたIssue: #278

## 決定事項

1. **pyrightアノテーション修正方針**: `patch` を型として使うのは誤り。モックの型は `MagicMock` を使う
2. **pyrightのexclude活用**: 削除済みスクリプトを参照するテストは一時的にexcludeリストで対処し、独立Issueで根本修正する
3. **時間依存テストの動的化**: ハードコード日付は `datetime.now()` で動的生成するルールを徹底する

## アクションアイテム

- [ ] KG v3.0 YAML SSoT Wave2以降の実装継続（Issue #278が残存） (優先度: 高)
- [ ] test_scrape_jetro.pyの孤立テスト修正を独立Issueで対応 (優先度: 低)

## 次回の議論トピック

- KG v3.0 Wave2の実装内容とスコープ確認
- scrape_jetro.pyの削除経緯と孤立テストのクリーンアップ方針

## 参考情報

- PR #294: https://github.com/YH-05/note-finance/pull/294
- Issue #278: KG v3.0 YAML SSoT整備（Wave2以降）
- pyright `reportInvalidTypeForm`: https://microsoft.github.io/pyright/#/configuration
- `unittest.mock.patch` vs `MagicMock`: patch は関数・コンテキストマネージャ。引数の型アノテーションには MagicMock を使う
