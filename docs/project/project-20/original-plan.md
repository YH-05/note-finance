# Neo4j書き込みパイプライン一本化計画

## Context

research-neo4jのFact 310件を監査した結果、リレーション欠落が深刻（ABOUT 18%欠落、TAGGED 43%欠落、EXTRACTED_FROM 35%欠落）。

**根本原因**: 正式な2段パイプライン（`emit_graph_queue.py` → `save-to-graph`）が存在しリレーションも正しく作成される設計だが、**アドホックなCypher直書き**（`research-write_neo4j_cypher`を直接呼ぶ）がパイプラインをバイパスし、リレーション付与が漏れている。

| バッチ | 件数 | 経路 | 欠落 |
|--------|------|------|------|
| 3/16 ISATデータ | 80件 | Cypher直書き | ABOUT 45件、TAGGED 80件 |
| 3/18 ASEAN比較 | 108件 | Cypher直書き | EXTRACTED_FROM 73件 |
| 3/19 インドネシア政経 | 35件 | Cypher直書き→事後修正 | 初回全欠落 |

**対策**: アドホック調査データ用の`web-research`コマンドを`emit_graph_queue.py`に追加し、全投入を正式パイプライン経由に統一する。直書き禁止ルールを制定する。既存欠落データの修復、スキル作成、既存リサーチスキルへのKG出力統合も含む。

---

## Phase 1: パイプライン拡張（コア実装）

### Step 1: `map_web_research` 関数を `emit_graph_queue.py` に追加

**ファイル**: `scripts/emit_graph_queue.py` (L3003、`map_topic_discovery`の直後)

Web検索・アドホック調査の結果を graph-queue JSON に変換するマッパー関数。

**入力JSONスキーマ**:
```json
{
  "session_id": "web-research-indonesia-macro-20260319",
  "research_topic": "インドネシア政治経済分析",
  "as_of_date": "2026-03-19",
  "sources": [
    {"url": "https://...", "title": "...", "source_type": "news|report|official|data|analysis",
     "authority_level": "institution|rating_agency|central_bank|sell_side|media|think_tank",
     "published_at": "2026-03-04", "category": "macro_economics"}
  ],
  "entities": [
    {"name": "Indonesia", "entity_type": "country", "description": "..."}
  ],
  "topics": [
    {"name": "Macro Environment Indonesia", "category": "macro"}
  ],
  "facts": [
    {"content": "Indonesia GDP grew 5.11%...", "fact_type": "data_point",
     "as_of_date": "2025-12-31", "about_entities": ["Indonesia"],
     "tagged_topics": ["Macro Environment Indonesia"], "source_url": "https://..."}
  ]
}
```

**生成するリレーション（5種、全必須）**:
1. `source_fact` — Source → Fact (STATES_FACT)
2. `fact_entity` — Fact → Entity (ABOUT)
3. `tagged` — Fact → Topic (TAGGED) + Source → Topic (TAGGED)
4. `extracted_from_fact` — Fact → Source (EXTRACTED_FROM)

**既存ヘルパー再利用**:
- `generate_fact_id(content)` — `src/pdf_pipeline/services/id_generator.py:L216`
- `generate_source_id(url)` — 同 `L62`
- `generate_entity_id(name, entity_type)` — 同 `L273`
- `_mapped_result()` — `emit_graph_queue.py` 内の共通出力整形
- `_empty_rels()` — リレーション累積用dict初期化

**設計の要点**:
- `about_entities` フィールドで Fact→Entity の ABOUT リレーションを明示的に指定（曖昧なマッチングではなく）
- `tagged_topics` フィールドで Fact→Topic の TAGGED リレーションを明示的に指定
- `source_url` フィールドで Fact→Source の紐付けを `url_to_source_id` マッピングで解決
- Entity/Topic は既存ノードへの MERGE を前提とし、entity_key (`name::entity_type`) を生成

### Step 2: `COMMAND_MAPPERS` に登録

**ファイル**: `scripts/emit_graph_queue.py` L3009-3019

```python
COMMAND_MAPPERS: dict[str, MapperFn] = {
    ...既存9エントリ...,
    "web-research": map_web_research,  # 追加
}
```

### Step 3: テスト追加

**ファイル**: `tests/scripts/test_emit_graph_queue.py`

```
TestMapWebResearch:
  test_正常系_基本マッピング_ソースとファクトとエンティティ
  test_正常系_全5リレーション種が生成される
  test_正常系_エンティティ重複排除
  test_正常系_ソースURL紐付け_ファクトからソースへ
  test_エッジケース_空のfacts配列
  test_エッジケース_about_entities未指定時
```

---

## Phase 2: ルール制定

### Step 4: ルールファイル作成

**ファイル**: `.claude/rules/neo4j-write-rules.md`

内容骨子:
1. **禁止**: `research-write_neo4j_cypher` でのノード/リレーション作成（例外: スキーマ操作、明示的承認のある修復）
2. **必須パイプライン**: `emit_graph_queue.py` → `/save-to-graph`
3. **`web-research` コマンド**: アドホック調査データの標準投入経路
4. **違反実績**: 3/16, 3/18, 3/19 の欠落データを記録（再発防止の証跡）
5. **読み取りは自由**: `research-read_neo4j_cypher` は制限なし
6. **チェックリスト**: 投入前に確認すべき5項目

### Step 5: `rules/README.md` 更新

`neo4j-write-rules.md` のエントリを追加。

### Step 6: 品質チェック

```bash
make check-all
```

---

## Phase 3: 既存欠落データの修復

### Step 7: 3/16バッチ（ISATデータ 80件）の修復

**対象**: ABOUT 45件欠落、TAGGED 80件全欠落

手順:
1. `research-read_neo4j_cypher` で欠落Factの `content` を読み取り、対象Entityを特定
2. 修復用の入力JSONを作成（facts[].about_entities, tagged_topics を補完）
3. `emit_graph_queue.py --command web-research` で graph-queue JSON を生成
4. `/save-to-graph` で投入（MERGE で冪等に追加リレーションのみ作成）

### Step 8: 3/18バッチ（ASEAN比較 108件）の修復

**対象**: EXTRACTED_FROM 73件欠落、TAGGED 35件欠落、ABOUT 7件欠落

手順: Step 7と同様。content からソースURLを特定し、Source ノードとの紐付けを補完。

### Step 9: 初期バッチ（epoch型 47件）の修復

**対象**: EXTRACTED_FROM 全欠落（47件）

手順: `source_context` プロパティからソース情報を抽出し、Source ノードを作成・リンク。

---

## Phase 4: スキル・統合

### Step 10: `emit-research-queue` スキル作成

**ファイル**: `.claude/skills/emit-research-queue/SKILL.md`

`emit_graph_queue.py --command web-research` のラッパースキル。

機能:
1. パラメータ: `--topic`, `--input-file`（またはインラインJSON）
2. インラインデータの場合、入力JSONを構築して `.tmp/web-research-input-{ts}.json` に書き出し
3. `python3 scripts/emit_graph_queue.py --command web-research --input {file}` を実行
4. 生成された graph-queue ファイルパスを報告
5. オプションで `/save-to-graph` にチェーンして即時投入

### Step 11: 既存リサーチスキルへのKG出力フェーズ追加

以下のスキルに「Phase N: KG Output」セクションを追加し、`emit-research-queue` の利用を案内:

| スキル | ファイル |
|--------|---------|
| investment-research | `.claude/skills/investment-research/SKILL.md` |
| macro-economic-research | `.claude/skills/macro-economic-research/SKILL.md` |
| equity-stock-research | `.claude/skills/equity-stock-research/SKILL.md` |

追加内容（各スキル末尾）:
```markdown
## KG Output（任意）

リサーチ結果をresearch-neo4jに永続化する場合:
1. `/emit-research-queue` スキルでgraph-queue JSONを生成
2. `/save-to-graph` でNeo4jに投入
```

---

## 変更対象ファイル一覧

| Phase | ファイル | 変更内容 |
|-------|---------|---------|
| 1 | `scripts/emit_graph_queue.py` | `map_web_research` 関数追加 + COMMAND_MAPPERS登録 |
| 1 | `tests/scripts/test_emit_graph_queue.py` | `TestMapWebResearch` テストクラス追加 |
| 2 | `.claude/rules/neo4j-write-rules.md` | **新規作成**: 直書き禁止ルール |
| 2 | `.claude/rules/README.md` | エントリ追加 |
| 3 | *(Neo4j直接操作)* | 既存欠落リレーションの修復（3バッチ分） |
| 4 | `.claude/skills/emit-research-queue/SKILL.md` | **新規作成**: ラッパースキル |
| 4 | `.claude/skills/investment-research/SKILL.md` | KG Outputセクション追加 |
| 4 | `.claude/skills/macro-economic-research/SKILL.md` | KG Outputセクション追加 |
| 4 | `.claude/skills/equity-stock-research/SKILL.md` | KG Outputセクション追加 |

## 参照ファイル（変更なし）

| ファイル | 参照理由 |
|---------|---------|
| `src/pdf_pipeline/services/id_generator.py` | ID生成関数の再利用 |
| `.claude/skills/save-to-graph/SKILL.md` | 4フェーズ投入パイプラインの仕様 |
| `.claude/skills/save-to-graph/guide.md` | Cypherテンプレート・リレーション仕様 |
| `data/config/knowledge-graph-schema.yaml` | KGスキーマ定義（SSOT） |

---

## 検証方法

1. **ユニットテスト**: `uv run pytest tests/scripts/test_emit_graph_queue.py -v -k web_research`
2. **統合テスト**: サンプル入力JSON → `python scripts/emit_graph_queue.py --command web-research --input sample.json` → 出力JSONの5種リレーション存在確認
3. **E2Eテスト**: graph-queue JSON → `/save-to-graph` → `MATCH (f:Fact)-[:ABOUT]->(e:Entity)` 等でリレーション検証
4. **修復検証**: 修復後に品質監査クエリを再実行し、ABOUT/TAGGED/EXTRACTED_FROM の充足率が改善したことを確認
5. **回帰テスト**: `make check-all`
