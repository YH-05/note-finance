# 議論メモ: ASEAN Telecom セクター research-neo4j 情報ギャップ分析と補完

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

ISAT（Indosat Ooredoo Hutchison）およびテレコムセクターの投資分析を支援するため、research-neo4j の情報基盤を体系的に構築するセッション。alphaxiv MCP による学術論文の技術調査から開始し、8領域の情報ギャップを特定・解消した。

## セッションの流れ

### Phase 0: 技術動向投入（alphaxiv MCP）
- 衛星通信/NTN/O-RAN/AI for Telecom 等の学術論文 **22本** を投入
- 技術 Entity **20件**（LEO Satellite, NTN, RIS, JCAS, NFV/SDN 等）
- ISAT関連企業を **19社** に拡張（機器ベンダー、衛星、ASEANテレコム、タワー）
- 企業間リレーション構築（親子/競合/ピア/インフラ利用）

### ギャップ分析結果（8領域）
| 優先度 | 領域 | 投入前の状態 |
|-------|------|------------|
| P0 | 規制環境 | Source 0件（最大の弱点） |
| P0 | ASEAN マクロ経済 | インドネシアのみ |
| P1 | 個別企業財務 | IOH中心 |
| P1 | 政治リスク | 断片的 |
| P2 | スペクトラム割当 | 未整備 |
| P2 | デジタルサービス収益化 | 未整備 |
| P3 | タワー会社財務 | ノードのみ |

### P0: 規制環境 + マクロ経済（2エージェント並列）
**規制環境** (Source 20 / Fact 35 / Claim 14):
- インドネシア: Omnibus Law外資100%開放、1.4GHz FWAオークション完了
- タイ: True-DTAC合併でHHI 5000、MVNO全滅、NBTC機能不全
- フィリピン: PSA改正で外資100%、DITO急成長
- マレーシア: DNB 5G単一卸売モデル終了、U Mobile第2ネットワーク（Huawei）
- ベトナム: 3社国有、Viettel国産5G機器、Decree 13データローカライゼーション
- シンガポール: 5G SA 95%+、SIMBA-M1合併
- 横断: DEFA 2025/10合意、外資規制の国別スペクトラム

**マクロ経済** (Source 17 / Fact 60 / Claim 10):
- ベトナム: GDP 8.02%（ASEAN最高）、FDI $38.4B
- フィリピン: 人口1.158億（最若年）、OFW $38.3B
- マレーシア: DNB 5G 82.4%カバレッジ
- タイ: GDP 2.2%（ASEAN最低）、デフレ型ARPU圧縮
- シンガポール: デジタル経済GDP比18.6%

### P1: 企業財務 + 政治リスク（2エージェント並列）
**企業財務** (Source 9 / Fact 85 / Claim 24):
| 企業 | EV/EBITDA | 注目ポイント |
|------|-----------|-------------|
| Telkom Indonesia | 5.0x | EBITDA 50%、InfraCo分離触媒 |
| AIS | 8.1x | NP +54%、5G 1800万加入 |
| True Corp | 6.9x | 黒字転換、市場シェア51% |
| PLDT | 4.9x | EBITDA 52%、Maya黒字化 |
| Globe | 5.5x | EBITDA 53%、GCash持分利益PHP 6.1B |
| Singtel | 9.1x | Associate S$2.5B、S$2B自社株買い |

**政治リスク** (Source 20 / Fact 35 / Claim 30):
- 最重要: タイ政治麻痺(0.9)、SCS(0.9)、ASEAN機器二極化(0.9)
- インドネシア: Danantara配当圧力(0.8)、Starlink参入
- ベトナム: 最高成長機会(0.8)だがデジタルセキュロクラシー懸念

### P2: スペクトラム + デジタルサービス（2エージェント並列）
**スペクトラム** (Source 7 / Fact 42 / Claim 8):
- インドネシア: 1.3 MHz/百万人（シンガポールの1/86）、C-band未割当
- ベトナム: GSMA best practice（90%値引+15% CAPEX補助金）
- タイ: C-band未割当で5G競争力懸念
- ID 2026年 700MHz/2.6GHzオークションが重要カタリスト

**デジタルサービス** (Source 17 / Fact 46 / Claim 10 / Entity 15):
- フィリピンのテレコ×フィンテックモデルがASEAN最良（GCash/Maya両方黒字）
- Singtelの隠れデジタル資産: STT GDC($10.9B) + Nxera($5.5B+) + NCS
- インドネシアテレコムはモバイルマネーでスーパーアプリに敗北
- DC市場にオーバービルドリスク（ハイパースケーラー$20B+直接投資）

### P3: タワー会社（1エージェント）
**タワー会社** (Source 28 / Fact 50 / Claim 11 / Entity 12):
| 指標 | Mitratel | Tower Bersama | Sarana Menara |
|------|---------|--------------|--------------|
| タワー数 | 40,102 | 23,892 | 35,400 |
| EBITDA margin | 82.7% | 85.5% | 84.0% |
| テナント比率 | 1.55x | 1.79x | 1.64x |
- TOWR 7.3x vs セクター平均9.8x（バリュエーションギャップ）
- MNO統合チャーンリスク vs 5G密度化による構造的需要

## 最終累計

| 項目 | 件数 |
|------|------|
| Source | 140 |
| Fact | 369 |
| Claim | 117 |
| Entity | 85 |
| Topic | 23 |

## 決定事項

1. alphaxiv MCPで技術論文22本を投入し、ISAT関連企業を19社に拡張
2. 8領域のギャップをP0-P3の優先順位で体系的に解消
3. 7つのリサーチエージェントを並列実行し全領域を完了
4. research-neo4jにASEANテレコム投資分析基盤が完成

## アクションアイテム

- [ ] **[高]** research-neo4j の AuraDB バックアップ実行（大量投入分を含む）
- [ ] **[高]** ISAT Initial Report 執筆（research-neo4j のデータを活用）
- [ ] **[中]** ASEAN Telecom 比較表の作成（6カ国×主要指標マトリクス、画像生成含む）
- [ ] **[中]** セルサイドレポートの PDF 変換・KG 投入で財務データ補強
- [ ] **[低]** 定期更新フロー構築（マクロ指標・決算データの四半期更新スキル化）

## 次回の議論トピック

- ISAT Initial Report の構成設計（equity-stock-research スキル活用）
- ASEAN Telecom 比較記事のフォーマット（note.com 向け）
- research-neo4j データの品質検証（重複・矛盾チェック）
