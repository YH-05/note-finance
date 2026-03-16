# save-to-article-graph スキル実装計画（精査版）

## Context

wealth blog スクレイピング（`scrape_wealth_blogs.py`）と topic-discovery スキルが収集した情報を article-neo4j（bolt://localhost:7689）に蓄積するパイプラインが未整備。既存の `emit_graph_queue.py` + `save-to-graph` パターンを拡張し、2つの新コマンドマッパーとオーケストレータースキルを追加する。

元プラン: `docs/plan/2026-03-16_save-to-article-graph-skill.md`

## 元プランからの変更点

| # | 変更 | 理由 |
|---|------|------|
| 1 | **Author サポートを除外** | 全239ファイルの `author` が空文字。save-to-graph も AUTHORED_BY リレーション未対応。デッドコードになるため後回し |
| 2 | **`tagged` を `_empty_rels()` に追加** | 既存の `_empty_rels()` には `tagged` がない。暗黙 all-to-all ワイヤリングでは不正確（全6テーマにタグ付けされてしまう） |
| 3 | **`topic_key` プロパティを Topic に追加** | article-neo4j に `topic_key` UNIQUE 制約がある（L23）。topic-discovery の Topic は `topic_key` 必須 |
| 4 | **`run()` を list 対応に拡張** | wealth-scrape backfill はドメインごとに分割出力（239ファイル一括は非現実的） |

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `scripts/emit_graph_queue.py` | 編集 | 新マッパー2つ + フレームワーク拡張 |
| `docker/article-neo4j/init/01-constraints-indexes.cypher` | 編集 | Author 制約・インデックス追加（将来準備） |
| `.claude/skills/save-to-article-graph/SKILL.md` | 新規 | オーケストレータースキル |
| `tests/scripts/test_emit_graph_queue.py` | 編集 | 新マッパーのユニットテスト追加 |

## Phase 1: フレームワーク拡張（emit_graph_queue.py）

### 1.1 `_empty_rels()` に `tagged` 追加（L974）

```python
def _empty_rels() -> dict[str, list[dict[str, str]]]:
    return {
        "tagged": [],           # 追加
        "source_fact": [],
        "source_claim": [],
        # ... 既存10キーはそのまま
    }
```

### 1.2 `_parse_yaml_frontmatter()` 新ヘルパー

```python
def _parse_yaml_frontmatter(file_path: Path) -> dict[str, str] | None:
    """Parse YAML frontmatter between --- delimiters (regex, no PyYAML)."""
```

- 正規表現: `^---\n(.*?)\n---` (DOTALL)
- `key: 'value'` or `key: value` をパース
- 戻り値: `{"url": ..., "title": ..., "date": ..., "author": ..., "domain": ...}` or `None`

### 1.3 `_scan_wealth_directory()` 新ヘルパー

```python
def _scan_wealth_directory(dir_path: Path) -> list[dict[str, Any]]:
```

- `{dir_path}/{domain}/*.md` をスキャン
- `data/config/wealth-management-themes.json` を読み込み
- **ドメインごとに1 dict** を返す（list で返す）
- 各 dict: `{"session_id": "wealth-scrape-backfill-{domain}-{ts}", "mode": "backfill", "domain": domain, "articles": [...], "themes": themes}`

### 1.4 `_load_and_parse()` ディレクトリ対応（L1274）

- 戻り値型: `dict[str, Any] | list[dict[str, Any]] | None`
- `command == "wealth-scrape" and input_path.is_dir()` → `_scan_wealth_directory()` 呼び出し → mapper を各 dict に適用 → list で返す
- それ以外は既存 JSON ロードロジック

### 1.5 `run()` の list 対応（L1388）

- `mapped` が list の場合、各要素に `_build_queue_doc()` + `_write_output()` を実行
- 出力ファイルを全て表示

### 1.6 COMMAND_MAPPERS 登録（L1167）

```python
COMMAND_MAPPERS["wealth-scrape"] = map_wealth_scrape
COMMAND_MAPPERS["topic-discovery"] = map_topic_discovery
```

## Phase 2: wealth-scrape マッパー

### 2.1 `map_wealth_scrape()` ディスパッチャー

- `data.get("mode") == "backfill"` → `map_wealth_scrape_backfill()`
- それ以外（`themes` キーあり）→ `map_wealth_scrape_incremental()`

### 2.2 `map_wealth_scrape_backfill()` ノードマッピング

| データ | ノード | ID | プロパティ |
|-------|--------|-----|-----------|
| 記事 | Source | `generate_source_id(url)` | `source_type="blog"`, `domain` |
| テーマ | Topic | `generate_topic_id(name_en, "wealth-management")` | `category="wealth-management"` |
| ドメイン | Entity | `generate_entity_id(domain, "domain")` | `entity_type="domain"` |

リレーション:
- `tagged`: Source → Topic（タイトル vs テーマ `keywords_en` でマッチング）

キーワードマッチロジック:
```python
title_lower = article["title"].lower()
for theme_key, theme in themes.items():
    if any(kw.lower() in title_lower for kw in theme["keywords_en"]):
        rels["tagged"].append({"from_id": source_id, "to_id": topic_id})
```

### 2.3 `map_wealth_scrape_incremental()` ノードマッピング

`map_asset_management()` パターンに準拠:
- Source: `generate_source_id(url)`
- Topic: テーマ名からハッシュ
- Claim: `generate_claim_id(summary)`
- Relations: `tagged` (Source→Topic), `source_claim` (Source→Claim)

## Phase 3: topic-discovery マッパー

**neo4j-mapping.md に完全準拠。文字列ベース ID を使用（UUID5 ではない）。**

### 3.1 ノードマッピング

| データ | ノード | ID | プロパティ |
|-------|--------|-----|-----------|
| セッション | Source | `{session_id}` 直接 | `source_type="original"`, `command_source="topic-discovery"` |
| カテゴリ | Topic | `content:{category_key}` | `category="content_planning"`, `topic_key={name}::content_planning` |
| 提案 | Claim | `ts:{session_id}:rank{rank}` | `claim_type="recommendation"`, scores, magnitude |
| 銘柄 | Entity | `symbol:{ticker}` | `entity_type` = `^` → "index", else "stock" |
| トレンド | Fact | `trend:{session_id}:{i}:{j}` | `fact_type="event"`, `no_search` 時スキップ |

### 3.2 magnitude 判定

```python
def _magnitude_from_score(total: int) -> str:
    if total >= 40: return "strong"
    if total >= 30: return "moderate"
    return "slight"
```

### 3.3 カテゴリ定数

```python
TOPIC_DISCOVERY_CATEGORIES = {
    "market_report": "マーケットレポート",
    "stock_analysis": "個別株分析",
    "macro_economy": "マクロ経済",
    "asset_management": "資産形成",
    "side_business": "副業・収益化",
    "quant_analysis": "クオンツ分析",
    "investment_education": "投資教育",
}
```

### 3.4 リレーション

| キー | From → To |
|------|-----------|
| `tagged` | Source → Topic, Claim → Topic |
| `source_claim` | Source → Claim |
| `claim_entity` | Claim → Entity |
| `source_fact` | Source → Fact |

## Phase 4: article-neo4j スキーマ

`docker/article-neo4j/init/01-constraints-indexes.cypher` に追加:

```cypher
CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE;
CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.name);
CREATE INDEX author_type IF NOT EXISTS FOR (a:Author) ON (a.author_type);
```

## Phase 5: save-to-article-graph スキル

`.claude/skills/save-to-article-graph/SKILL.md` 新規作成。

処理フロー:
1. `uv run python scripts/emit_graph_queue.py --command {command} --input {input}`
2. `NEO4J_URI=bolt://localhost:7689 /save-to-graph --source {command}`

パラメータ: `--command`, `--input`, `--dry-run`, `--keep`

## Phase 6: テスト

### ヘルパーデータ生成関数

- `_wealth_scrape_backfill_data()`: ドメイン記事 + テーマ設定
- `_wealth_scrape_incremental_data()`: WealthScrapeSession 形式
- `_topic_discovery_data()`: topic-suggestions セッション JSON

### テストクラス

```
TestMapWealthScrapeBackfill (6テスト)
  - test_正常系_記事からSourceノード生成
  - test_正常系_テーマからTopicノード生成
  - test_正常系_ドメインからEntityノード生成
  - test_正常系_キーワードマッチでtaggedリレーション生成
  - test_エッジケース_キーワード不一致でtagged未生成
  - test_エッジケース_空URL記事スキップ

TestMapWealthScrapeIncremental (2テスト)
  - test_正常系_テーマ記事からSource_Topic_Claim生成
  - test_正常系_source_claimリレーション生成

TestMapTopicDiscovery (8テスト)
  - test_正常系_セッションからSourceノード生成
  - test_正常系_カテゴリからTopicノード生成
  - test_正常系_提案からClaimノード生成
  - test_正常系_推奨銘柄からEntityノード生成
  - test_正常系_トレンドからFactノード生成
  - test_正常系_全リレーション正しく生成
  - test_topic_discovery_IDが文字列ベースであること
  - test_エッジケース_no_searchでFact未生成

TestScanWealthDirectory (3テスト)
TestParseYamlFrontmatter (3テスト)
```

## 再利用する既存コード

| 関数 | パス | 用途 |
|------|------|------|
| `_make_source()` | `emit_graph_queue.py:239` | Source dict 生成 |
| `_mapped_result()` | `emit_graph_queue.py:269` | マッパー出力標準化 |
| `_empty_rels()` | `emit_graph_queue.py:974` | リレーション初期化（拡張後） |
| `_extend_rels()` | `emit_graph_queue.py:957` | リレーションマージ |
| `generate_source_id()` | `pdf_pipeline/services/id_generator.py` | URL → Source ID |
| `generate_entity_id()` | 同上 | Entity ID |
| `generate_claim_id()` | 同上 | Claim ID（SHA-256[:32]） |
| `generate_fact_id()` | 同上 | Fact ID（SHA-256[:32]） |
| `generate_topic_id()` | `emit_graph_queue.py:129` | Topic ID（UUID5） |
| `map_asset_management()` | `emit_graph_queue.py:465` | テーマ→Topic パターン参照 |

## 実装順序（Wave グルーピング）

### Wave A: 基盤（並列実行可能）
- A-1: `_empty_rels()` に `tagged` 追加
- A-2: `_parse_yaml_frontmatter()` 新規
- A-3: article-neo4j スキーマに Author 追加
- A-4: テストヘルパーデータ生成関数

### Wave B: マッパー（A に依存）
- B-1: `_scan_wealth_directory()` + `_load_and_parse()` 拡張 + `run()` list 対応
- B-2: `map_wealth_scrape()` (backfill + incremental)
- B-3: `map_topic_discovery()`

### Wave C: テスト・スキル（B に依存）
- C-1: wealth-scrape テスト
- C-2: topic-discovery テスト
- C-3: save-to-article-graph SKILL.md

### Wave D: 検証
- D-1: E2E dry-run 検証

## 検証手順

```bash
# 1. topic-discovery emit
uv run python scripts/emit_graph_queue.py --command topic-discovery \
  --input .tmp/topic-suggestions/2026-03-16_1800.json

# 2. wealth-scrape backfill emit
uv run python scripts/emit_graph_queue.py --command wealth-scrape \
  --input data/scraped/wealth/

# 3. dry-run save
NEO4J_URI=bolt://localhost:7689 NEO4J_PASSWORD=gomasuke \
  /save-to-graph --source topic-discovery --dry-run

# 4. テスト
make test

# 5. Neo4j Browser で確認 (http://localhost:7476)
```
