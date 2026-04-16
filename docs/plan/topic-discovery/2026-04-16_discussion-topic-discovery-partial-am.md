# 議論メモ: topic-discovery セッション 2026-04-16（asset_management 部分補強）

**日付**: 2026-04-16
**参加**: ユーザー + AI (Claude Opus 4.6)
**Discussion ID**: `disc-2026-04-16-topic-discovery-partial-am`

## 背景・コンテキスト

`/topic-discovery` コマンドによる金融記事トピック発掘セッション。既存記事カテゴリ分布（macro_economy:10, stock_analysis:8, asset_management:9, investment_education:5, market_report:2, earnings:4）と research-neo4j (18,893ノード) の知識ギャップを突合し、次の執筆候補をデータ駆動で決定する。

## 議論のサマリー

### Phase 0: KGマイニング（research-neo4j）

- 未回答Question: 2件（テキスト空のためスコア外）
- Insight gap: 0件
- カバレッジ薄Technology: 1.6T/3.2Tb Transceivers、AI Data Center Power、415V Power、AC vs DC 等8種以上がFact 1件のまま滞留
- ソース急増Entity（30日内）: Oil(14), Fed(11), MAG7各9, Qwen-3-Next各9, LLM(9)
- Controversy: Nvidia(bull25/bear4), LLM(25/4), Telkomsel(27/4)

### Phase HF0: ユーザー判断

KGから kg_gap_score≥5 候補が5件以上揃い充足判定。ユーザーは `p asset_management` を選択し、asset_managementに絞ってWeb検索を追加することに合意。

### Phase 1: Web検索（asset_management 4クエリ）

主要発見:
- Bloomberg「イラン戦火でヘッジの定石打破、分散投資の前提が揺らぐ」→ 60/40モデル論点
- 金が1980年インフレ調整後ピーク超え
- Monex/YouTube/gentosha-goで50-60代向け新NISA出口戦略コンテンツ多数 → 退職金シニア需要

### Phase 3: スコアリング結果（KG補正含む）

| 順位 | トピック | カテゴリ | スコア | KG Gap |
|---|---|---|---|---|
| 1 | MAG7 Q1 2026決算プレビュー（AAPL/GOOGL/META/AMZN/MSFT 収斂評価） | earnings | 45 | 7 |
| 2 | AIデータセンター物理層（光モジュール/415V直流/液冷） | stock_analysis | 45 | 8 |
| 3 | Nvidia論争整理（bull25 vs bear4 をInitial Report形式） | stock_analysis | 45 | 7 |
| 4 | イラン戦争×60/40崩壊（asset_management） | asset_management | 42 | 5 |
| 5 | 退職金1000万×新NISA出口戦略 | asset_management | 41 | 2 |

### Phase 5: 永続化

- セッション: `.tmp/topic-suggestions/2026-04-16_0813.json`
- 履歴: `data/topic-history/suggestions.jsonl`
- research-neo4j: Source 1件 + Facts 5件 + Topics 3件（`internal://topic-discovery/topic-suggestion-2026-04-16T0813`）

### 運用上の発見（Phase 5.3 再実行時）

- `src/data_pipeline/neo4j_loader.py` は CLI `main()` を持たないライブラリモジュール。直接実行すると exit 0 でも無反応。
- 正規CLIは `scripts/ingest_graph_queue.py --file <resolved.json>`
- `emit_research_queue.py --command topic-discovery` は入力JSONの entities/facts を無視。`--command web-research` を使うべき。

## 決定事項

1. **[dec-2026-04-16-mag7-earnings-priority]** 次回執筆は MAG7 Q1 2026決算プレビュー を最優先。4/25決算週に合わせて公開。完成後 Rank 3 Nvidia論争 → 5/21 NVDA決算接続で3段ロケット導線を形成。
2. **[dec-2026-04-16-ingest-cli-canonical]** research-neo4j 投入は `scripts/ingest_graph_queue.py --file` を正規ルートとする。`neo4j_loader.py` 直接実行は禁止。
3. **[dec-2026-04-16-emit-command-webresearch]** `emit_research_queue.py --command` は `web-research` を使用（`topic-discovery` はentities/facts無視）。

## アクションアイテム

- [ ] **act-2026-04-16-001** MAG7決算プレビュー記事フォルダ作成＆ドラフト着手 (high, due 2026-04-24)
- [ ] **act-2026-04-16-002** AIデータセンター物理層記事 (high, due 2026-05-09)
- [ ] **act-2026-04-16-003** Nvidia論争整理記事 (high, due 2026-05-18 / NVDA決算前)
- [ ] **act-2026-04-16-004** 60/40崩壊記事 (medium, due 2026-05-02)
- [ ] **act-2026-04-16-005** 退職金NISA出口戦略記事 (medium, due 2026-05-16)
- [ ] **act-2026-04-16-006** topic-discoveryスキルPhase 5.3テンプレ修正（ingest_graph_queue.py明記＋web-research統一） (medium, due 2026-04-23)

## 次回の議論トピック

- earnings記事の収斂評価フォーマットの標準化（横比較テンプレ作成）
- stock_analysis の Initial Report形式（Nvidia論争記事で確立予定）の他銘柄への展開可能性
- 「日本語市場 × Tavily検索」の歩留まり改善（今回のiDeCo/NISA検索で日本語ヒットが弱かった）

## 参考情報

- Bloomberg: イラン戦火、ヘッジの「定石」打破－揺らぐ分散投資の前提 (2026-03-13)
- research-neo4j: Source `internal://topic-discovery/topic-suggestion-2026-04-16T0813` で Facts 5件記録
- 既存関連記事: `articles/macro_economy/2026-04-09_iran-war-economic-timeline-market-impact/`, `articles/stock_analysis/2026-04-11_hyperscaler-700b-capex-analysis/`, `articles/stock_analysis/2026-04-11_vistra-ai-power-demand/`
