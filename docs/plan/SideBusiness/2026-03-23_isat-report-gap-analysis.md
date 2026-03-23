# 議論メモ: ISAT銘柄推奨レポート データギャップ分析（第2回）

**日付**: 2026-03-23
**参加**: ユーザー + AI
**前回**: disc-2026-03-18-isat-research-gaps（構造的障壁診断）

## 背景・コンテキスト

research-neo4jのISAT(Indosat Ooredoo Hutchison)関連データを、銘柄推奨レポート執筆の観点から網羅的に診断。前回(3/18)の構造的障壁診断後、データは大幅に充実しており、レポート骨格の大部分は構築可能な水準に達している。

## 現在のデータ充実度

### 充実している領域

| カテゴリ | 件数 | 状態 |
|---------|------|------|
| Entity | 1 (main) | ticker/sector/industry/country設定済 |
| Facts | 31件 | 市場概要、AI TechCo、FibreCo、ARPU、スペクトラム等 |
| Claims | 38件 | 9社レーティング、ガイダンス、セクター見解、リスク |
| FinancialDataPoints | 60+件 | Revenue/EBITDA/NI/FCF/Capex/ARPU等 FY2021-FY2026E |
| Sources | 80+件 | 会社IR(1Q23-4Q25) + セルサイド + Web |
| Stances | 31件 | 10アナリストのレーティング時系列 |
| Competitors | 4社 | Telkomsel, Telkom, XL Axiata, XLSmart |
| Partners | 7社 | NVIDIA, Nokia, Ericsson, Cisco, Google, GoTo, BDx |
| Topics | 29件 | セクター、バリュエーション、AI、マクロ等 |

## 不足データ一覧

### P0: Critical（レポート骨格に必須）

1. **バランスシート絶対額** — 総資産・総負債・純資産・グロス有利子負債・現預金残高
   - ND/EBITDA(0.39x)はあるが絶対額なし
   - 5Gスペクトラム取得後のレバレッジ影響分析が不可能
   - 取得元: Financial Statements 4Q2025を再パース

2. **株価・時価総額・発行済株式数** — 現在株価、52週高値安値、発行済株式数
   - アナリストTP(2,175-3,300 IDR)の妥当性検証不可
   - PER/PBR/配当利回りの算出不可
   - 取得元: Bloomberg/Google Finance/Yahoo Finance

3. **EPS ヒストリカル** — FY2021-FY2025実績
   - FY2026Eの1点(178 IDR)のみ
   - PERバンド分析不可
   - 取得元: NI(既存)÷発行済株式数で算出可能（act-002に依存）

### P1: High（レポート品質向上に重要）

4. **マルチイヤー予測** — FY2027E-FY2028E Revenue/EBITDA/NI/EPS/FCF
   - 「2028年EBITDA倍増」ガイダンスの裏付けなし
   - DCF端末価値前のCF予測が組めない
   - 取得元: セルサイドレポートから抽出

5. **株主構成** — Ooredoo Group/CK Hutchison/インドネシア政府/浮動株比率
   - ガバナンスリスク評価不可
   - 流動性分析不可
   - 取得元: Annual Report 2024/IDX filing

6. **ピアバリュエーション** — TLKM/EXCL(XLSmart)の主要財務指標
   - 相対バリュエーション分析不可
   - 取得元: セルサイドセクターレポート

### P2: Medium（あれば尚良）

7. **経営陣プロフィール** — CEO Vikram Sinha以外のC-suite情報
8. **マクロデータ** — インドネシアGDP/CPI/BI rate/IDR-USD推移
9. **セグメント別P&L** — Cellular/MIDI/Fixedのセグメント別EBITDA
10. **WACC構成要素** — 構造化DataPointとしての整理

## 決定事項

1. **P0-P2の優先度体系を採用** — P0の3項目が揃えばレポート骨格は構築可能
2. **BS取得を最優先** — Financial Statements 4Q2025の再パースから着手
3. **株価データはWebFetchで取得** — リアルタイム性が必要

## アクションアイテム

- [ ] [P0/Critical] BS絶対額取得: 総資産/負債/現預金/有利子負債 FY2023-FY2025 (act-2026-03-23-001)
- [ ] [P0/Critical] 株価・時価総額・発行済株式数・52週レンジ取得 (act-2026-03-23-002)
- [ ] [P0/Critical] EPS FY2021-FY2025実績を算出 (act-2026-03-23-003)
- [ ] [P1/High] FY2027E-FY2028Eコンセンサス予測をセルサイドレポートから抽出 (act-2026-03-23-004)
- [ ] [P1/High] 株主構成をAnnual Report/IDXから取得 (act-2026-03-23-005)
- [ ] [P1/High] ピア比較データ（TLKM/EXCL主要指標）取得 (act-2026-03-23-006)

## 次回の議論トピック

- P0データ取得完了後のレポート構成設計
- バリュエーションモデル（DCF vs マルチプル）の方針
- レポートのターゲット読者設定（note.com記事 vs 社内メモ）

## neo4j保存先

| ノード | ID |
|--------|-----|
| Discussion | disc-2026-03-23-isat-report-gaps |
| Decision | dec-2026-03-23-isat-data-priorities |
| ActionItems | act-2026-03-23-001 〜 006 |
