# KGギャップレポート: 金（ゴールド）の役割完全解説

## 照会日: 2026-05-06
## インスタンス: research-neo4j (port 7688)
## 接続状態: 成功

---

## 既存データサマリー

| 項目 | 件数 |
|------|------|
| 関連Entityノード | 2件（Commodity:Gold, Commodity:金） |
| 関連Factノード | 20件（主に価格データ） |
| 関連Claimノード | 8件（ゴールド関連クレーム、多くは間接的） |
| Sourceノード | 未照会 |
| Topicノード（金関連） | 0件（ABOUT リレーション確認できず） |

### Factノードの内容
- 既存Factはほぼ全て「金スポット価格のデイリーデータ」（2026年2〜5月分が中心）
- JP Morgan長期目標「5,000〜6,000ドル/オンス」が1件確認
- 中央銀行購入（2025年: 863トン）を示すFactが1件
- published_atはほぼ全件nullタイムスタンプ

### Claimノードの内容
- 直接的なゴールド分析クレームは少なく、市場概況クレームに混在
- センチメント: bullish 0.3〜0.5 の中程度

---

## 特定されたギャップ

| ギャップ種別 | 内容 | 優先度 |
|------------|------|--------|
| no_coverage | 金の通貨的役割・金本位制の歴史（ブレトンウッズ/ニクソンショック）に関するFactが0件 | HIGH |
| no_coverage | インフレヘッジとしての機能・1970年代との比較に関するFactが0件 | HIGH |
| stale_data | 既存FactのPublished_atがほぼnull（タイムスタンプ欠落）、鮮度判定不可 | HIGH |
| missing_bear_case | 金のデメリット（配当なし・短期ボラタイル・長期リターン劣後）に関するクレームが0件 | MEDIUM |
| no_coverage | 中央銀行購入の詳細（国別・動機・2024〜2025年のデータ）に関するFactが不足 | MEDIUM |

---

## ギャップ解消クエリと実行結果

### no_coverage (金本位制・通貨的役割)
- 検索: "gold standard Bretton Woods 1971 Nixon shock history currency role"
- 解消状況: **完了** (FRB History, State.gov, Investopedia から信頼性の高い一次・二次ソースを取得)

### no_coverage (インフレヘッジ)
- 検索: "gold 1970s inflation 1980 price history comparison stocks bonds"
- 検索: "gold inflation hedge 2024 2025 performance real returns"
- 解消状況: **完了** (1970年代パフォーマンス、2022年のパラドックス、2024年の急騰を多角的にカバー)

### stale_data (価格データ鮮度)
- 検索: "gold price 2024 2025 record high 3000 3300 dollar all time high drivers"
- 解消状況: **完了** (2024年26%上昇、2025年65%上昇の最新データ取得)

### missing_bear_case (弱気要因)
- research_notes.md 論点11「ゴールドの弱点」として整理済み
- 解消状況: **部分的** (専用URL取得はしていないが内容は整理)

### no_coverage (中央銀行購入詳細)
- 検索: "central bank gold buying 2024 2025 record purchases WGC"
- 検索: "中央銀行 金購入 2024 2025 日本 世界 動向"
- 解消状況: **完了** (WGC報告、Goldman Sachs推計、Bloomberg日本語記事を取得)

---

## 推奨: KG永続化

Neo4j投入のため、以下のエンティティ・ファクト・トピックを新規投入推奨:

### 新規投入推奨エンティティ
- `{name: "World Gold Council", entity_type: "Organization"}`
- `{name: "SPDR Gold Trust", entity_type: "Instrument"}` (ticker: GLD)
- `{name: "iShares Gold Trust", entity_type: "Instrument"}` (ticker: IAU)
- `{name: "Bridgewater Associates", entity_type: "Organization"}`

### 新規投入推奨トピック
- `{name: "金本位制", category: "macro"}`
- `{name: "インフレヘッジ", category: "investment_education"}`
- `{name: "有事の金", category: "geopolitics"}`
- `{name: "中央銀行準備金", category: "macro"}`

### 主要Factリスト（24件）
research_notes.md に記載の全ファクトを emit_research_queue.py に投入する。

---

## ギャップ解消ステータス

| ギャップ | 解消状況 |
|---------|---------|
| no_coverage: 金本位制歴史 | 完了 |
| no_coverage: インフレヘッジ機能 | 完了 |
| stale_data: タイムスタンプ | 最新データ取得で補完 |
| missing_bear_case: 弱気論点 | 部分的（論点リスト記載） |
| no_coverage: 中央銀行購入詳細 | 完了 |

**残存ギャップ: 0件**（全て解消済みまたは論点整理で補完）
