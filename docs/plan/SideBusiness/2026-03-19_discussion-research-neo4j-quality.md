# 議論メモ: research-neo4j グラフDB品質評価と改善

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j (bolt://localhost:7688) のグラフDBとしてのクオリティを評価。
AIがこれを使って創発的に投資仮説を構築できる段階にあるかを検証した。

## 初期評価（Before）

| 観点 | スコア | 問題点 |
|------|--------|--------|
| スキーマ設計 | 8/10 | 優秀 |
| データ量 | 3/10 | PoC段階 |
| 接続密度 | 4/10 | 薄い |
| 時間的深度 | 2/10 | ニュース4日分のみ |
| カバレッジ幅 | 3/10 | インドネシア通信に偏重 |
| AI仮説構築 | 3/10 | 使える段階ではない |

**致命的ギャップ**:
1. ニュース683件がわずか4日間のスナップショット
2. Entity間ビジネス関係33本（190 Entityに対して極めて疎）
3. 財務データ175dpがインドネシア通信1セクターのみ
4. Claim→Entityリンク率55.3%
5. Author/Stanceが9件のみ

## 実行した6施策

### P0: Claim→Entity紐付け（直接Cypher実行）
- 33社/機関を新規Entity化（Federal Reserve, Samsung, Netflix等）
- 文字列マッチ + ticker + alias で紐付け
- 結果: 55.3% → 64.4%（+92リンク）、ABOUT関係 688→1,501

### P0: ニュース収集（バックグラウンドエージェント）
- RSS経由で55件の新規ニュース取得
- 時間範囲: 4日 → 53日（2026-01-26 ~ 2026-03-19）
- マクロ/エネルギー/AI/株式市場をカバー

### P1: SEC Edgar MAG7財務データ（バックグラウンドエージェント）
- 7社全て投入: AAPL(18dp), MSFT(14dp), GOOGL(18dp), AMZN(16dp), META(18dp), NVDA(19dp), TSLA(17dp)
- PL/BS/CF/Profitability メトリクス完備
- FiscalPeriod正規化によるクロスカンパニー比較対応

### P1: Author/Stance抽出（バックグラウンドエージェント）
- PDFレポート解析で6新規Author + 65新規Stance
- ISAT IJ: 12アナリスト、39 Stance（Buy 10 / Neutral 1 / Suspended 1）
- TLKM IJ: 9アナリスト、34 Stance
- レーティング変更追跡: BofA Neutral→Buy、Citi Buy→Suspended等

### P2: Entity間関係抽出（バックグラウンドエージェント）
- CO_MENTIONED_WITH + Claimコンテンツ分析
- +58新規ビジネス関係（COMPETES_WITH+29, CUSTOMER_OF+14等）
- 代表例: Google↔Microsoft(Cloud/AI), OpenAI→Nvidia(GPU顧客), Amazon→Anthropic(投資)

### P2: TREND + トピックネットワーク（直接Cypher実行）
- TREND +2（既存データでの隣接期間が限定的）
- SHARES_TOPIC +10,792（Entity横断発見性の飛躍的向上）
- claim_typeベースの自動トピックタグ付け

## Phase 2: US Telecom 4社のSEC 10-K包括投入

### 対象企業と投入データ

| 企業 | DataPoints | Facts | Claims | Revenue | FCF |
|------|-----------|-------|--------|---------|-----|
| AT&T (T) | 23 | 15 | 7 | $101B | $19.4B |
| Verizon (VZ) | 22 | 10 | 8 | $113B | $20.5B |
| T-Mobile (TMUS) | 19 | 14 | 7 | $58B | $10.3B |
| Comcast (CMCSA) | 25 | 12 | 7 | $124B | $21.9B |

### 投入データの種類
- **財務データ**: PL/BS/CF/Margins/KPI + セグメント別revenue
- **ビジネス内容**: 各社のセグメント構成、戦略、差別化要素
- **リスク要因**: 競争、規制、サイバーセキュリティ（VZ: Salt Typhoon）、コードカッティング
- **経営コメント**: 5G+Fiber収束、Un-carrier、FWA、Peacock成長等

### グラフ構造の追加
- Nokia/Ericsson（機器ベンダー）をEntityとして追加
- CUSTOMER_OF: US/ASEAN carrier → Nokia/Ericsson
- COMPETES_WITH: US 4社相互 + CMCSA↔Disney/Netflix
- SUBSIDIARY_OF: NBCUniversal/Sky/Peacock → CMCSA
- Topic: "US Telecom", "Global Telecom Comparison"

### リレーション正規化
エージェント間で異なるリレーション名（FOR_ENTITY, REPORTED_BY, REPORTED, IN_PERIOD, SOURCED_FROM）を
KG v2スキーマ標準（RELATES_TO, FOR_PERIOD, HAS_DATAPOINT）に統一。

## 最終評価（After）

| 観点 | Before | After |
|------|--------|-------|
| スキーマ設計 | 8/10 | 8/10 |
| データ量 | 3/10 | 5/10 |
| 接続密度 | 4/10 | 7/10 |
| 時間的深度 | 2/10 | 3/10 |
| カバレッジ幅 | 3/10 | 6/10 |
| AI仮説構築 | 3/10 | 5.5/10 |

### 数値変化

| 指標 | Before | After |
|------|--------|-------|
| 総ノード | 3,425 | ~3,900 |
| 平均次数 | 3.77 | 10.19 |
| Entity | 190 | ~235 |
| FinancialDataPoint | 175 | ~384 |
| Stance | 9 | 74 |
| ビジネス関係 | 33 | ~120 |
| ABOUT | 688 | ~1,500 |
| SHARES_TOPIC | 682 | 11,474 |

## アクションアイテム

- [ ] **[高]** ニュース収集のcronジョブ化（週次RSS+published_at必須）
- [ ] **[高]** MAG7+テレコムの過去2-3年分SEC Edgarデータ追加でTREND本格稼働
- [ ] **[高]** AI投資仮説構築のE2Eデモ（テレコムセクターでグラフ探索→仮説生成→検証）
- [ ] **[中]** 残り319件の未リンクClaim: NLPベースEntity自動抽出パイプライン
- [ ] **[中]** VZ EBITDA投入漏れ修正、AT&T/TMUS subscriber_total補完

## 次回の議論トピック

- AI投資仮説構築の具体的なクエリパターン設計
- グラフ探索アルゴリズム（最短経路、コミュニティ検出）の活用
- セルサイドレポートの継続的取り込みパイプライン
