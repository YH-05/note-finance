# save-to-article-graph スキル実装計画

## Context

wealth blog スクレイピング（`scrape_wealth_blogs.py`）と topic-discovery スキルが収集した情報を article-neo4j（bolt://localhost:7689）に蓄積するパイプラインが未整備。既存の `emit_graph_queue.py` + `save-to-graph` パターンを拡張し、2つの新コマンドマッパーとオーケストレータースキルを追加する。

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `scripts/emit_graph_queue.py` | 編集 | wealth-scrape / topic-discovery マッパー追加、authors 対応 |
| `docker/article-neo4j/init/01-constraints-indexes.cypher` | 編集 | Author 制約・インデックス追加 |
| `.claude/skills/save-to-article-graph/SKILL.md` | 新規 | オーケストレータースキル |
| `tests/scripts/test_emit_graph_queue.py` | 編集 | 新マッパーのユニットテスト追加 |

## Phase 1: フレームワーク拡張（emit_graph_queue.py）

### 1.1 authors 対応

現状 `_mapped_result()` (L269) に `authors` パラメータがなく、`_build_queue_doc()` (L1330) にも `authors` キーがない。save-to-graph SKILL.md は Author MERGE を定義済みだが、emit 側が未対応。

変更:
- `_mapped_result()`: `authors: list[dict[str, Any]] | None = None` パラメータ追加、戻り値に `"authors": authors or []` 追加
- `_build_queue_doc()`: `"authors": mapped.get("authors", [])` 追加
- `_empty_rels()` (L974): `"authored_by": []` 追加（新リレーションキー）

### 1.2 `_load_and_parse()` のディレクトリ入力対応

wealth-scrape backfill は `data/scraped/wealth/` ディレクトリを入力とする。現状の `_load_and_parse()` は JSON ファイルのみ対応。

変更:
- `command == "wealth-scrape"` かつ `input_path.is_dir()` の場合、`_scan_wealth_directory()` を呼び出す
- それ以外は既存の JSON ロードロジック

### 1.3 新ヘルパー: `_scan_wealth_directory(dir_path: Path)`

- `data/scraped/wealth/{domain}/*.md` を再帰的にスキャン
- 各ファイルの `---` 間の YAML frontmatter を正規表現でパース（PyYAML 不要）
- `data/config/wealth-management-themes.json` を読み込みテーマ情報を付加
- 戻り値: `{"session_id": "wealth-scrape-backfill-{timestamp}", "mode": "backfill", "articles": [...], "themes": {...}}`

## Phase 2: wealth-scrape マッパー

### 2.1 `map_wealth_scrape()` ディスパッチャー

- `data.get("mode") == "backfill"` or `"articles"` キー → `map_wealth_scrape_backfill()`
- `data.get("themes")` キー（incremental WealthScrapeSession）→ `map_wealth_scrape_incremental()`

### 2.2 `map_wealth_scrape_backfill()` ノードマッピング

| スクレイプデータ | ノード | ID生成 | 備考 |
|----------------|--------|--------|------|
| 記事 | Source | `generate_source_id(url)` | `source_type="blog"` |
| 著者（非空時） | Author | `uuid5("author:{name}")` | `author_type="media"` |
| テーマ（6件） | Topic | `uuid5("wealth-{name_en}")` | `category="wealth-management"` |
| ドメイン | Entity | `generate_entity_id(domain, "domain")` | `entity_type="domain"` |

リレーション:
- `tagged`: Source → Topic（記事タイトル+本文 vs テーマ keywords_en でマッチング）
- `authored_by`: Source → Author（author が非空の場合）

大量ファイル対策: ドメインごとに graph-queue を分割出力（1ファイル = 1ドメイン）

### 2.3 `map_wealth_scrape_incremental()` ノードマッピング

| データ | ノード | ID生成 |
|-------|--------|--------|
| テーマ内記事 | Source | `generate_source_id(url)` |
| テーマ | Topic | テーマ名からハッシュ |
| 記事 summary | Claim | `generate_claim_id(summary)` |

リレーション:
- `tagged`: Source → Topic（テーマグループから自明）
- `source_claim`: Source → Claim

### 2.4 COMMAND_MAPPERS 登録

```python
COMMAND_MAPPERS["wealth-scrape"] = map_wealth_scrape
```

## Phase 3: topic-discovery マッパー

`.claude/skills/topic-discovery/references/neo4j-mapping.md` に完全準拠。

### 3.1 `map_topic_discovery()` ノードマッピング

| データ | ノード | ID | 備考 |
|-------|--------|-----|------|
| セッション | Source | `{session_id}` 直接使用 | `source_type="original"` |
| カテゴリ | Topic | `content:{category_key}` | 7カテゴリ固定 |
| 各提案 | Claim | `ts:{session_id}:rank{rank}` | `claim_type="recommendation"` |
| 推奨銘柄 | Entity | `symbol:{ticker}` | `^` → index, 他 → stock |
| 検索トレンド | Fact | `trend:{session_id}:{i}:{j}` | `--no-search` 時スキップ |

**ID は neo4j-mapping.md の文字列ベース ID を使用**（UUID5 ではない）。既存の topic-discovery Phase 5.3 の直接 Cypher と MERGE が冪等に動作するため。

### 3.2 リレーション

| リレーション | From → To |
|-------------|-----------|
| `tagged` | Source → Topic, Claim → Topic |
| `source_claim` | Source → Claim |
| `claim_entity` | Claim → Entity |
| `source_fact` | Source → Fact |

### 3.3 COMMAND_MAPPERS 登録

```python
COMMAND_MAPPERS["topic-discovery"] = map_topic_discovery
```

## Phase 4: article-neo4j スキーマ更新

`docker/article-neo4j/init/01-constraints-indexes.cypher` に追加:

```cypher
CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE;
CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.name);
CREATE INDEX author_type IF NOT EXISTS FOR (a:Author) ON (a.author_type);
```

既存コンテナには `cypher-shell` で手動投入。

## Phase 5: save-to-article-graph スキル

### 5.1 ファイル: `.claude/skills/save-to-article-graph/SKILL.md`

処理フロー:
1. emit: `uv run python scripts/emit_graph_queue.py --command {command} --input {input}`
2. save: `NEO4J_URI=bolt://localhost:7689 /save-to-graph --source {command}`

使用例:
```bash
# backfill（ディレクトリ指定）
/save-to-article-graph --command wealth-scrape --input data/scraped/wealth/

# incremental（セッション JSON）
/save-to-article-graph --command wealth-scrape --input .tmp/wealth-scrape-*.json

# topic-discovery
/save-to-article-graph --command topic-discovery --input .tmp/topic-suggestions/2026-03-16_1800.json

# dry-run
/save-to-article-graph --command topic-discovery --dry-run
```

## Phase 6: テスト

`tests/scripts/test_emit_graph_queue.py` に追加:

| テスト | 内容 |
|-------|------|
| `test_map_wealth_scrape_backfill` | frontmatter パース → Source/Topic/Author/Entity 生成確認 |
| `test_map_wealth_scrape_incremental` | WealthScrapeSession → Source/Topic/Claim 生成確認 |
| `test_map_topic_discovery` | セッション JSON → Source/Topic/Claim/Entity/Fact + リレーション確認 |
| `test_topic_discovery_id_format` | ID が neo4j-mapping.md の文字列形式であること |
| `test_scan_wealth_directory` | YAML frontmatter 正規表現パーサーの正常系・異常系 |

## 再利用する既存コード

| 関数/パターン | パス | 用途 |
|-------------|------|------|
| `_make_source()` | emit_graph_queue.py:239 | Source dict 生成 |
| `_mapped_result()` | emit_graph_queue.py:269 | マッパー出力標準化 |
| `generate_source_id()` | pdf_pipeline/services/id_generator.py | URL → Source ID |
| `generate_entity_id()` | 同上 | Entity ID |
| `generate_claim_id()` | 同上 | Claim ID |
| `generate_fact_id()` | 同上 | Fact ID |
| `map_asset_management()` | emit_graph_queue.py | テーマベースマッピングのパターン参照 |

## 検証手順

1. `uv run python scripts/emit_graph_queue.py --command topic-discovery --input .tmp/topic-suggestions/2026-03-16_1800.json` → graph-queue JSON 生成確認
2. `uv run python scripts/emit_graph_queue.py --command wealth-scrape --input data/scraped/wealth/` → graph-queue JSON 生成確認
3. `NEO4J_URI=bolt://localhost:7689 NEO4J_PASSWORD=gomasuke /save-to-graph --source topic-discovery --dry-run` → Cypher 出力確認
4. article-neo4j に投入後、Browser (http://localhost:7476) でノード・リレーション確認
5. `make test` でテスト通過確認
