# 議論メモ: ASEAN テレコム規制分析 & ISAT カバレッジ開始ガイド

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j（KG）に蓄積されたASEANテレコムセクターのデータを活用し、2つの調査を `/ask-research-neo4j` スキルで実施。KGデータのみに基づく回答（外部検索・LLM知識不使用）。

## 議論のサマリー

### 調査1: テレコムセクターと国の制度の関係性

ASEAN各国のテレコム規制を5つの軸で横断分析:
1. **スペクトラム割当制度** — 国ごとに方式が大きく異なる（オークション/政府主導/低価格割当）
2. **外資規制** — フィリピン40%上限、シンガポール制限なし、ベトナムStarlink向け緩和等
3. **政治・政策環境** — Prabowo政権の接続目標、ミャンマー軍政下テレコム管理等
4. **Starlink参入と規制攻防** — 既存オペレーターのロビイング、中国ベンダー排除圧力
5. **データ主権・AI規制** — インドネシアのソブリンAI要件がISATに規制的モート提供

### 調査2: ISAT（Indosat Ooredoo Hutchison）カバレッジ開始ガイド

KG蓄積データの棚卸し:
- **Fact 59件、Claim 114件、FinancialDataPoint 50件超、Stance 15件、Source 25件**
- 4大投資テーマ: ARPU回復、AI Native TechCo、FibreCo売却、5Gスペクトラム
- 6フェーズ調査ガイドを策定（会社概要→財務→テーマ深掘り→バリュエーション→リスク→競合）

### Insight投入

5件のクロスカッティングInsightを抽出し、web-researchパイプライン経由でresearch-neo4jに投入:
1. ASEAN規制3類型分類（cross_entity_insight）
2. ISAT bearish viewの過小代表（data_gap_insight）
3. FibreCo政治リスク（risk_insight）
4. スペクトラム×FibreCo自然ヘッジ（financial_linkage_insight）
5. Starlink vs. 既存オペレーター規制攻防（thematic_pattern_insight）

**技術的決定**: neo4j_loaderがInsightノード未対応のため、Claim（claim_type: `*_insight`）として投入。`claim_type CONTAINS 'insight'` でフィルタ可能。

## 決定事項

1. **Insight投入方式**: web-researchパイプライン経由のClaim形式（claim_type: *_insight）を採用
2. **ISATカバレッジアプローチ**: 6フェーズ調査、KG既存データ活用→ギャップ補充の順序
3. **ASEAN規制分類フレームワーク**: 「投資促進型/収益化型/国家主導型」の3類型

## アクションアイテム

- [ ] ISAT bearish viewの補充（優先度: 高）— `/investment-research` でARPU持続性リスク、XLSmart価格競争を調査
- [ ] ISATバランスシート詳細調査（優先度: 高）— 債務満期構造、外貨建て債務比率
- [ ] FibreCoクロージング最新状況（優先度: 中）— Arsari Group/Northstar売却完了状況を `/research-enrichment` で取得
- [ ] テレコム規制機関EntityのKG追加（優先度: 低）— IMDA、MCMC、Kominfo/BRTIをEntity登録

## 次回の議論トピック

- ISATのInitial Report骨子の策定
- bearish view補充後のbull/bearバランス評価
- FibreCo売却完了後の資本配分シナリオ分析

## 参考情報

- KGのISATカバレッジは充実（アナリスト8社のStance、FY2022-FY2026E財務データ完備）
- Morgan Stanleyのみ Equal-weight（TP 2,175 IDR）、他7社 Buy/Overweight
- FibreCo EV: IDR 14.6T、IPO 2026年Q3予定
