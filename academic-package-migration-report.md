# academic パッケージ移植レポート

**日付**: 2026-03-19
**移植元**: quants (`/Users/yukihata/Desktop/quants/src/academic/`)
**移植先**: note-finance (`/Users/yukihata/Desktop/note-finance/src/academic/`)

---

## 1. 概要

quants プロジェクトの `academic` パッケージを note-finance プロジェクトに移植した。
alphaxiv MCP で調査した論文の著者・引用文献情報を arXiv / Semantic Scholar API から自動取得し、
Neo4j ナレッジグラフに投入するためのパッケージである。

### 移植の目的

- note-finance の研究ワークフローで alphaxiv MCP を使用して論文を調査した後、
  その論文の著者ネットワーク・引用グラフを Neo4j に自動構築する
- 既存の graph-queue パイプライン（`emit_graph_queue.py` → `/save-to-graph`）と統合する

### 移植方針

- quants 固有の内部依存（`database`, `market.cache`, `edgar`, `utils_core`）を
  note-finance の既存インフラまたはスタンドアロン実装に置換
- 機能・API インターフェースは完全に維持
- note-finance の graph-queue スキーマ v2.2 に適合

---

## 2. パッケージ構成

```
src/academic/
├── __init__.py          # パッケージエクスポート
├── __main__.py          # CLI エントリポイント (fetch / backfill)
├── types.py             # 型定義 (frozen dataclass)
├── errors.py            # 例外階層
├── rate_limiter.py      # スタンドアロン RateLimiter [新規]
├── retry.py             # tenacity ベースリトライデコレータ
├── cache.py             # スタンドアロン SQLite キャッシュ [新規]
├── arxiv_client.py      # arXiv Atom API クライアント
├── s2_client.py         # Semantic Scholar Graph API クライアント
├── fetcher.py           # 3段フォールバック オーケストレータ
├── mapper.py            # PaperMetadata → graph-queue JSON マッパー
└── py.typed             # PEP 561 マーカー
```

---

## 3. 各ファイルの詳細

### 3.1 types.py — 型定義

変更なし。quants 版をそのまま使用。

| データクラス | フィールド | 用途 |
|-------------|-----------|------|
| `AuthorInfo` | name, s2_author_id, organization | 著者情報 |
| `CitationInfo` | title, arxiv_id, s2_paper_id | 引用/被引用論文 |
| `PaperMetadata` | arxiv_id, title, authors, references, citations, abstract, published, updated | 論文メタデータ全体 |
| `AcademicConfig` | s2_api_key, s2_rate_limit, arxiv_rate_limit, cache_ttl, max_retries, timeout | API 設定 |

### 3.2 errors.py — 例外階層

変更なし。HTTP ステータスコードに基づくリトライ判定を提供。

```
AcademicError (基底)
├── RetryableError (429, 5xx) → リトライ対象
│   └── RateLimitError (429)
├── PermanentError (403, 404) → リトライ不可
│   └── PaperNotFoundError (404)
└── ParseError (パース失敗)
```

### 3.3 rate_limiter.py — スレッドセーフ RateLimiter [新規]

quants の `edgar.rate_limiter.RateLimiter` から抽出したスタンドアロン実装。
外部依存なし。

| 項目 | 値 |
|------|-----|
| アルゴリズム | 最小インターバル方式 |
| スレッドセーフ | `threading.Lock` |
| デフォルト | 10 req/sec |

**変更点**: `edgar.config.DEFAULT_RATE_LIMIT_PER_SECOND` → ローカル定数に変更

### 3.4 retry.py — リトライデコレータ

tenacity ベースの指数バックオフ + ジッター。

| パラメータ | デフォルト |
|-----------|----------|
| 最大試行回数 | 3 |
| 初回待機 | 1秒 |
| 最大待機 | 60秒 |
| ジッター | 0〜1秒 |
| リトライ条件 | `RetryableError` のみ |

**変更点**: `from utils_core.logging import get_logger` → `import structlog`

### 3.5 cache.py — SQLite キャッシュ [新規]

quants の `market.cache.SQLiteCache` に相当するスタンドアロン実装。
`json.dumps/loads` でシリアライズ、TTL ベースの有効期限管理。

| 設定 | デフォルト |
|------|----------|
| DB パス | `data/cache/academic.db` |
| TTL | 604,800秒（7日） |
| 最大エントリ | 5,000 |
| 超過時 | 古いエントリから自動削除 |

**API**:
- `get(key) -> dict | None` — TTL 超過時は自動削除して None を返す
- `set(key, value)` — INSERT OR REPLACE + 超過時の自動 eviction
- `make_cache_key(arxiv_id)` — `"academic:paper:{arxiv_id}"` 形式

### 3.6 arxiv_client.py — arXiv API クライアント

arXiv Atom API (`export.arxiv.org/api/query`) から論文メタデータを取得。
feedparser + defusedxml でパース。

| 機能 | 詳細 |
|------|------|
| メタデータ | タイトル、著者名、アフィリエーション、要旨、公開日 |
| 引用情報 | 提供なし（常に空タプル） |
| レート制限 | 3 req/sec（arXiv 推奨） |
| XML パーシング | defusedxml (セキュア) + feedparser |

**変更点**:
- `from edgar.rate_limiter import RateLimiter` → `from .rate_limiter import RateLimiter`
- `from utils_core.logging import get_logger` → `import structlog`

### 3.7 s2_client.py — Semantic Scholar API クライアント

Semantic Scholar Graph API (`api.semanticscholar.org/graph/v1`) から論文メタデータを取得。

| 機能 | 詳細 |
|------|------|
| メタデータ | タイトル、著者（S2 author ID 付き）、要旨、公開日 |
| 引用情報 | references + citations（arXiv ID 付き） |
| バッチ取得 | POST /paper/batch（500件/リクエスト自動分割） |
| 認証 | `S2_API_KEY` 環境変数 or `AcademicConfig.s2_api_key` |
| レート制限 | 1 req/sec（API キーなし時） |

**変更点**: rate_limiter/logging の差し替え（arxiv_client と同様）

### 3.8 fetcher.py — PaperFetcher オーケストレータ

3段フォールバック戦略:

```
1. SQLite キャッシュ → ヒットなら即 return
2. S2Client.fetch_paper() → 成功なら PaperMetadata に変換 + キャッシュ保存
3. ArxivClient.fetch_paper() → S2 失敗時のフォールバック（著者のみ、引用なし）
```

| 機能 | 詳細 |
|------|------|
| 単一取得 | `fetch_paper(arxiv_id)` |
| バッチ取得 | `fetch_papers_batch(arxiv_ids)` — キャッシュ分離 + S2 バッチ + arXiv 個別フォールバック |
| DI 対応 | `S2ClientProtocol`, `ArxivClientProtocol`, `CacheProtocol` |
| シリアライズ | `paper_metadata_to_dict()` / `_dict_to_paper_metadata()` |

**変更点**:
- `from market.cache.cache import SQLiteCache` → `from .cache import SQLiteCache`
- logging の差し替え

### 3.9 mapper.py — graph-queue マッパー

PaperMetadata リストを note-finance の graph-queue スキーマ v2.2 に変換。

| 生成ノード | 説明 |
|-----------|------|
| Source | `source_type="paper"`, `publisher="arXiv"` |
| Author | `author_type="academic"` |

| 生成リレーション | 説明 |
|-----------------|------|
| AUTHORED_BY | Source → Author |
| CITES | Source → Source（existing_source_ids 内の参照のみ） |
| COAUTHORED_WITH | Author ↔ Author（50名以下の論文のみ、paper_count 付き） |

**変更点**:
- `from database.id_generator import ...` → `from pdf_pipeline.services.id_generator import ...`
- graph-queue 空構造に note-finance 固有フィールド追加: `chunks`, `stances`, `questions`, `extracted_from`, `holds_stance`, `on_entity`, `based_on`
- `schema_version`: `"2.1"` → `"2.2"`

### 3.10 __main__.py — CLI

| サブコマンド | 用途 | 出力 |
|------------|------|------|
| `fetch` | 論文メタデータ取得 | `.tmp/academic/papers.json` |
| `backfill` | バッチ取得 + graph-queue 生成 | `.tmp/academic/graph-queue.json` |

```bash
# 単一論文
python -m academic fetch --arxiv-id 2301.08245

# 複数論文
python -m academic fetch --arxiv-ids 2301.08245 2303.09406

# バックフィル（Neo4j 投入用 graph-queue JSON 生成）
python -m academic backfill --ids-file ids.txt --output-dir .tmp/academic
```

---

## 4. 依存関係マッピング

### 外部ライブラリ

| ライブラリ | 用途 | note-finance での状態 |
|-----------|------|---------------------|
| `httpx>=0.28.1` | HTTP クライアント | 既存 ✅ |
| `feedparser>=6.0.12` | Atom XML パース | 既存 ✅ |
| `tenacity>=9.1.2` | リトライデコレータ | 既存 ✅ |
| `structlog>=25.4.0` | 構造化ロギング | 既存 ✅ |
| `defusedxml>=0.7.1` | セキュアな XML パース | **追加** ⚡ |

### 内部依存の差し替え

| quants (移植元) | note-finance (移植先) | 方式 |
|----------------|---------------------|------|
| `database.id_generator` | `pdf_pipeline.services.id_generator` | パス変更のみ（同一 UUID5 実装） |
| `edgar.rate_limiter.RateLimiter` | `academic.rate_limiter.RateLimiter` | スタンドアロン抽出 |
| `market.cache.SQLiteCache` | `academic.cache.SQLiteCache` | 軽量再実装 |
| `utils_core.logging.get_logger` | `structlog.get_logger` | 直接使用 |

---

## 5. pyproject.toml 変更

```diff
 dependencies = [
     ...
+    "defusedxml>=0.7.1",
 ]

 [tool.hatch.build.targets.wheel]
-packages = ["src/rss", ..., "src/youtube_transcript"]
+packages = ["src/rss", ..., "src/youtube_transcript", "src/academic"]
```

---

## 6. graph-queue スキーマ適合

### quants (v2.1) → note-finance (v2.2) の差分

| 項目 | quants | note-finance |
|------|--------|-------------|
| schema_version | 2.1 | **2.2** |
| ノード: chunks | なし | **あり** |
| ノード: stances | なし | **あり** |
| ノード: questions | なし | **あり** |
| リレーション: extracted_from | なし | **あり** |
| リレーション: holds_stance | なし | **あり** |
| リレーション: on_entity | なし | **あり** |
| リレーション: based_on | なし | **あり** |
| リレーション: about | あり | `about` → 維持 |
| quants 固有リレーション | exploits, evaluates, quantified_by 等 | **除外**（note-finance 未使用） |

academic mapper が出力する graph-queue は note-finance の `/save-to-graph` コマンドと完全互換。

---

## 7. ID 生成の互換性

両プロジェクトの `generate_source_id` / `generate_author_id` は同一の UUID5 アルゴリズムを使用。

```python
# 両プロジェクトで同一の ID が生成される
generate_source_id("https://arxiv.org/abs/2301.08245")
# → 同一の UUID5 文字列

generate_author_id("John Doe", "academic")
# → 同一の UUID5 文字列
```

これにより、quants と note-finance で同じ論文を処理した場合でも ID が衝突しない（同一 ID が生成される）。

---

## 8. 動作確認結果

### インポートテスト

```
✅ from academic import PaperFetcher, map_academic_papers, AcademicConfig
```

### ユニットテスト

| テスト | 結果 |
|--------|------|
| Mapper 空データ | ✅ schema_version=2.2, note-finance 固有フィールド存在 |
| Mapper 1論文 | ✅ sources=1, authors=2, authored_by=2, coauthored_with=1 |
| SQLiteCache get/set | ✅ TTL ベース、存在しないキーは None |
| RateLimiter acquire | ✅ スレッドセーフ |

### E2E テスト（実 API 呼び出し）

```
✅ python -m academic fetch --arxiv-id 2301.08245
   → S2 API 経由で取得成功
   → 著者 7名（S2 author ID 付き）
   → 参考文献 98件、被引用 37件
   → .tmp/academic/papers.json に出力
```

---

## 9. 使い方

### 基本ワークフロー

```bash
# 1. alphaxiv MCP で論文を調査（Claude Code 内）
#    → arXiv ID を取得

# 2. 論文メタデータを取得
python -m academic fetch --arxiv-id 2505.11122

# 3. バッチでバックフィル（複数論文 → graph-queue JSON）
python -m academic backfill \
  --ids-file data/arxiv-ids.txt \
  --output-dir .tmp/academic

# 4. graph-queue → Neo4j 投入
/emit-graph-queue --command academic-fetch --input .tmp/academic/graph-queue.json
/save-to-graph
```

### Python API

```python
from academic import PaperFetcher, paper_metadata_to_dict, map_academic_papers

# 単一論文取得
with PaperFetcher() as fetcher:
    paper = fetcher.fetch_paper("2301.08245")
    print(paper.title)
    print(f"Authors: {len(paper.authors)}")
    print(f"References: {len(paper.references)}")

# graph-queue 生成
papers_dict = [paper_metadata_to_dict(paper)]
graph_queue = map_academic_papers({
    "papers": papers_dict,
    "existing_source_ids": [],  # 既存 Neo4j Source ID（CITES フィルタ用）
})
```

### 環境変数

| 変数 | 用途 | デフォルト |
|------|------|----------|
| `S2_API_KEY` | Semantic Scholar API キー | なし（レート制限あり） |

---

## 10. 今後の作業

| 項目 | 優先度 | 説明 |
|------|--------|------|
| `emit_graph_queue.py` に `academic-fetch` マッパー追加 | 高 | `/emit-graph-queue --command academic-fetch` 対応 |
| テストスイート移植 | 中 | `tests/academic/` の unit/property テスト |
| `/academic-fetch` スラッシュコマンド作成 | 中 | Claude Code コマンドとして統合 |
| S2 API キー取得・設定 | 低 | レート制限緩和（100 req/sec） |
