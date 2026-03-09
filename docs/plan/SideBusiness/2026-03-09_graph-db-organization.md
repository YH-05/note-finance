# 議論メモ: グラフDB組織化の評価と改善計画

**日付**: 2026-03-09
**参加**: ユーザー + AI

## 背景・コンテキスト

副業プロジェクトのグラフDB（Neo4j）が十分に組織化されているか、新しいアイディア発掘に使えるかを評価した。

### 診断結果

グラフDBは**議論アーカイブ**としては機能しているが、**知識発見エンジン**としては不十分だった。

主な問題点:
1. **Claim品質**: 686件全てが `claim_type: "analysis"` で未分類、sentiment/magnitude なし
2. **時系列構造なし**: TimePeriod ノードが未実装
3. **クロスドメイン断絶**: Source 間のテーマ的つながりが構築されていない

## 議論のサマリー

### Phase A: Claim再構造化（最優先）

- 686件のClaimを12種の claim_type + sentiment + magnitude に分類
- 実装方式: AIエージェントによるコマンドベース（`/restructure-claims`）
- Python スクリプト + API Key 方式は却下（環境依存を避けるため）

### 実行結果

| 指標 | 値 |
|------|-----|
| 処理件数 | 686/686 (100%) |
| 平均 sentiment | +0.05 (ほぼ中立) |
| sentiment 範囲 | -0.70 ~ +0.80 |
| 平均 magnitude | 0.44 |

#### claim_type 分布

| claim_type | 件数 | 割合 |
|------------|------|------|
| fundamental | 271 | 39.5% |
| bullish | 138 | 20.1% |
| risk_event | 73 | 10.6% |
| bearish | 72 | 10.5% |
| technical | 33 | 4.8% |
| earnings_beat | 28 | 4.1% |
| sector_rotation | 27 | 3.9% |
| policy_hawkish | 21 | 3.1% |
| earnings_miss | 9 | 1.3% |
| policy_dovish | 7 | 1.0% |
| guidance_up | 4 | 0.6% |
| guidance_down | 3 | 0.4% |

## 決定事項

1. **dec-2026-03-09-001**: Phase A（Claim再構造化）を最優先で実施 → **完了**
2. **dec-2026-03-09-002**: AIエージェントによるコマンドベース実装（`/restructure-claims`） → **完了**

## アクションアイテム

- [ ] Phase B: TimePeriod 時系列構造の追加 (優先度: 高) `act-2026-03-09-001`
- [ ] Phase C: クロスドメイン接続（Source→Concept, Narrative→CandidateTheme） (優先度: 中) `act-2026-03-09-002`
- [ ] Entity enrichment: 72件のEntityにsector/industry付与 (優先度: 中) `act-2026-03-09-003`

## 次回の議論トピック

- Phase B の TimePeriod ノード設計（粒度: 日/週/月？）
- Claim分類結果を使った記事ネタ発掘クエリの設計
- Entity enrichment の実施方法（手動 vs AIエージェント）

## 成果物

| 成果物 | パス/ID |
|--------|---------|
| コマンド定義 | `.claude/commands/restructure-claims.md` |
| Python スクリプト | `scripts/restructure_claims.py` |
| Neo4j Discussion | `disc-2026-03-09-graph-db-organization` |
| Neo4j Decisions | `dec-2026-03-09-001`, `dec-2026-03-09-002` |
| Neo4j ActionItems | `act-2026-03-09-001` ~ `003` |
