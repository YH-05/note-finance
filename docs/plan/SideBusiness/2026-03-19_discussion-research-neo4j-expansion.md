# 議論メモ: research-neo4j拡充とnote記事ネタ収集

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

note記事執筆プロジェクトの進捗確認から、research-neo4jの拡充を優先する方針を決定。
- 記事17本中PUBLISHED 4本、REVISED 9本（投稿可能だが未投稿）
- research-neo4jはASEAN Telecomに偏重、MAG7/G7マクロのカバレッジゼロ
- Entity-Topic/Claim-Topic接続が全数孤立状態

## 実施内容

### Phase D: 構造品質改善

| 施策 | 結果 |
|------|------|
| D1: 重複Entityマージ | 28ノード削除、145リレーション移行、マルチロール5件保持 |
| D2: Entity→Topic接続 | 748リレーション作成、86% (302/351) 接続 |
| D3: Claim→Topic接続 | 5,846リレーション作成、70% (661/945) 接続 |

### Phase C: 新規セクター追加

| 項目 | C1: MAG7 | C2: マクロ |
|------|---------|----------|
| Source | 27 | 48 |
| Topic | 29 | 11 |
| Entity | 7 | 49 |
| Fact | 52 | 67 |
| RELATES_TO | 77 | 89 |

### 記事ネタ収集

7件の記事ネタ候補をresearch-neo4jに保存:

1. **MAG7のAI設備投資サイクル** — Amazon$200B, Meta$115-135B, Microsoft~$120B (stock_analysis)
2. **2026年3月FOMC分析** — FFレート据え置き、年内2回利下げ見通し (macro_economy)
3. **日銀利上げと円安の構造分析** — 春闘5.46%、USD/JPY 148-154レンジ (macro_economy)
4. **Nvidia Q4 FY2026決算深掘り** — 売上$68.1B(+73% YoY) (stock_analysis)
5. **クラウド3強の勢力図2026** — AWS vs Azure vs Google Cloud (stock_analysis)
6. **The Great Rotation** — MAG7→スモールキャップ (asset_management)
7. **ASEANテレコムセクター投資ガイド** — 6カ国主要オペレーター (stock_analysis)

## 決定事項

1. research-neo4j拡充を記事投稿より優先（リサーチ基盤→高品質記事の順序）
2. マルチロールEntity（company/organization/broker）は重複ではなく正当な区別として保持

## アクションアイテム

- [ ] 記事ネタ候補7件から優先3本を選定し執筆開始 (優先度: 高)
- [ ] REVISED状態9本のうち品質確認済みをnote.comに投稿 (優先度: 中)

## 次回の議論トピック

- 記事ネタの優先順位付け（読者需要×データ充実度×差別化）
- 残存する構造問題（orphan Facts 596件、news/blog Source未処理1,174件）
