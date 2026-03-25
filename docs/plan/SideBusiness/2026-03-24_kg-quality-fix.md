# KG品質チェック + 6項目一括修復

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j (bolt://localhost:7688) の定期品質チェックを実施。
7カテゴリ計測 + LLM-as-Judge accuracy評価 + 創発的発見ポテンシャル評価の3フェーズを完了し、
特定された6項目の改善を即時実行した。

## 品質スコア（修復前）

| カテゴリ | スコア |
|---------|-----:|
| Overall | 61.4/100 (Rating B) |
| Structural | 80.0 |
| Completeness | 50.0 |
| Consistency | 50.0 |
| Accuracy (LLM-as-Judge) | 0.407 (FC=0.645, SG=0.000, TV=0.495) |
| Timeliness | 66.7 |
| Finance Specific | 66.7 |
| Discoverability | 66.7 |

## 創発的発見レポート（Overall: 0.615）

4件の発見・仮説を構築:

1. **圏論→金融ARPU分析への適用仮説** — Causal Emergence（因果創発）のマクロ＞ミクロ説明力概念がISATのARPU要因分解に適用可能。ただし2クラスタ間ブリッジFactなし
2. **TLKM コスト削減 vs マージン低下の緊張** — EBITDA Margin 4年連続低下（52.9%→50.0%）に対し6T IDRコスト削減目標。Revenue横ばいの中でマージン回復の蓋然性に疑問
3. **バリュエーション指標の非対称性** — ISAT: EV/EBITDA 4.8x等保有。TLKM: ゼロ。J.P. MorganのROIC低下懸念を検証不能
4. **AI投資ブーム→通信セクター構造変化** — AI市場$2.4B→$10.9B(CAGR 29%)でISAT(GPUaaS)とTLKM(NeutraDC)の技術戦略分岐

## 6項目修復結果

| # | 項目 | Before | After |
|---|------|--------|-------|
| 1 | Source Grounding | 0% | 21.5% (517 EXTRACTED_FROM) |
| 2 | Stance summary NULL | 0/74 | 74/74 |
| 3 | TLKMバリュエーション | FDP 0件 | 23件 (FY2023-FY2025E) |
| 4 | ノイズClaim | 147件 | 2件残 |
| 5 | Coverage Span | 5日 | 3,659日 |
| 6 | インデックス | 41件 | 45件 |

## 決定事項

1. **Source Grounding修復方式**: Fact/Claim.source_url → Source.url の EXTRACTED_FROM 直接接続（パイプライン非経由の修復作業）
2. **ノイズClaim基準**: auto-claim-* プレフィックス + 100字未満 = 削除対象
3. **TLKMバリュエーション直接投入**: web-researchパイプラインがFDP非対応のため修復作業として実施。Telkom公式IR出典

## アクションアイテム

- [ ] **高** Source Grounding残り78.5%改善（パイプライン側でsource_url付与対応）
- [ ] **高** XLSmart（EXCL IJ）データ投入で3社寡占分析基盤完成
- [ ] **中** emit_research_queue.py に FinancialDataPoint 対応追加
- [ ] **低** Probe B クエリ最適化（3ホップ制限 or APOC path procedures）

## 次回の議論トピック

- relationship_compliance 66.7% の改善（EXTRACTED_FROM のスキーマ準拠性確認）
- KG v3.0 FIBO準拠スキーマへの移行タイミング
- AuraDB バックアップとの差分同期

## 参考ファイル

- スナップショット: `data/processed/kg_quality/snapshot_20260324.json`
- Accuracy キャッシュ: `data/processed/kg_quality/accuracy_cache.json`
- 創発的発見レポート: `data/processed/kg_quality/discovery_report_20260324.json`
- Markdown レポート: `data/processed/kg_quality/report_20260324.md`
