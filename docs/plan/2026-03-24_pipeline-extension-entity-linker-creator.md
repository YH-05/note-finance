# パイプライン拡張: Entity Linker + creator-neo4j 対応 + ベクトル類似度

## Context

run_pipeline() が research-neo4j 向けに一気通貫で動作するようになったが、creator-neo4j には未対応。Entity Linker も research-neo4j では使われていない。両インスタンスのパイプラインを統一的に扱えるよう拡張する。

## 実装順序

### Step 1: pyproject.toml に embedding optional dependency 追加

**ファイル**: `pyproject.toml`

```toml
[project.optional-dependencies]
embedding = ["sentence-transformers>=3.0.0"]
```

entity_linker.py の第4層は既に実装済み（`_resolve_by_embedding_*`）で、import 失敗時は graceful skip。

### Step 2: neo4j_loader.py に creator-neo4j 投入追加

**ファイル**: `src/data_pipeline/neo4j_loader.py`

- `_get_creator_driver()` 追加（bolt://localhost:7689、`NEO4J_CREATOR_URI` 環境変数）
- `ingest_to_creator_neo4j(queue_data, dry_run)` 追加
- 既存の `CreatorGraphWriter`（`creator_enrichment/neo4j_writer.py`）をアダプター経由で再利用

```python
def ingest_to_creator_neo4j(queue_data, *, dry_run=False):
    if dry_run:
        return _count_creator_nodes_rels(queue_data)
    driver = _get_creator_driver()
    try:
        from creator_enrichment.neo4j_writer import CreatorGraphWriter
        writer = CreatorGraphWriter(driver)
        result = writer.ingest(queue_data)
        return {"nodes": result["nodes_created"], "relations": result["relations_created"]}
    finally:
        driver.close()
```

理由: `CreatorGraphWriter` は 10ノード+11リレーションの UNWIND バッチ MERGE を既に実装済み。再実装は不要。

### Step 3: research-neo4j に Full-Text Index 作成 + pipeline.py に Entity Linker 統合

**ファイル**:
- `src/data_pipeline/pipeline.py` — Layer 3.5 として entity_linker 挿入
- research-neo4j に Full-Text Index 3本を作成（Cypher スキーマ操作）

```cypher
CREATE FULLTEXT INDEX research_entity_fulltext IF NOT EXISTS
  FOR (n:Entity) ON EACH [n.name, n.entity_key];
CREATE FULLTEXT INDEX research_alias_fulltext IF NOT EXISTS
  FOR (n:Alias) ON EACH [n.name, n.value];
```

pipeline.py に `link_entities: bool = False` パラメータ追加:

```python
# Layer 3.5: Entity Linking (optional)
if link_entities:
    from scripts.entity_linker import resolve_all, Neo4jClient, load_instance_config
    config = load_instance_config(target)
    client = Neo4jClient(config["bolt_uri"], config["user"], config["password"])
    resolved = resolve_all(client, emit_data, use_embedding=False, use_v3=True)
    client.close()
```

**既存コード変更なし**: `entity_linker.py` は既に `--instance` パラメータ対応で汎用設計。

### Step 4: run_pipeline(target="creator") 実装

**ファイル**:
- `src/data_pipeline/pipeline.py` — `target` パラメータ追加、Layer 3/4 分岐
- `src/data_pipeline/structurer/emitter.py` — `run_emit_creator_queue()` 追加

Layer 0-2 は共通。Layer 3 以降で分岐:

```
target="research":
  Layer 3: LlmExtractor → StructuredOutput → emit_research_queue.py
  Layer 4: neo4j_loader.ingest_to_neo4j()

target="creator":
  Layer 3: ContentExtractor → CycleData → emit_creator_queue_v2.py
  Layer 3.5: entity_linker.resolve_all()
  Layer 4: neo4j_loader.ingest_to_creator_neo4j()
```

`run_pipeline()` シグネチャ:

```python
def run_pipeline(
    *,
    target: Literal["research", "creator"] = "research",
    source_ids: list[str] | None = None,
    method: str | list[str] = "rss",
    extract: bool = True,
    max_items_per_feed: int = 10,
    ingest_neo4j: bool = True,
    dry_run: bool = False,
    genre: str = "career",        # creator のみ
    link_entities: bool = False,   # entity linking 有効化
) -> PipelineResult:
```

**再利用する既存コード**:
- `creator_enrichment.phases.extract.ContentExtractor` — creator LLM 抽出
- `creator_enrichment.llm_client.SdkLLMClient` — LLM クライアント
- `creator_enrichment.neo4j_writer.CreatorGraphWriter` — Neo4j 投入
- `scripts.entity_linker.resolve_all` — Entity Linker
- `scripts.emit_creator_queue_v2.map_creator_enrichment_v2` — graph-queue 生成

## テスト

### 新規テストファイル

| ファイル | 内容 |
|---|---|
| `tests/unit/test_data_pipeline/test_neo4j_loader_creator.py` | creator 投入の dry-run テスト |
| `tests/unit/test_data_pipeline/test_pipeline_creator.py` | target="creator" のモックテスト |

### 既存テスト

169 テスト（data_pipeline）+ 7049 テスト（全体）が壊れないことを確認。

## 検証手順

```bash
# Step 1: 依存追加
uv sync --all-extras

# Step 2: neo4j_loader テスト
uv run pytest tests/unit/test_data_pipeline/test_neo4j_loader_creator.py -v

# Step 3: Full-Text Index 作成（Neo4j起動時）
# mcp__neo4j-research__research-write_neo4j_cypher で実行

# Step 4: パイプライン dry-run テスト
uv run python -c "
from data_pipeline.pipeline import run_pipeline
# research（既存動作確認）
r = run_pipeline(target='research', source_ids=['jp-trade'], extract=False, dry_run=True, max_items_per_feed=2)
print(f'research: {r.items_collected} collected, {r.facts_total} facts')

# creator（新規）
c = run_pipeline(target='creator', source_ids=['wealth-blogs-scrape'], extract=False, dry_run=True, max_items_per_feed=2)
print(f'creator: {c.items_collected} collected')
"

# 全テスト
uv run pytest tests/unit/test_data_pipeline/ -v
```
