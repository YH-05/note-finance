# KGギャップ分析レポート

**対象記事**: 投資の心理学（損失回避・FOMO・暴落時の行動バイアス）  
**実行日**: 2026-04-04  
**インスタンス**: research-neo4j (bolt://localhost:7688)

---

## 既存データサマリー

| 項目 | 件数 | 備考 |
|------|------|------|
| 損失回避関連 Fact/Claim | 0件 | no_coverage |
| 行動経済学関連 Topic | 0件 | no_coverage |
| NISA心理関連 Source | 0件 | no_coverage |
| NISA関連 Topic（既存） | 5件 | 投資教育・積立投資系のみ |

**DB状態**: apoc.meta.schema で I/Oエラー（文字列ストアに破損疑い）。ラベル確認は正常。

---

## 特定されたギャップ

### HIGH優先度

| # | ギャップ種別 | 内容 |
|---|------------|------|
| 1 | no_coverage | 損失回避・FOMO・アンカリング・ディスポジション効果のFact/Claimがゼロ件 |
| 2 | no_coverage | DALBAR・Morningstar行動ギャップデータがゼロ件 |
| 3 | no_coverage | 日本NISA投資家の暴落時行動データがゼロ件 |
| 4 | stale_data | 前回リサーチ2026-03-15から約20日経過。2025年4月トランプ関税ショック後のデータが未反映 |

---

## 推奨検索クエリ（ギャップ解消用）

優先度順:

1. `DALBAR QAIB 2025 investor behavior gap 848bp 2024` → ✅ 解消済み
2. `Morningstar mind the gap 2025 annual behavioral gap 122bp` → ✅ 解消済み
3. `日本 NISA投資家 2024年8月 令和ブラックマンデー 狼狽売り 行動データ` → ✅ 解消済み
4. `2025年4月 トランプ関税ショック NISA投資家 行動 行動経済学` → ✅ 解消済み
5. `disposition effect Japanese retail investors 2025 research` → ✅ 解消済み

---

## ギャップ解消状況

| ギャップ | 解消状況 | 収集ソース |
|---------|---------|-----------|
| 損失回避・行動バイアス基礎データ | ✅ 強化 | Investopedia, PICBE 2025, EFMP 2025 |
| DALBAR行動ギャップ | ✅ 解消 | planadviser.com, virtus.com, kirrmar.com |
| Morningstar Mind the Gap | ✅ 解消 | Barclays Private Bank, Strategence Capital |
| 日本NISA 2024年8月データ | ✅ 解消 | MUFG資産形成研究所, 大和AM白書2025 |
| 日本NISA 2025年4月データ | ✅ 解消 | アライアンス・バーンスタイン |
| 株価ショック短縮化トレンド | ✅ 解消 | SBI証券レポート, 日経 |
| ディスポジション効果（日本） | ✅ 解消 | MDPI (Kohsaka et al.) |
| 日本個人投資家行動統計2025-2026 | ✅ 解消 | Yahoo Finance/Bloomberg data |

---

## KG永続化結果

- **実行日時**: 2026-04-04（docker restart neo4j-enterprise 後に解消）
- **投入ノード数**: 48
- **投入リレーション数**: 177
- **確認済み投入データ**:
  - Topic: 損失回避バイアス、行動経済学・投資心理、ディスポジション効果、FOMO、DALBAR行動ギャップ、NISA投資家行動、令和のブラックマンデー（7件）
  - Fact: DALBAR 848bpギャップ、Morningstar 122bp、AB調査NISA逆張り行動 等
- **副次対応**: `data/config/neo4j-instances/research.yaml` の `bolt_uri` を 7688→7687 に修正
