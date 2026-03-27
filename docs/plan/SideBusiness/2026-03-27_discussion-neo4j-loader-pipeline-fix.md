# 議論メモ: neo4j_loader.py パイプライン設計修正

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

`/investment-research telcomセクターに関連した技術トレンド` 実行時に、graph-queue v3.0 データの Neo4j 投入で複数のバグが発覚。ノードは投入できるがリレーションが全件サイレントスキップされる致命的な問題と、Entity/Topic の MERGE キー不一致によるUNIQUE制約違反が発生していた。

## 議論のサマリー

### 発覚した根本的バグ（3件）

1. **entity_id/topic_id での MERGE**: パイプライン間で異なるUUIDが生成され、entity_key UNIQUE制約違反が発生（Ericsson entity で実際に発生）
2. **v3.0 from_id/to_id 未対応**: `_merge_relation` が `rel.get("fact_id")` 等で取得 → 全てNone → 325件/ファイルのリレーションがサイレントスキップ
3. **PROVIDES vs STATES_FACT 混在**: neo4j_loader.py は `PROVIDES` を使用、save-to-research-graph スキルは `STATES_FACT`/`MAKES_CLAIM` を使用 → DB内で同義の異なるリレーション名が共存

### 設計上の問題（3件）

4. **extracted_from_fact の Chunk 未対応**: 宛先が Source にハードコード → chunks 付きキューで将来サイレントスキップ
5. **Neo4j ドライバー再生成**: セクションごとに ~13回/ファイルの接続確立（パフォーマンス浪費）
6. **--file フラグ欠落**: ingest_graph_queue.py で単一ファイル投入ができない

## 決定事項

1. **entity_key/topic_key MERGE**: Entity/Topic は entity_key/topic_key（ビジネスキー）で MERGE。entity_id/topic_id は ON CREATE のみ設定し既存ノードの id を上書きしない
2. **v3.0 from_id/to_id 対応**: `_merge_relation` で `from_id`/`to_id` を優先、フォールバックでドメイン固有キー名。`id_to_key` 解決マップで entity_id → entity_key を変換
3. **STATES_FACT/MAKES_CLAIM 統一**: Source→Fact は `STATES_FACT`、Source→Claim は `MAKES_CLAIM`。既存 PROVIDES 18件も移行済み
4. **extracted_from 動的切替**: `_resolve_rel_endpoints()` で chunks 有無に応じて宛先を Source/Chunk に動的決定
5. **ドライバー単一化**: `ingest_to_neo4j` 内で1回だけ生成、`try/finally` で確実に close
6. **--file フラグ追加**: `process_single_file()` + `--file`/`--keep` 引数で単一ファイル投入に対応

## 修正ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/data_pipeline/neo4j_loader.py` | `_NODE_KEY_MAP`, `_NODE_ID_ON_CREATE`, `_merge_node`, `_REL_ENDPOINTS`, `_resolve_rel_endpoints`, `_merge_relation`, `ingest_to_neo4j` |
| `scripts/ingest_graph_queue.py` | `process_single_file()`, `--file`/`--keep` 引数追加 |

## アクションアイテム（第1セッション）

- [x] neo4j_loader.py + ingest_graph_queue.py の変更をコミット・PR作成 (優先度: 高) → コミット済み
- [ ] 過去web-researchファイル(~17件)のリレーション再投入 (優先度: 高)
- [ ] テレコムリサーチ残存ギャップ4件を次回リサーチで解消 (優先度: 中)

## テレコムリサーチ成果（副産物）

- リサーチノート: `.tmp/investment-research/telecom-tech-trends_20260327-1500.md`
- research-neo4j 投入: 73 nodes, 325 relations
- 主要トピック: AI×RAN自動化、Open RAN、6G標準化、NTN/衛星、テレコムCapex
- ブル/ベア各5点、ニュートラル3点の論点整理済み

---

## 第2セッション: 追加4問題修正（コミット `096f6b8`）

### 新たに発見・修正した問題

#### 問題A: Fact→Topic TAGGED が Source→Topic と混在
- `emit_research_queue.py` の `map_web_research()` が `tagged_rels`（Source→Topic）と `fact_tagged`（Fact→Topic）を混在させて `relations.tagged` に出力していた
- `neo4j_loader.py` の `_REL_ENDPOINTS["tagged"]` は Source→Topic のみ対応 → Fact→Topic が全件サイレントスキップ
- **修正（方針A）**: `tagged` と `tagged_fact` を別セクションに分離
  - emit: `"tagged_fact": fact_tagged` を独立キーで出力
  - loader: `_REL_ENDPOINTS["tagged_fact"] = ("fact_id", "Fact", "topic_key", "Topic", "TAGGED")` 追加

#### 問題B: リレーション投入検証がなかった
- `rel_count` がループ回数を数えるだけで、Neo4j への実際の MERGE 成功数を計測していなかった
- **修正**:
  - `_merge_relation()` の戻り値を `int`（`summary.counters.relationships_created`）に変更
  - `ingest_to_neo4j()` に `rel_verification: dict[str, tuple[int, int]]` を追加（期待数 vs 実創数）
  - `ingest_graph_queue.py` に `_verify_ingestion()` 追加: `created == 0 && expected > 0` で ERROR 判定

#### スキル文書更新
- `.claude/skills/save-to-research-graph/SKILL.md` に v3.0 差異セクションを追加
  - Chunk 廃止、tagged_fact 追加、entity_key/topic_key MERGE を明記

### 第2セッションの決定事項

7. **tagged_fact は別セクション（方針A）**: コードとデータ形式が1対1で見通しが良い
8. **検証閾値10%**: 全件 created=0 のみ ERROR、既存 MERGE による created < expected は正常
9. **スキル文書も同期更新**: コード変更時は SKILL.md も同時に更新する

### アクションアイテム（第2セッション）

- [ ] web-research 再投入テストで修正を検証する (優先度: 高)
- [ ] 他パイプライン（finance-news-workflow等）に tagged_fact 分離が必要か確認 (優先度: 中)
- [ ] _verify_ingestion 10%閾値が実運用で適切か数回後に見直す (優先度: 低)

### 変更ファイル（コミット `096f6b8`）

| ファイル | 変更内容 |
|---------|---------|
| `src/data_pipeline/neo4j_loader.py` | tagged_fact追加、_merge_relation戻り値int化、rel_verification追加 |
| `scripts/ingest_graph_queue.py` | _verify_ingestion()追加、_VERIFICATION_ERROR_THRESHOLD定義 |
| `scripts/emit_research_queue.py` | tagged_fact分離、tagged_relsからfact_taggedを除外 |
| `.claude/skills/save-to-research-graph/SKILL.md` | v3.0差異セクション追加、tagged_fact文書化 |
