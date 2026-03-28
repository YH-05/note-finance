# 議論メモ: KG投入パイプライン不整合の特定と修正

**日付**: 2026-03-28
**参加**: ユーザー + AI
**前提**: disc-2026-03-28-kg-quality-repair（KG品質チェック＋決定論的修復）の続き

## 背景・コンテキスト

KG品質チェックで発覚したconsistency/completeness/structuralの低スコアについて、
DB上の事後修復だけでなく、データ投入パイプライン自体に根本原因がないかを調査した。
結果、emit_research_queue.py・kg_quality_metrics.py・スキルドキュメントに6件の不整合を発見し修正。

## 議論のサマリー

### 発見した不整合

1. **fact_type空文字列投入**（emit_research_queue.py:1882）
   - `fact.get("fact_type", "")` で空文字がそのまま投入されていた
   - completenessスコア低下＋IS_FACT_TYPEリレーション欠落の根本原因

2. **about_entities型不一致**（emit_research_queue.py:1807-1836）
   - `_resolve_entity_rels`が`list[str]`のみ対応、SKILL.mdは`list[dict]`を指示
   - chunk経由コマンド（pdf-extraction等）でdict形式が来るとサイレントに失敗
   - さらにabout_entitiesが空のときフォールバックなし → RELATES_TO欠落1,054件の原因

3. **ENTITY_TYPE_META vs ALLOWED_ENTITY_TYPES不一致**
   - emit: 14種（concept, regulation含む）
   - kg_quality: 23種（concept, regulation含まない）
   - 正規タイプで投入しても品質チェックで違反扱い

4. **kg-quality-check Source Groundingクエリバグ**
   - `(f)<-[:STATES_FACT|MAKES_CLAIM]-(c:Chunk)` はリレーション方向＋ノード型が誤り
   - LLM-as-Judge の Source Grounding軸が常に0.0

5. **save-to-research-graph SKILL.md v3.0誤記述**
   - 「Chunk廃止、EXTRACTED_FROM→Source」と記載されていたが実際はChunk維持が正しい
   - PDFソースは最大21チャンク（section_title付き）で、Chunkが出典箇所の根拠
   - **ユーザーの指摘で安易なSource集約を中止**、Chunk維持に決定

6. **emit-research-queue SKILL.md例示の`institution`**
   - ENTITY_TYPE_METAにもALLOWED_ENTITY_TYPESにも存在しない
   - `organization`に修正

### パス別EXTRACTED_FROMの設計

| パス | EXTRACTED_FROM → | 理由 |
|-----|-----------------|------|
| chunk ベース (PDF等) | Chunk | section_titleで出典箇所を特定（例: "Phase 3-2: ARPU分析"）|
| web-research | Source | 1 Source = 1 記事、Chunk分割なし |

## 決定事項

1. **fact_typeバリデーション導入** (`dec-2026-03-28-fact-type-validation`)
   - FACT_TYPE_META外の値は`"empirical"`にフォールバック

2. **about_entitiesデュアルフォーマット+フォールバック** (`dec-2026-03-28-about-entities-fallback`)
   - `_resolve_entity_rels`がstr/dictの両方を処理
   - 空のとき同一chunk内entityにフォールバック

3. **EXTRACTED_FROMはChunk維持** (`dec-2026-03-28-extracted-from-chunk`)
   - chunkベースパスのChunk粒度を保存（Sourceに集約しない）
   - SKILL.mdのv3.0記述を修正

4. **ENTITY_TYPE統一** (`dec-2026-03-28-entity-type-unification`)
   - ALLOWED_ENTITY_TYPESにconcept/regulation追加
   - SKILL.md例示のinstitution→organization修正

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `scripts/emit_research_queue.py` | fact_type検証、_resolve_entity_rels dual format、about_entitiesフォールバック |
| `scripts/kg_quality_metrics.py` | ALLOWED_ENTITY_TYPESにconcept/regulation追加 |
| `.claude/skills/kg-quality-check/SKILL.md` | Source Groundingクエリ修正（EXTRACTED_FROM 3パス+coalesce）|
| `.claude/skills/save-to-research-graph/SKILL.md` | v3.0記述修正、検証クエリ修正 |
| `.claude/skills/save-to-research-graph/guide.md` | EXTRACTED_FROMセクション修正 |
| `.claude/skills/emit-research-queue/SKILL.md` | institution→organization修正 |

## 次回の議論トピック

- 変更のコミット・PR作成
- web-researchパスとchunkパスの統一戦略（将来的にChunk廃止するか否か）
- emit_research_queue.py のENTITY_TYPE_METAとALLOWED_ENTITY_TYPESの正規ソース一元化
