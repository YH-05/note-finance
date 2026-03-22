# 議論メモ: 論文42本投入後のKG品質チェック — 消化不良の診断

**日付**: 2026-03-21
**参加**: ユーザー + AI

## 背景・コンテキスト

同日のセッションで42本の論文（TDA/CT橋渡し5本 + JSAI SIG-FIN-036 34本 + その他3本）をresearch-neo4jに投入。投入後にKG品質チェックを再実行し、品質変化を計測。

## KG品質 Before / After

| 指標 | 投入前 | 投入後 | 変化 |
|------|------:|------:|------|
| ノード数 | 5,836 | 7,391 | +26.6% |
| リレーション数 | 39,202 | 41,796 | +6.6% |
| Overall Score | 60.7 (B) | 51.8 (C) | **-8.9pt** |
| Structural | 75.0 | 62.5 | -12.5 |
| Connected Ratio | 0.9474 | 0.7482 | **-21%** |
| Consistency | 50.0 | 33.3 | -16.7 |
| Constraint Violations | 1 | 34 | +33 |
| Schema Compliance Violations | 21 | 120 | **+99** |
| Accuracy (LLM) Overall | 0.475 | 0.631 | **+33%** |
| Source Grounding | 0.100 | 0.680 | **+580%** |
| Discoverability | 66.7 | 33.3 | -33.4 |
| Bridge Rate | 0.895 | 0.545 | **-39%** |

## 診断

**「消化不良」**: ノードは26%増えたがリレーションは6.6%増にとどまり、新Entityの多くが孤立した小サブグラフを形成。

**改善した点**:
- Accuracy: Source Grounding 0.10→0.68（新論文のSTATES_FACTリレーションが正常に機能）
- Timeliness: Coverage Span 3→5日
- Semantic Diversity: 0.695→0.697（微増）

**悪化した点**:
- Structural: Connected Ratio 0.95→0.75、Orphan Ratio 0.002→0.048
- Consistency: 制約違反1→34、schema違反21→120
- Discoverability: Bridge Rate 0.90→0.55、no_path 21→91

## 決定事項

1. **消化フェーズ最優先**: 新規投入より構造品質回復（dedup、クロスリンク、schema修復）を先行
2. **NASマウント暫定対応**: rsyncによるローカルコピー起動。恒久対応は別途検討

## アクションアイテム

- [ ] **[Critical]** Entity重複整理 + schema違反120件修復 (act-005)
- [ ] **[Critical]** JSAI論文のクロスリンク強化: Bridge Rate 0.55→0.80 (act-006)
- [ ] **[High]** /tmp/neo4j-research-data → NAS書き戻し (act-009)
- [ ] **[Medium]** Orphanノード接続: Connected Ratio 0.75→0.90 (act-007)
- [ ] **[Medium]** NASマウント恒久対応検討 (act-008)

## 次回の議論トピック

- Entity dedup の自動化方針（名寄せルール設計）
- クロスリンク強化のバッチ実行戦略
- NAS/Docker統合の恒久アーキテクチャ
