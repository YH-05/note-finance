# Neo4j書き込みパイプライン一本化計画

## Context

research-neo4jのFact 310件を監査した結果、リレーション欠落が深刻（ABOUT 18%欠落、TAGGED 43%欠落、EXTRACTED_FROM 35%欠落）。

**根本原因**: 正式な2段パイプライン（`emit_graph_queue.py` → `save-to-graph`）が存在しリレーションも正しく作成される設計だが、**アドホックなCypher直書き**（`research-write_neo4j_cypher`を直接呼ぶ）がパイプラインをバイパスし、リレーション付与が漏れている。

| バッチ | 件数 | 経路 | 欠落 |
|--------|------|------|------|
| 3/16 ISATデータ | 80件 | Cypher直書き | ABOUT 45件、TAGGED 80件 |
| 3/18 ASEAN比較 | 108件 | Cypher直書き | EXTRACTED_FROM 73件 |
| 3/19 インドネシア政経 | 35件 | Cypher直書き→事後修正 | 初回全欠落 |

**対策**: アドホック調査データ用の`web-research`コマンドを`emit_graph_queue.py`に追加し、全投入を正式パイプライン経由に統一する。直書き禁止ルールを制定する。

---

## 実装ステップ

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

## 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scripts/emit_graph_queue.py` | `map_web_research` 関数追加 + COMMAND_MAPPERS登録 |
| `tests/scripts/test_emit_graph_queue.py` | `TestMapWebResearch` テストクラス追加 |
| `.claude/rules/neo4j-write-rules.md` | **新規作成**: 直書き禁止ルール |
| `.claude/rules/README.md` | エントリ追加 |

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
2. **統合テスト**: サンプル入力JSONを作成 → `python scripts/emit_graph_queue.py --command web-research --input sample.json` → 出力JSONの構造検証（5種リレーション存在確認）
3. **E2Eテスト**: 生成された graph-queue JSON を `/save-to-graph` で research-neo4j に投入 → `MATCH (f:Fact)-[:ABOUT]->(e:Entity)` 等でリレーション存在を確認
4. **回帰テスト**: `make check-all`

---

## スコープ外

- 既存欠落データ（3/16, 3/18バッチ）の修復 — 別タスクで対応
- `emit-research-queue` スキル作成 — `map_web_research` の安定後に検討
- 既存リサーチスキルへのKG出力フェーズ追加 — 同上
