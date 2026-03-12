# DATA_ROOT 環境変数によるデータパス一元管理

## Context

プロジェクトの生データ（CSV, Parquet, PDF, DuckDB等）とドキュメント（PDF→Markdown/JSON→Neo4j）を外部ボリューム `/Volumes/NeoData` に格納し、プロジェクトからアクセスしたい。

**現状の問題**:
- 65ファイル・135箇所で `Path("data/...")` がハードコードされている
- パス管理モジュールが存在せず、各パッケージが独自にデフォルトパスを定義
- 環境変数によるパス切替は2箇所のみ（`RSS_DATA_DIR`, `FINANCE_NEWS_LOCAL_DIR`）

**目標**: 環境変数 `DATA_ROOT` で `data/` → `/Volumes/NeoData/finance/` に一括切替。config ファイルはプロジェクト内に残す。

## 設計方針

### パス解決ルール

| サブパス | DATA_ROOT 未設定 | DATA_ROOT=/Volumes/NeoData/finance/ |
|---------|-----------------|-------------------------------------|
| `raw/rss` | `{project}/data/raw/rss` | `/Volumes/NeoData/finance/raw/rss` |
| `processed` | `{project}/data/processed` | `/Volumes/NeoData/finance/processed` |
| `config/rss-presets.json` | `{project}/data/config/rss-presets.json` | `{project}/data/config/rss-presets.json` (**常にローカル**) |

### API

```python
from data_paths import get_path, get_data_root, get_config_dir

get_path("raw/rss")                    # DATA_ROOT / "raw/rss"
get_path("config/rss-presets.json")    # 常に {project}/data/config/rss-presets.json
get_data_root()                        # DATA_ROOT or {project}/data
get_config_dir()                       # 常に {project}/data/config
```

`config/` で始まるサブパスは自動的にプロジェクトローカルにルーティングされる。

---

## Phase 0: `data_paths` パッケージ作成

### 新規ファイル

| ファイル | 内容 |
|---------|------|
| `src/data_paths/__init__.py` | 公開API エクスポート |
| `src/data_paths/paths.py` | コア実装 (~100行) |
| `src/data_paths/_logging.py` | structlog設定（`src/rss/_logging.py` と同パターン） |
| `src/data_paths/py.typed` | 型チェック用マーカー |
| `tests/data_paths/unit/test_paths.py` | ユニットテスト |
| `tests/data_paths/__init__.py` | テストパッケージ |
| `tests/data_paths/unit/__init__.py` | テストパッケージ |

### `paths.py` コア設計

```python
"""DATA_ROOT 環境変数によるデータパス一元管理."""

from functools import lru_cache
from pathlib import Path
import os

class DataPathError(Exception): ...

@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """pyproject.toml を含むプロジェクトルートを返す."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise DataPathError("pyproject.toml not found")

@lru_cache(maxsize=1)
def get_data_root() -> Path:
    """DATA_ROOT 環境変数、未設定なら {project}/data を返す."""
    env_val = os.environ.get("DATA_ROOT")
    if env_val:
        root = Path(env_val).resolve()
        if not root.exists():
            raise DataPathError(
                f"DATA_ROOT={env_val} does not exist. "
                "Is the external volume mounted?"
            )
        return root
    return get_project_root() / "data"

def get_config_dir() -> Path:
    """常にプロジェクトローカルの data/config/ を返す."""
    return get_project_root() / "data" / "config"

def get_path(sub_path: str) -> Path:
    """サブパスを適切なルートに結合して返す."""
    if sub_path.startswith("config/") or sub_path == "config":
        remainder = sub_path.removeprefix("config").lstrip("/")
        return get_config_dir() / remainder if remainder else get_config_dir()
    return get_data_root() / sub_path

def ensure_data_dirs(extra: list[str] | None = None) -> list[Path]:
    """標準ディレクトリ構造を作成."""
    standard = [
        "raw/rss", "raw/pdfs", "raw/ai-research/pdfs",
        "raw/fred/indicators", "raw/etfcom", "raw/report-scraper/pdfs",
        "processed", "exports", "exports/news-workflow",
        "scraped/reports", "scraped/pdfs",
        "news", "market", "stock",
        "macroeconomics", "investment_theme", "topic-history", "sample_report",
    ]
    dirs_to_create = standard + (extra or [])
    root = get_data_root()
    created = []
    for d in dirs_to_create:
        path = root / d
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created

def _reset_cache() -> None:
    """テスト用: lru_cache をクリア."""
    get_project_root.cache_clear()
    get_data_root.cache_clear()
```

### 変更する既存ファイル

| ファイル | 変更内容 |
|---------|---------|
| `pyproject.toml` L61 | `packages` に `"src/data_paths"` を追加 |
| `.env.example` L22-23 | `DATA_DIR` コメントを `DATA_ROOT` に更新し説明追加 |

### テストケース

```
test_正常系_デフォルトでプロジェクトルートのdata配下を返す
test_正常系_DATA_ROOT設定時に外部パスを返す
test_正常系_config_pathは常にプロジェクトローカル
test_正常系_get_pathでサブパスを結合
test_異常系_DATA_ROOTが存在しないパスでDataPathError
test_正常系_ensure_data_dirsでディレクトリ作成
test_エッジケース_config単体パス
```

---

## Phase 1-5: 各パッケージへの段階的移行

各Phaseは独立したPRとして実施可能。

### Phase 1: `rss` パッケージ

| ファイル | Before | After |
|---------|--------|-------|
| `src/rss/cli/main.py:48` | `DEFAULT_DATA_DIR = Path("data/raw/rss")` | `get_path("raw/rss")` |
| `src/rss/cli/main.py:643` | `default=Path("data/config/rss-presets.json")` | `default=get_path("config/rss-presets.json")` |
| `src/rss/mcp/server.py:74` | `DEFAULT_DATA_DIR = Path("data/raw/rss")` | `get_path("raw/rss")` |
| `src/rss/mcp/server.py:91` | `os.environ.get("RSS_DATA_DIR", ...)` | `RSS_DATA_DIR` 優先、fallback を `get_path` に |
| `src/rss/services/company_scrapers/pdf_handler.py:64` | `Path("data/raw/ai-research/pdfs")` | `get_path("raw/ai-research/pdfs")` |

### Phase 2: `pdf_pipeline` パッケージ

| ファイル | Before | After |
|---------|--------|-------|
| `src/pdf_pipeline/cli/main.py:53` | `Path("data/processed")` | `get_path("processed")` |
| `src/pdf_pipeline/cli/main.py:58` | `Path("data/config/pdf-pipeline-config.yaml")` | `get_path("config/pdf-pipeline-config.yaml")` |
| `src/pdf_pipeline/types.py:162-163` | `default=Path("data/processed")` | `default_factory=lambda: get_path("processed")` |
| `src/pdf_pipeline/types.py:188-189` | `default=Path("data/config/chunk-template.md")` | `default_factory=lambda: get_path("config/chunk-template.md")` |

### Phase 3: `report_scraper` パッケージ

| ファイル | Before | After |
|---------|--------|-------|
| `src/report_scraper/cli/main.py:51` | `Path("data/scraped/reports")` | `get_path("scraped/reports")` |
| `src/report_scraper/cli/main.py:54` | `Path("data/config/report-scraper-config.yaml")` | `get_path("config/report-scraper-config.yaml")` |
| `src/report_scraper/types.py:168` | `default=Path("data/scraped/reports")` | `default_factory=lambda: get_path("scraped/reports")` |
| `src/report_scraper/types.py:172` | `default=Path("data/scraped/pdfs")` | `default_factory=lambda: get_path("scraped/pdfs")` |
| `src/report_scraper/storage/pdf_store.py:39` | `"data/raw/report-scraper/pdfs"` | `str(get_path("raw/report-scraper/pdfs"))` |

### Phase 4: `news` パッケージ

| ファイル | Before | After |
|---------|--------|-------|
| `src/news/config/models.py` | 各 `Path("data/config/...")` | `get_path("config/...")` |
| `src/news/scripts/finance_news_workflow.py:65` | `Path("data/config/news-collection-config.yaml")` | `get_path("config/...")` |
| `src/news/sources/yfinance/macro.py:43` | `Path("data/config/news_search_keywords.yaml")` | `get_path("config/...")` |

### Phase 5: `scripts/`

| ファイル | Before | After |
|---------|--------|-------|
| `scripts/prepare_news_session.py:63,66` | `Path("data/raw/rss")`, `Path("data/config/...")` | `get_path(...)` |
| `scripts/prepare_asset_management_session.py:55,58,386` | 同上 | `get_path(...)` |
| `scripts/collect_finance_news.py:286,293` | 同上 | `get_path(...)` |
| `scripts/rss_recent_articles.py:15` | `Path("data/raw/rss")` | `get_path("raw/rss")` |
| `scripts/note_publisher/types.py:203` | `default=Path("data/config/...")` | `default_factory=lambda: get_path("config/...")` |
| `scripts/scrape_finance_news.py:57` | `os.environ.get("FINANCE_NEWS_LOCAL_DIR", "data/scraped")` | fallback を `get_path("scraped")` に |
| `scripts/collect_finance_news_stock.py:454` 等 (4ファイル) | ハードコード絶対パス `/Users/yukihata/Desktop/finance/data/config/...` | `get_path("config/finance-news-themes.json")` |

### Pydantic default_factory パターン

```python
# Before (import時に評価):
output_dir: Path = Field(default=Path("data/processed"))

# After (インスタンス生成時に評価):
output_dir: Path = Field(default_factory=lambda: get_path("processed"))
```

`default_factory` を使うことで、`DATA_ROOT` がモジュールimport後に設定されても正しく動作する。

---

## 外部ボリュームセットアップ

```bash
# .env に追加
DATA_ROOT=/Volumes/NeoData/finance

# ディレクトリ構造の初期化（一回限り）
python -c "from data_paths import ensure_data_dirs; ensure_data_dirs()"
```

生成されるディレクトリ構造:
```
/Volumes/NeoData/
├── neo4j/           # 既存（docker-compose.yml）
└── finance/         # 新規
    ├── raw/rss/
    ├── raw/pdfs/
    ├── raw/ai-research/pdfs/
    ├── raw/fred/indicators/
    ├── processed/
    ├── exports/
    ├── scraped/
    ├── news/
    ├── market/
    └── ...
```

---

## 後方互換性

- `DATA_ROOT` 未設定時: 全パスが現在と完全に同一（`{project}/data/...`）
- 既存環境変数 `RSS_DATA_DIR`, `FINANCE_NEWS_LOCAL_DIR` は引き続き優先
- 関数シグネチャの変更なし
- 各Phase は独立PRで段階移行可能

---

## 検証方法

### Phase 0 完了後

```bash
# 1. ユニットテスト
uv run pytest tests/data_paths/ -v

# 2. デフォルト動作確認
python -c "from data_paths import get_path; print(get_path('raw/rss'))"
# → .../note-finance/data/raw/rss

# 3. DATA_ROOT 設定時の動作確認
DATA_ROOT=/tmp/test-data python -c "
from data_paths import get_path, ensure_data_dirs
ensure_data_dirs()
print(get_path('raw/rss'))
print(get_path('config/rss-presets.json'))
"
# → /tmp/test-data/raw/rss
# → .../note-finance/data/config/rss-presets.json

# 4. 型チェック・リント
make check-all
```

### 各Phase移行後

```bash
# 全テストが通ることを確認
make test

# DATA_ROOT設定下でCLIが動作することを確認
DATA_ROOT=/Volumes/NeoData/finance rss-cli feeds list
DATA_ROOT=/Volumes/NeoData/finance pdf-pipeline --help
```

### 最終検証（全Phase完了後）

```bash
# .env に DATA_ROOT=/Volumes/NeoData/finance を設定して全機能テスト
make check-all
```
