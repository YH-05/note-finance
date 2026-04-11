# 議論メモ: JPMorgan Q1 2026決算プレビュー記事 — earningsワークフロー初完走

**日付**: 2026-04-11
**参加**: ユーザー + AI

---

## 背景・コンテキスト

JPMorgan Chase（JPM）のQ1 2026決算が2026年4月14日（火）寄り前（ET 6:45 AM）に予定されており、
4月11日に記事作成フルワークフローを実行した。

`earnings` カテゴリとして以下のワークフローを完走:
1. `/article-research` — quants SQLite DB（NASDAQ/SEC/yfinance/AV）+ web検索
2. `/article-draft` — finance-article-writer スキル（earnings.md）使用、表画像・チャート画像生成
3. `/article-critique` — full モード（5エージェント並列批評）
4. `/article-publish` — note.com 下書き投稿

---

## 議論のサマリー（セッション振り返り）

### リサーチフェーズ

- research-neo4j（port 7688）は未起動のためKG照会・投入をスキップ
- quants SQLite DBから EPS予想・財務データ・株価を取得
  - NASDAQ calendar: EPS $5.46
  - SEC EDGAR（FY2025): 売上$182.4B, 純利益$57.0B, 総資産$4.42T
  - yfinance: 現在株価 $309.87（4/11時点）
  - AV: バリュエーション（PER 14.71x, PBR 2.32x, 目標株価$337.75）
- web検索（Reuters, CNN, CNBC, NYT, Seeking Alpha）でDimon株主書簡・IBフィー動向を補完
- 収集ソース数: 11件

### ドラフトフェーズ

- 生成文字数: 7,994字（目標4,000字を大幅超過）
- 生成画像: 3枚
  - `table_jpm_overview.png` — 会社概要表（13行）
  - `chart_price_1y.png` — 1年株価チャート
  - `table_sector_comparison.png` — 主要6行比較表

### **重大バグ: NII単位誤り**

初稿で「純金利収入 $103B」が「103億ドル」と誤表記された。

- 誤り: 103億ドル（= $10.3 billion）
- 正しい: **1,030億ドル**（= $103 billion）
- 誤差: 10倍
- 発生箇所: セクション2・5・6の計3箇所、および費用ガイダンスも「105億ドル→1,050億ドル」

このバグは `finance-critic-fact` が `score: 62/fail` で検出。

### 批評フェーズ（full モード）

| 批評エージェント | スコア | ステータス |
|---------------|--------|-----------|
| finance-critic-fact | 62 | FAIL |
| finance-critic-compliance | 85 | WARN |
| finance-critic-structure | 78 | WARN |
| finance-critic-data | 80 | WARN |
| finance-critic-readability | 62 | FAIL |
| finance-critic-writer-rules | 85 | WARN |
| **総合** | **75** | — |

主な修正事項:
1. [CRITICAL] NII/費用の$Bを「X,000億ドル」形式に修正（3箇所+1箇所）
2. [HIGH] リスクシナリオ（セクション5）を箇条書きに変換
3. [HIGH] 株価リターンをリスト形式に変換
4. [HIGH] 「フィーマシン」→ヘッジ表現に修正
5. [MEDIUM] 文字数 7,994字→約4,900字に圧縮
6. [MEDIUM] まとめを番号付きリストに変換

### 投稿フェーズ

- note.com 下書き投稿完了
- **下書きURL**: https://editor.note.com/notes/nc0427e9a06a1/edit/
- 投稿ブロック数: 69（heading:12, paragraph:28, list_item:15, numbered:4, image:3, separator:7）

---

## 決定事項

1. **$X billion の日本語換算ルール確立**
   - 誤: `103億ドル` → 正: `1,030億ドル`
   - ルール: `$X B = X,000億ドル（X × 10億ドル）`
   - 今後の全earningsカテゴリ記事に適用

2. **earningsフルワークフローの実行可能性確認**
   - research → draft → critique → publish を1セッションで完走
   - quants DB + web検索 + 表画像 + チャート画像 + 批評5並列 すべて自動化

---

## アクションアイテム

- [ ] note.com下書きにカバー画像・ハッシュタグを設定して公開（4/13まで、決算発表4/14の前） (優先度: 高)
- [ ] research-neo4j起動後にKGデータを手動投入（.resolved.json 準備済み） (優先度: 中)
- [ ] earnings.md ライタールールに「$Bの日本語換算ルール」を追記 (優先度: 中)

---

## 次回の議論トピック

- 決算発表後（4/14）に実績vs予想の乖離を記録するアフターレポート記事の作成
- Q1 2026銀行セクター決算（BAC/WFC/C/GS/MS）の比較記事

---

## 参考情報

- 記事ディレクトリ: `articles/earnings/2026-04-11_jpmorgan-q1-2026-earnings-preview/`
- KG投入待ちファイル: `.tmp/graph-queue/web-research/gq-20260411000823-3321a96f.resolved.json`
- JPM Q1 2026 EPS予想: $5.44-5.46（YoY +7.18%）
- 2026年通期NIIガイダンス: $103B = 1,030億ドル（コンセンサス$100B = 1,000億ドルを上回る）
- 決算発表日: 2026-04-14 寄り前（ET 6:45 AM）
