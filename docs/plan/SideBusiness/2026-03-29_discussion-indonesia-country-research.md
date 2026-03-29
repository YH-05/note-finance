# 議論メモ: インドネシア国・経済・政治状況 調査 + KG永続化

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

インドネシアテレコムセクター記事（ISAT/TLKM）の執筆に向け、マクロ経済・金融政策・政治状況の深掘りリサーチを実施。
`/investment-research` スキルで Bank Indonesia（bi.go.id）公式データおよび research-neo4j KG既存データを活用した。

## 調査結果サマリー

### 国家概要
- 人口: 2億8,390万人（SEA最大）、17,000島
- GDP: 1.4兆USD（2024、World Bank）、成長率 5.0〜5.11%
- 一人あたりGDP: 4,925USD

### 金融政策（Bank Indonesia公式）
- BI-Rate: 4.75%（2026年3月17日現在）
- 2024年9月からの累計利下げ: 150bp
- 利下げサイクル: 2025年6月5.50% → 7月5.25% → 8月4.75%、その後7会合連続据え置き

### インフレ（Bank Indonesia公式）
- 2026年2月: 4.76%（前年比）— BIターゲット上限3.5%を大幅超過
- 主因: 2025年電気料金割引の低ベース効果剥落（一時的要因）
- コアインフレ（2026年1月）: 2.5%（BIターゲット中央値水準）

### 政治状況
- プラボウォ政権（2024年10月就任）。軍出身、強い中央集権志向
- 2026年予算: GDP比 2.68% 財政赤字（上限3%に接近）
- IMFが財政健全化を勧告

## 技術的成果

### KG永続化（research-neo4j port 7688）
- 投入ファイル: `gq-20260329014049-5f1aede5.json`（schema v3.0）
- 3 Source + 2 Topic + 4 Entity + 6 Fact
- Phase 3c 検証結果: STATES_FACT 6/6, RELATES_TO 10/10, EXTRACTED_FROM 6/6 — **全OK**

## 決定事項

1. **BPSフォールバック**: bps.go.id は Cloudflare 403 でアクセス不可。Bank Indonesia公式データ + KG既存データで代替調査完了（`dec-2026-03-29-bps-fallback`）
2. **KG v3.0投入**: BI公式時系列データ（BI-Rate月次6件・インフレ月次6件）をresearch-neo4jに永続化（`dec-2026-03-29-kg-indonesia-v30`）

## アクションアイテム

- [ ] Indonesia Telecom 記事 review → publish 3本（優先度: 高）— `act-2026-03-29-002`
- [ ] Claude Code restart → custom Tavily MCP server 有効化（優先度: 高）— `act-2026-03-29-001`

## 調査の活用方針

- インドネシアテレコムセクター記事の「マクロ環境」セクションに本調査データを活用
- BI-Rate据え置き（4.75%）とインフレ上昇（4.76%）の組み合わせは、通信事業者の設備投資コスト・消費動向に影響
- プラボウォ政権の財政拡張と国内産業保護政策はISAT/TLKMの規制環境に関連

## 参考情報

| ソース | URL | 権威性 |
|--------|-----|--------|
| Bank Indonesia BI-Rate | https://www.bi.go.id/en/statistik/indikator/bi-rate.aspx | official |
| Bank Indonesia Inflation | https://www.bi.go.id/en/statistik/indikator/data-inflasi.aspx | official |
| World Bank Indonesia | https://data.worldbank.org/country/indonesia | official |
