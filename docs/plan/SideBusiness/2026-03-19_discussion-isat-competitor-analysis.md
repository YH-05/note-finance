# 議論メモ: ISAT競合企業分析 & データパイプライン修正

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4jにISAT（Indosat Ooredoo Hutchison）の調査データが蓄積されているが、競合企業（Telkomsel, XLSmart, Telkom Indonesia）の情報量が不足していた。ISATと同等水準まで競合データを拡充するため、gemini-searchを使った10フェーズの系統的調査を実施した。

## 議論のサマリー

### Phase 1: 競合データ調査（10フェーズ）

| フェーズ | 対象 | 内容 |
|---------|------|------|
| 1 | Telkomsel | 財務指標 & 運用KPI |
| 2+5 | Telkomsel | 戦略・パートナーシップ・バリュエーション |
| 3+4+6 | XLSmart | 財務・統合進捗・バリュエーション |
| 7 | Telkom Indonesia | 最新動向補強（Danantara, Infranexia, NeutraDC） |
| 8 | 全社 | ESG・コスト最適化・インフラ |
| 9 | 全社 | B2B・固定BB・競争比較 |
| 10 | 全社 | リスク分析・セクターアウトルック |

**投入結果**:

| 企業 | Facts | Sources | Claims | 合計 |
|------|-------|---------|--------|------|
| ISAT | 51 | 82 | 40 | 173 |
| Telkom Indonesia | 30 | 66 | 34 | 130 |
| Telkomsel | 44 | 19 | 19 | 82 |
| XLSmart | 21 | 18 | 12 | 51 |

### Phase 2: Source URL検証

- Tavily MCPで8件の実URLを検証・更新
- 27件は `gemini-search-aggregated://` に統一（`url_verified: false`, `data_source: gemini-cli-web-search`）

### Phase 3: パイプライン問題の発見と修正

データ投入過程で3つの問題が発覚:

1. **MERGEキー不整合**: `topic_id`/`entity_id` でMERGEしていたが、異なるパイプラインで同じTopic/Entityに異なるIDが付与され衝突
2. **Claims未処理**: `map_web_research()` が入力JSONの `claims[]` を完全に無視
3. **データ出自追跡不能**: Source URLがGemini集約結果で検証不能

## 決定事項

1. **save-to-graphのMERGEキー変更**: Topic は `topic_key`、Entity は `entity_key` でMERGE（`topic_id`/`entity_id` は ON CREATE で設定）
2. **Claims処理追加**: `_build_wr_claims()` を新設し `map_web_research` に統合。Claims → Claimノード + MAKES_CLAIM + ABOUT リレーション生成
3. **data_source passthrough**: `_build_wr_sources()` に `data_source` フィールドの透過的パスを追加
4. **url_verified**: パイプライン修正不要。運用対応（gemini-search利用時は `data_source` を入力JSONに明記）

## アクションアイテム

- [ ] make check-all で修正の品質チェック実行 (高)
- [ ] 修正をコミット&PR作成 (高)
- [ ] Telkomsel/XLSmartのSources数をISAT水準に近づける追加セルサイドレポートPDF投入 (中)

## 変更ファイル

| ファイル | 修正内容 |
|---------|---------|
| `scripts/emit_graph_queue.py` | `_build_wr_claims()` 新設, `map_web_research()` Claims統合, `_build_wr_sources()` data_source追加, docstring拡充 |
| `.claude/skills/save-to-graph/SKILL.md` | Topic/Entity MERGEキー変更 (topic_key/entity_key) |
| `.claude/skills/save-to-graph/guide.md` | 同上 + バッチ投入例更新 |

## 次回の議論トピック

- Telkomsel/XLSmartのセルサイドレポートPDF投入によるSources/Claims補強
- ISATのInitial Report執筆に向けた競合比較セクションの設計
