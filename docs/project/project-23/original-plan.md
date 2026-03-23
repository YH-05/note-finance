# creator-enrichment Python オーケストレーター実装計画

## Context

creator-enrichment は現在プロンプトベースの Claude Code スキルとして実装されている。1つの会話内で全サイクルを実行するため、コンテキスト膨張・LLMドリフトにより `--until` で指定した終了時刻前に停止してしまう問題がある。

**目的**: Python スクリプトで時間管理とサイクルループを**決定的に**制御し、指定時刻まで絶対に停止しないオーケストレーターを実装する。LLM 依存部分（分類・Entity抽出）のみ Anthropic API を直接呼び出し、それ以外は全て Python で完結させる。

## 設計方針

| フェーズ | 現状（スキル） | 新実装（Python） |
|---------|--------------|-----------------|
| 時間管理 | LLM が MCP time ツールで確認 | `datetime.now()` で決定的に制御 |
| Gap Analysis | MCP Neo4j read | `neo4j` Python driver 直接 |
| 検索 | MCP Tavily/Reddit/WebFetch | `httpx` で Tavily REST API 直接 |
| 分類・Entity抽出 | LLM がプロンプト内で処理 | `anthropic` SDK で API 呼び出し |
| Entity リンキング | `entity_linker.py` を subprocess | `entity_linker.resolve_all()` を import |
| Graph Queue 生成 | `emit_creator_queue_v2.py` を subprocess | `map_creator_enrichment_v2()` を import |
| Neo4j 投入 | MCP creator-write Cypher | `neo4j` driver で MERGE Cypher 直接実行 |
| Cross-Entity | LLM がプロンプト内で処理 | `anthropic` SDK で API 呼び出し |

## ファイル構成

```
scripts/
  creator_enrichment_runner.py          # CLI エントリポイント（薄いラッパー）

src/creator_enrichment/
  __init__.py
  orchestrator.py                       # メインループ: 時刻チェック、サイクル分離、エラー隔離
  config.py                             # 設定読み込み、CLI引数、dataclass
  types.py                              # 共有 dataclass / TypedDict
  session_log.py                        # Markdown セッションログ
  phases/
    __init__.py
    gap_analysis.py                     # Phase 1: Neo4j Cypher Q1-Q6
    search.py                           # Phase 2: Tavily httpx クライアント
    extract.py                          # Phase 3: Anthropic API 分類・Entity/Concept抽出
    pipeline.py                         # Phase 4: entity_linker + emit_queue + neo4j_writer
    cross_entity.py                     # Phase 4.5: 共起検出 + LLM リレーション判定
  neo4j_writer.py                       # MERGE Cypher パターン（guide-v2.md 移植）

tests/unit/test_creator_enrichment/
  test_orchestrator.py
  test_gap_analysis.py
  test_search.py
  test_extract.py
  test_neo4j_writer.py
  test_pipeline.py
```

## 実装詳細

### Step 1: types.py + config.py

**types.py** — 全フェーズ共通のデータ構造:
```python
@dataclass
class RawItem:             # Phase 2 検索結果
@dataclass
class CycleData:           # Phase 3 抽出結果（emit_creator_queue_v2 入力形式）
@dataclass
class GapAnalysisResult:   # Phase 1 ギャップ分析結果
@dataclass
class CycleReport:         # Phase 5 サイクルレポート
@dataclass
class IngestResult:        # Phase 4.2 投入結果
```

**config.py** — CLI引数パース + `data/config/creator-enrichment-config.json` 読み込み:
- `--until HH:MM`（必須）
- `--genre career|beauty-romance|spiritual`（任意）
- `--dry-run`（任意）
- `--max-cycles`（任意、デフォルト無制限）

### Step 2: gap_analysis.py（Phase 1）

`entity_linker.Neo4jClient` を再利用（`load_instance_config("creator")` で接続）。
gap-analysis-queries-v2.md の Q1-Q6 をメソッドとして実装。

```python
class GapAnalyzer:
    def __init__(self, neo4j_client: Neo4jClient): ...
    def analyze(self, prev_genre: str | None, genre_filter: str | None) -> GapAnalysisResult: ...
```

- ジャンルローテーション: `priority_score = 1.0 / (content_count + 1)` + ダンピング
- 低カバレッジ Concept/ConceptCategory の抽出

**参照ファイル**:
- `.claude/skills/creator-enrichment/references/gap-analysis-queries-v2.md` — Q1-Q6 の Cypher
- `scripts/entity_linker.py:130` — `load_instance_config()`
- `scripts/entity_linker.py:234` — `Neo4jClient` クラス

### Step 3: search.py（Phase 2）

Tavily REST API を `httpx.Client` で直接呼び出し。Reddit は初期実装では省略。

```python
class TavilySearcher:
    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str): ...
    def search(self, query: str, max_results: int = 5) -> list[RawItem]: ...
    def extract(self, urls: list[str]) -> list[RawItem]: ...
```

- `tenacity.retry` で指数バックオフ（max 3回）
- ジャンル別クエリテンプレートを config から読み込み
- `{topic}` = Gap Analysis Q3 の低カバレッジ Concept、`{year}` = 現在年
- 1サイクルあたり EN 3件 + JP 3件（max 6 API コール）

**参照ファイル**:
- `data/config/creator-enrichment-config.json` — ジャンル別検索テンプレート
- `.claude/skills/creator-enrichment/references/genre-config.md` — テンプレート詳細

### Step 4: extract.py（Phase 3）

Anthropic API でコンテンツ分類 + Entity/Concept 抽出。

```python
class ContentExtractor:
    def __init__(self, client: anthropic.Anthropic): ...
    def extract_single(self, item: RawItem, genre: str) -> dict: ...
    def extract_batch(self, items: list[RawItem], genre: str) -> CycleData: ...
```

- モデル: `claude-haiku-4-5-20251001`（コスト効率）
- プロンプト: `entity-extraction-prompt-v2.md` をテンプレートとして使用
- 各 RawItem に対して個別に API 呼び出し（1-2秒間隔）
- JSON パース + バリデーション
- 出力: `emit_creator_queue_v2.py` の入力形式に合わせた dict

**参照ファイル**:
- `.claude/skills/creator-enrichment/references/entity-extraction-prompt-v2.md` — プロンプト
- `scripts/restructure_claims.py` — Anthropic API 呼び出しパターン

### Step 5: neo4j_writer.py

`guide-v2.md` の MERGE Cypher パターンを Python に移植。

```python
class CreatorGraphWriter:
    def __init__(self, driver: neo4j.Driver): ...
    def ingest(self, queue_doc: dict) -> IngestResult: ...
    def validate(self, cycle_start: str) -> dict: ...
```

UNWIND バッチ MERGE を依存関係順に実行:
1. Genre → ConceptCategory → Domain → Source → Concept → Entity → Fact/Tip/Story
2. IS_A → FROM_DOMAIN → ABOUT → MENTIONS → IN_GENRE → FROM_SOURCE → SERVES_AS → concept rels

**参照ファイル**:
- `.claude/skills/save-to-creator-graph/guide-v2.md` — 全 MERGE パターン
- `scripts/neo4j_utils.py` — `create_driver()`

### Step 6: pipeline.py（Phase 4）

3つの既存コンポーネントをライブラリとして import し接続:

```python
def run_pipeline(cycle_data: CycleData, neo4j_client, neo4j_driver) -> IngestResult:
    # 4.0 Entity Linking（in-process import）
    from entity_linker import resolve_all
    resolved = resolve_all(neo4j_client, cycle_data.to_dict(), use_embedding=False)

    # 4.1 Graph Queue 生成（in-process import）
    from emit_creator_queue_v2 import map_creator_enrichment_v2
    queue_doc = map_creator_enrichment_v2(resolved)

    # 4.2 Neo4j MERGE 投入
    writer = CreatorGraphWriter(neo4j_driver)
    return writer.ingest(queue_doc)
```

- 各ステップの中間 JSON を `.tmp/` に保存（リカバリポイント）
- `--dry-run` 時は Step 4.2 をスキップ

**参照ファイル**:
- `scripts/entity_linker.py:653` — `resolve_all()`
- `scripts/emit_creator_queue_v2.py:168` — `map_creator_enrichment_v2()`

### Step 7: cross_entity.py（Phase 4.5）

3サイクルに1回実行。共起候補の Neo4j クエリ + Anthropic API で関係判定。

- SKILL.md の共起候補クエリ（co_occurrence >= 2）+ 同一タイプ未接続ペア
- Anthropic API で最大25ペアを一括判定
- SKIP 以外の結果を Neo4j driver で MERGE

**参照ファイル**:
- `.claude/skills/creator-enrichment/SKILL.md:329-403` — 共起クエリ + LLM プロンプト

### Step 8: orchestrator.py

```python
class CreatorEnrichmentOrchestrator:
    def run(self):
        self._init_connections()    # Neo4j + Anthropic + Tavily
        try:
            while self._time_remaining():
                try:
                    self._run_cycle()
                    self.consecutive_errors = 0
                except CycleError as e:
                    self.consecutive_errors += 1
                    self.session_log.record_error(self.cycle_count, e)
                    if self.consecutive_errors >= 5:
                        break  # 5回連続エラーで停止
                finally:
                    self._enforce_min_interval()  # 30秒間隔保証
        finally:
            self._finalize()
```

- `_time_remaining()`: `datetime.now(ZoneInfo("Asia/Tokyo")) < until_time`
- `_run_cycle()`: Phase 1 → 2 → 3 → 4 → (4.5) → 5
- サイクルエラーは隔離（try/except）、次サイクルに影響させない
- 空サイクル3回連続 → 停止
- エラー5回連続 → 停止

### Step 9: session_log.py

SKILL.md のログ形式をそのまま踏襲（`.tmp/creator-enrichment-{timestamp}.log.md`）。

### Step 10: creator_enrichment_runner.py

```python
#!/usr/bin/env python3
"""Creator enrichment continuous runner."""
from creator_enrichment.config import parse_args, load_config
from creator_enrichment.orchestrator import CreatorEnrichmentOrchestrator

def main():
    args = parse_args()
    config = load_config(args)
    orchestrator = CreatorEnrichmentOrchestrator(config)
    orchestrator.run()

if __name__ == "__main__":
    main()
```

実行: `uv run python scripts/creator_enrichment_runner.py --until 23:30`

### Step 11: pyproject.toml 更新

`[tool.hatch.build.targets.wheel]` の packages に `src/creator_enrichment` を追加。

## エラーハンドリング

| レベル | 戦略 | 条件 |
|--------|------|------|
| サイクル | 完全隔離 | try/except で次サイクルへ。5回連続エラーで停止 |
| API コール | tenacity リトライ | max 3回、指数バックオフ（2s→4s→8s） |
| Neo4j | 接続チェック | サイクル開始時に接続確認。失敗なら1回再接続試行 |
| 致命的 | 即停止 | 初期接続失敗、API キー未設定、`--until` パース失敗 |

## 既存スキル/コマンドとの関係

- `.claude/skills/creator-enrichment/SKILL.md` — **変更なし**（ad-hoc 用として残す）
- `.claude/commands/creator-enrichment.md` — **変更なし**
- Python オーケストレーターは長時間連続実行の「本番パス」として共存

## 検証方法

1. **ユニットテスト**: 各 Phase のモック付きテスト（`make test`）
2. **ドライラン**: `--dry-run --max-cycles 2` で検索+分類のみ確認
3. **短時間テスト**: `--until {5分後}` で 1-2 サイクル実行を確認
4. **Neo4j 検証**: 投入後に Q1 クエリでノード数増加を確認
5. **セッションログ確認**: `.tmp/creator-enrichment-*.log.md` の内容検証

## 実装順序

| Step | 内容 | 依存 |
|------|------|------|
| 1 | `types.py` + `config.py` | なし |
| 2 | `gap_analysis.py` + テスト | Step 1 |
| 3 | `search.py` + テスト | Step 1 |
| 4 | `extract.py` + テスト | Step 1 |
| 5 | `neo4j_writer.py` + テスト | Step 1 |
| 6 | `pipeline.py` + テスト | Step 2-5 |
| 7 | `cross_entity.py` + テスト | Step 1 |
| 8 | `orchestrator.py` + テスト | Step 2-7 |
| 9 | `session_log.py` | Step 1 |
| 10 | `creator_enrichment_runner.py` | Step 8-9 |
| 11 | `pyproject.toml` 更新 | Step 10 |

## 重要な参照ファイル

| ファイル | 用途 |
|---------|------|
| `scripts/entity_linker.py` | `resolve_all()`, `Neo4jClient`, `load_instance_config()` をインポート |
| `scripts/emit_creator_queue_v2.py` | `map_creator_enrichment_v2()` をインポート |
| `scripts/neo4j_utils.py` | `create_driver()` パターン参照 |
| `scripts/restructure_claims.py` | Anthropic API + バッチ処理 + チェックポイントパターン参照 |
| `.claude/skills/save-to-creator-graph/guide-v2.md` | 10ノード+11リレーション MERGE Cypher |
| `.claude/skills/creator-enrichment/references/entity-extraction-prompt-v2.md` | Phase 3 プロンプト |
| `.claude/skills/creator-enrichment/references/gap-analysis-queries-v2.md` | Phase 1 Cypher Q1-Q6 |
| `data/config/creator-enrichment-config.json` | ジャンル別検索テンプレート |
| `data/config/neo4j-instances/creator.yaml` | Neo4j 接続設定 |
