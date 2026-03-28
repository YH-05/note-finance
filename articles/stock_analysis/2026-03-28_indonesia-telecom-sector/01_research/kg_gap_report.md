# KG ギャップ分析レポート

## 照会日時: 2026-03-28

## テーマ: インドネシアのtelcomセクターと企業

## 既存データサマリー

- 関連エンティティ: 7件（Telkom Indonesia, Indosat Ooredoo Hutchison, Telkomsel, XL Axiata, Sarana Menara Nusantara, Tower Bersama Infrastructure, Smartfren）
- 関連ファクト: 165件（全体合計）
- 関連クレーム: 446件（bullish: ~105, bearish: ~16, neutral: ~32, その他数値スコア多数）
- 関連ソース: 182件（日付情報なし）
- 関連トピック: 「Indonesian Telecom」(152 claims), 「ASEAN Telecom」(308 claims), 「5G Deployment」(88 claims)
- 未回答Question: 0件
- FinancialDataPoint: 0件

## 既存ファクトの主要内容

- 政府持株: Danantara経由で52.1%, Dwi Warna特別株
- Telkomsel: モバイル収益シェア約51%, 2024年にシェア180bps低下
- IndiHome統合: 2023年7月にTelkomselへ移管、FMC浸透率37%→57%
- 業界統合: 実質3オペレーターに集約、価格競争緩和
- Infranexia（InfraCo）スピンオフ: 2026年1月完了予定
- 自社株買い: 最大3兆IDR（2025年5月〜2026年5月）
- FY2024配当性向: 89%（DPS 212.47 IDR）
- 収益CAGR 2021-2024: 5.4%

## 特定されたギャップ

### HIGH 優先度

| ギャップ種別       | 詳細                                                                          | 推奨検索クエリ                                  |
| ------------------ | ----------------------------------------------------------------------------- | ----------------------------------------------- |
| stale_data         | ソース・ファクトに日付情報がなく鮮度不明。2025-2026年の最新動向が不足の可能性 | "Indonesia telecom sector 2025 2026 outlook"    |
| no_coverage (FREN) | Smartfrenのファクト7件・クレーム4件のみ。カバレッジ薄                         | "Smartfren FREN subscriber market share 2025"   |
| missing_financials | 全エンティティでFinancialDataPoint=0件。バリュエーション・財務データなし      | "Telkom Indonesia TLKM earnings valuation 2025" |

### MEDIUM 優先度

| ギャップ種別                   | 詳細                                                                         | 推奨検索クエリ                                     |
| ------------------------------ | ---------------------------------------------------------------------------- | -------------------------------------------------- |
| missing_bear_case              | bearish claim比率が低い（bullish 105 vs bearish 16）。リスク要因の深掘り不足 | "Indonesia telecom sector risks challenges 2025"   |
| no_coverage (TOWR/TBIG claims) | タワー2社のクレームが少ない（TOWR: 6, TBIG: 5）                              | "Indonesia telecom tower TOWR TBIG growth outlook" |
| no_coverage (EXCL sources)     | XL Axiataのソースが2件のみ                                                   | "XL Axiata EXCL financial performance 2025"        |

## 検索計画

- ギャップ解消用クエリ: 8件（HIGH 3 + MEDIUM 5）
- 通常リサーチクエリ: 6件
- 合計検索予算: 14件（standard深度）
