# KG投入レポート

## 投入日時
2026-04-04

## 入力ファイル
- graph-queue: `.tmp/graph-queue/web-research/gq-20260404052948-b031c81d.json`
- resolved: `.tmp/graph-queue/web-research/gq-20260404052948-b031c81d.resolved.json`

## 投入結果

| 種別 | 件数 |
|------|------|
| **ノード（合計）** | **74** |
| **リレーション（合計）** | **284** |

### リレーション検証

| リレーション種別 | 期待値 | 実際 | 状態 |
|---------------|--------|------|------|
| STATES_FACT（Source→Fact） | 8 | 8 | ✅ |
| EXTRACTED_FROM（Fact→Source） | 8 | 8 | ✅ |
| TAGGED（全ノード→Topic） | 120 | 119 | ⚠️ 1件未解決 |
| TAGGED（Fact→Topic） | 48 | 48 | ✅ |

## ギャップ解消状況

| ギャップ | 解消 |
|---------|------|
| 債券ファンドデータ | ✅ |
| 国際分散（VXUS）データ | ✅ |
| 年代別ポートフォリオ例 | ✅ |
| S&P500 CAPE比率・集中リスク | ✅ |
| 60/40歴史データ | ✅ |
| 海外投資家実態（Reddit/iShares調査） | ✅ |
| S&P500一本リスク事例 | ✅ |

## 注意事項
- TAGGEDリレーションが1件未解決（topic_key解決失敗と思われる）
- entity_linker実行済み（NERフォールバックあり）
