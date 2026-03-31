# 議論メモ: Starlinkリサーチ実施と記事化着目点の選定

**日付**: 2026-03-30
**参加**: ユーザー + AI
**スキル**: /investment-research

---

## 背景・コンテキスト

SpaceX Starlinkの衛星通信ビジネスと競合他社への影響を把握するため、`/investment-research` スキルを実施。
深度: standard（9回のWeb検索）。KGギャップ分析→マルチソース検索→ファクト整理→論点抽出→KG永続化まで完了。

**リサーチノート**: `.tmp/investment-research/starlink-satellite-competition_20260330-1430.md`
**KG投入済み**: `gq-20260330110926-6b04313f.json`（research-neo4j）

---

## 主要リサーチ結果サマリー

### Starlink 2025年実績
| 指標 | 数値 |
|------|------|
| 加入者 | 920万人（1年で2倍） |
| 推定収益 | $11.8B |
| Speedtestシェア | 97.1%（世界） |
| 国際ブロードバンドシェア | 約40% |

### 競合へのインパクト
- **HughesNet**: ゴーイングコンサーン開示、残存加入者739,000人
- **EchoStar**: スペクトル$17BでSpaceXに売却、2025年純損失$144.97億
- **Viasat**: 純損失率-25%、負債$130億超、5年株価-80%
- **SES+Intelsat合併（2025年7月）**: $3.1B、合併理由はStarlink対抗
- **GEO業界再編3件**: Viasat+Inmarsat/Eutelsat+OneWeb/SES+Intelstatがいずれも2023-2025年

### 市場別インパクト
- 航空IFC: Starlink 2034年39%シェア予測（現在1,400機）
- 海事: NGSO帯域シェア2034年98%
- D2C: T-Mobile提携700万ユーザー（2025年7月商業ローンチ）

---

## 記事化推奨着目点（5件）

### 選定決定事項

| 優先度 | テーマ | カテゴリ | 理由 |
|--------|--------|--------|------|
| ★★★ | EchoStarの失敗パターン | stock_analysis | データ充実・投資教訓として明快 |
| ★★★ | GEO業界再編3件の歴史的意味 | macro_economy | マクロ視点・note金融記事向き |
| ★★ | Amazon Leo vs Starlink | macro_economy | 2026年最注目テーマ |
| ★★ | Starlinkが作る新地政学 | macro_economy | 後回し（ISATと重複） |
| ★ | AST SpaceMobileのB2B賭け | stock_analysis | 詳細調査が必要 |

### 優先度1: EchoStarの失敗パターン
- スペクトルという高コスト固定資産がLEOに駆逐された典型例
- $17Bスペクトル売却＋ゴーイングコンサーンの経緯
- 投資家向け教訓として構成しやすい

### 優先度2: GEO業界再編3件の歴史的意味
- わずか2年（2023-2025）で3組の大型合併
- 「産業崩壊」の証左としてStarlinkの破壊力を際立たせる
- note.com読者層（長期投資家）に刺さる構成

### 優先度3: Amazon Leo vs Starlink（将来）
- 2025年4月初打ち上げ、2026年商業化
- AWS統合・Amazonエコシステムの潜在力
- 「Starlink一強時代はいつ終わるか？」という問い

---

## 決定事項

1. 記事化推奨着目点5件を選定（詳細は上表参照）
2. 記事化優先度の暫定順位を設定（EchoStar → GEO再編 → Amazon Leo）
3. 残存ギャップ（インド市場詳細・Eutelsat財務・ViaSat-3障害詳細）は次回補完

---

## アクションアイテム

- [ ] 記事化テーマ1本を決定し `/article-init` で記事フォルダ作成（優先度: 高）
- [ ] Eutelsat財務・ViaSat-3障害の補完調査 `/investment-research --theme "Eutelsat financial 2025"` （優先度: 中）

---

## 次回の議論トピック

- どの記事テーマを先に着手するか（EchoStar vs GEO再編）
- Starlinkリサーチの続編: インド市場・ASEAN規制詳細

---

## 参考情報

- リサーチノート: `.tmp/investment-research/starlink-satellite-competition_20260330-1430.md`
- KG投入: `gq-20260330110926-6b04313f.json`（research-neo4j済）
- 既存KGにISAT/TLKM/ASEAN衛星競争分析が蓄積済み（重複注意）
