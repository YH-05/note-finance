# 議論メモ: research-enrichment スキル設計（Phase構成・スコアリング確定）

**日付**: 2026-03-25
**参加**: ユーザー + AI
**前回議論**: `docs/plan/SideBusiness/2026-03-24_discussion-research-enrichment-design.md`

## 背景・コンテキスト

creator-enrichment（creator-neo4j向け）のように、research-neo4jへ自動で情報投入するループ型スキルを構築したい。前回議論（2026-03-24）で2層アーキテクチャ、Gap分析4軸、フォールバックチェーン等の大枠が決定済み。今回は具体的なPhase構成・スコアリング・ソース選択ロジックを確定する。

## 議論のサマリー

### 1. ターゲット選定ロジック

3案を比較:
- 案A: 上位1ターゲット集中 → シンプルだがサイクルの幅が狭い
- 案B: 軸別1件ずつ計4件 → 網羅的だが1件あたりの検索量が薄い
- **案C（採用）: 統合スコア上位3-5件バッチ** → バランスが最良

統合スコア算出:
```
unified_score = w1 * category_gap + w2 * entity_gap + w3 * staleness + w4 * financial_gap
```

各軸の正規化:
- category_gap: `1.0 / (facts_per_topic + 1)`
- entity_gap: ticker あり & Fact 0 → 1.0、Fact 1-3 → 0.5、4以上 → 0
- staleness: `min((today - latest_fact_date).days / 90, 1.0)`
- financial_gap: sec_cik あり & FDP 0 → 1.0

### 2. 投入パイプライン

**2段パイプライン踏襲**を採用:
1. LLM分類 → web-research入力JSON（`.tmp/research-enrich-*.json`）
2. `emit_research_queue.py --command web-research` → graph-queue JSON
3. `/save-to-research-graph` → Neo4j投入

理由: neo4j-write-rulesの「emit経由必須」ルール準拠。過去の孤立ノード事案の再発防止。

### 3. ソース選択

**ターゲット属性ベースの動的選択**を採用:

| ソース | 実行条件 |
|--------|---------|
| Tavily/WebSearch EN | 常時（2クエリ/ターゲット） |
| Tavily/WebSearch JA | 常時（2クエリ/ターゲット） |
| Reddit | 常時（設定subredditから） |
| SEC EDGAR | target.ticker が存在 |
| alphaxiv | target.category ∈ {Technology, EquityResearch} |
| Wikipedia | target.description が未登録 |
| browser-use CLI | フォールバック専用 |

### 4. RawStore統合

**SEC EDGAR・alphaxiv以外は初期から組み込み**:
- Web検索結果、Reddit投稿、WebFetch/browser-use抽出テキスト → RawStore.save_text()
- SEC EDGAR（構造化データ）、alphaxiv（論文メタデータ）→ RawStore不要
- collect/ingest分離の思想に合致、同一データのcreator-neo4j再投入も可能に

## 決定事項

1. **ターゲット選定**: 4軸統合スコアの上位3-5件バッチ処理
2. **投入パイプライン**: 2段パイプライン踏襲（emit_research_queue.py → /save-to-research-graph）
3. **ソース選択**: ターゲット属性ベースの動的選択
4. **RawStore**: SEC EDGAR・alphaxiv以外で初期から組み込み

## Phase構成（確定）

```
/research-enrichment --until HH:MM

Phase 0: Init
  Neo4j接続確認、設定読込、セッションログ作成、
  browser-use可用性チェック、時刻チェック

Phase 1: Gap Analysis
  4軸Cypherクエリ実行 → 統合スコア算出 → 上位3-5ターゲット選定

Phase 2: Search
  ターゲットごとに:
  - Web検索 EN/JA（Tavily→WebSearchフォールバック）
  - Reddit subreddit
  - SEC EDGAR（tickerあり）
  - alphaxiv（Technology/EquityResearch系）
  - Wikipedia（description未登録）
  → raw_items[] → RawStore保存（EDGAR/alphaxiv除く）

Phase 3: Transform
  LLM構造化: Source/Fact/Claim/Entity分類
  → web-research入力JSON（.tmp/research-enrich-*.json）

Phase 4: Save
  4a: emit_research_queue.py --command web-research → graph-queue JSON
  4b: /save-to-research-graph → Neo4j投入

Phase 5: Cycle Report + Loop
  投入統計・ログ追記、時刻チェック:
  now < --until - 5min → Phase 1へループ

Phase 6: Summary
  セッション全体の統計レポート
```

## アクションアイテム

- [ ] research-enrichment SKILL.md 作成（Phase 0-6 全体） (優先度: 高)
- [ ] Gap分析4軸Cypherクエリを references/gap-analysis-queries.md として実装 (優先度: 高)
- [ ] research-enrichment-config.json 設定ファイル作成 (優先度: 中)
- [ ] RawStore統合: Phase 2のWeb検索/Reddit結果をRawStore.save_text()で保存 (優先度: 中)

## 次回の議論トピック

- 統合スコアの重み（w1-w4）の初期値とチューニング方針
- Layer 1（事前バッチ）の統合ランナー設計
- research-enrichmentとcreator-enrichmentの共通化（共通基底スキル？）

## 参考情報

- creator-enrichment SKILL.md: `.claude/skills/creator-enrichment/SKILL.md`
- 前回議論: `docs/plan/SideBusiness/2026-03-24_discussion-research-enrichment-design.md`
- save-to-research-graph: `.claude/skills/save-to-research-graph/SKILL.md`
- emit_research_queue.py: `scripts/emit_research_queue.py`
- neo4j-write-rules: `.claude/rules/neo4j-write-rules.md`
