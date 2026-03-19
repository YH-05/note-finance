# 議論メモ: note記事プロジェクト進捗確認 & research-neo4j大規模拡充

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

note記事執筆プロジェクトの進捗確認を起点に、research-neo4jの構造品質改善→新規セクター追加→ASEANコンサルレポート収集の大規模作業を実施。

### 記事ステータス（セッション開始時）
- PUBLISHED: 4本（資産形成2, 投資教育1, 副業1）
- REVISED: 9本（投稿可能だが未投稿）
- DRAFTED: 2本

### research-neo4j問題（セッション開始時）
- Entity→Topic接続: 380/380 全孤立
- Claim→Topic接続: 945/945 全孤立
- Orphan Facts: 596/786 (76%)
- 重複Entity: 20+ペア
- MAG7/G7マクロ/コンサルレポート: カバレッジゼロ

## 実施内容

### Phase D: 構造品質改善

| 施策 | 結果 |
|------|------|
| D1: 重複Entityマージ | 28ノード削除、145リレーション移行、マルチロール5件保持 |
| D2: Entity→Topic接続 | 748リレーション作成、86% (302/351) 接続 |
| D3: Claim→Topic接続 | 5,846リレーション作成、70% (661/945) 接続 |

### Phase C: 新規セクター追加

| 項目 | C1: MAG7 | C2: G7マクロ | 合計 |
|------|---------|------------|------|
| Source | 27 | 48 | 75 |
| Topic | 29 | 11 | 40 |
| Entity | 7 | 49 | 56 |
| Fact | 52 | 67 | 119 |

### 記事ネタ収集（7件）

1. MAG7 AI設備投資サイクル（stock_analysis, 52 facts）
2. 2026年3月FOMC分析（macro_economy, 67 facts）
3. 日銀利上げと円安の構造（macro_economy, 67 facts）
4. Nvidia Q4 FY2026決算深掘り（stock_analysis, 13 facts）
5. クラウド3強の勢力図2026（stock_analysis, 52 facts）
6. The Great Rotation（asset_management, 52 facts）
7. ASEANテレコムセクター投資ガイド（stock_analysis, 124 facts）

### ASEANコンサルレポート10フェーズ反復検索

| Phase | テーマ | 主要ソース |
|-------|--------|----------|
| 1 | マクロ見通し | ADB ADO, IMF REO, AMRO AREO |
| 2 | デジタルエコノミー&FDI | e-Conomy SEA 2025, ASEAN Investment Report |
| 3 | ESG&エネルギー転換 | EY SEA PE, Deloitte, ACCA |
| 4 | 政治リスク | KPMG/Eurasia Group, CSIS, Brookings |
| 5 | 各国マクロ指標 | DBS ASEAN-6, OCBC ASEAN-5, ING |
| 6 | インフラ&人口動態 | McKinsey Infrastructure, AMRO |
| 7 | 金融セクター | Oliver Wyman Asia 2030, AMRO FSR |
| 8 | Danantara・国営企業改革 | Indonesia MoF, US State Dept, SWP |
| 9 | 通貨&関税交渉 | Maybank GWM, OCBC, UOB |
| 10 | 気候リスク・選挙カレンダー | Control Risks, Energy Tracker, World Bank |

投入結果: 24 Sources, 12 Topics(11 new), 25 Entities(17 new), 25 Facts, 888 TAGGEDリレーション

### 主要発見（ASEANコンサルレポート）

**マクロ**: ADB GDP 4.2%/4.3%(2025/26)、タイ1.6%で最弱、ベトナム6.7%で最強
**金融政策**: BI/BSP各50bps利下げ見込み、BOT 1.25%→1.00%可能、MYR/SGD最優先通貨
**FDI**: 電子機器$31B、デジタル$16B(倍増)、China+1でASEAN向け中国FDI$37.3B
**デジタル**: GMV $300B突破、BCG予測$1T by 2030
**政治**: タイ選挙(2/8)Anutin勝利、ベトナム党大会(1月)To Lam再選、PH ASEAN議長
**Danantara**: 投資成長5.2%→8.5%目標、PT PMA資本金$150Kに引下げ、ニッケル外交
**気候**: GDP 35%が気候リスク、タイ洪水$16B被害、化石燃料80%依存

## 決定事項

1. research-neo4j拡充をRESVISED記事投稿より優先（リサーチ基盤→高品質記事の順序）
2. マルチロールEntity（company/organization/broker）は正当な区別として保持
3. ASEAN検索は10フェーズ反復方式（ギャップ特定→クエリ最適化ループ）

## アクションアイテム

- [ ] 記事ネタ7件から優先3本選定・執筆開始 (優先度: 高)
- [ ] REVISED状態9本のうち品質確認済みをnote.com投稿 (優先度: 中)
- [ ] 残存構造問題（orphan Facts 596件、news/blog未処理1174件）(優先度: 低)

## 次回の議論トピック

- 記事ネタの優先順位付け（読者需要×データ充実度×差別化）
- ASEANテレコム記事の構成検討（KG活用方法の設計）
- 週次レポート再開（3月分が全て未作成）

## セッション統計

| 指標 | 値 |
|------|-----|
| research-neo4j投入ノード | ~200+ |
| research-neo4j投入リレーション | ~6,000+ |
| Web検索フェーズ | 10 |
| コンサルソース数 | 24 |
| 新規Topic | 52 (MAG7 29 + マクロ11 + ASEAN 12) |
