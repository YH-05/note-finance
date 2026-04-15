# 議論メモ: UNH Q1 2026 決算プレビュー — article-full 全工程完了

**日付**: 2026-04-15  
**参加**: ユーザー + AI

## 背景・コンテキスト

UnitedHealth Group（NYSE: UNH）の Q1 2026 決算プレビュー記事を `/article-full` で全工程（init→research→draft→critique→revision→publish）まで完了。

同日、BLK Q1 2026決算レビュー（Phase 2）、NFLX Q1 2026決算プレビュー（全工程）も完了しており、1日で3本のearnings記事を処理した。

## 記事情報

- **タイトル**: UnitedHealth Group（UNH）Q1 2026 決算プレビュー — 4月21日発表
- **カテゴリ**: earnings / earnings_preview
- **note.com下書き**: https://editor.note.com/notes/n361a30299cd5/edit/
- **批評スコア**: 68/100（修正前）
- **修正箇所**: 14箇所（CRITICAL×2、HIGH×6、MEDIUM×5、LOW×2）
- **公開推奨日**: 2026-04-20（決算発表前日）

## 議論のサマリー

### Phase 1〜2: リサーチ・初稿
- quants DB（nasdaq_calendar.db/sec_edgar.db/yfinance.db）からUNHデータを取得
- alphavantage.dbにUNHデータなし → Web検索で補完
- EPS予想の3ソース乖離を発見: GAAP $6.48（NASDAQ）/ adj $6.62（Yahoo）/ $7.27（Zacks）

### Phase 3: 批評で発見した重要問題

#### [CRITICAL] Billion単位の誤表記
- 日本語で `$109.6B` を「109.6億ドル」と書いてしまうミスが発生
- 正確には `1,096億ドル`（1B = 10億ドル ≠ 1億ドル）
- 同様に `$88.8B → 888億ドル`、`$89B → 890億ドル`
- **earnings/stock_analysis全カテゴリに影響する重要ルール**

#### [HIGH] CMS発表日と株価急騰日の混同
- CMS最終決定: **2026年4月6日（月）**
- UNH株急騰: **2026年4月8日（水）**（営業日2日後）
- 初稿では「4月8日のCMS発表」と誤記

#### [HIGH] Q3 2025 EPS予想値の誤り
- 初稿: 「予想2.74ドルをビート」
- 正確: 「予想2.81ドルをビート」

#### [HIGH] Hemsley氏の経歴誤記
- 初稿: 「創業期から会社を率いた」
- 正確: 「2006〜2017年にCEOを務めた」（創業者ではない）

### Phase 4: 修正版
- 全14箇所修正 → 文字数7,125字から3,845字へ削減（目標5,500字以内達成）
- MCR正式名称: Medical Care Ratio（Cost RatioはNG）
- フロントマター追加: `as_of_date`, `announcement_time: "BMO"`

## 決定事項

1. **Billion単位の日本語表記ルール確立**（dec-2026-04-15-billion-unit-japanese-notation）
   - `$X.XXB` → `X,XXX億ドル` で統一
   - 英語表記を残す場合は `$109.6B` または `1,096億ドル（$109.6B）` の形式

2. **UNH earnings preview の構成パターン**（dec-2026-04-15-unh-earnings-preview-structure）
   - 最重要指標: MCR（Q1は季節的に最低 = 元旦効果）
   - 次点: FY2026ガイダンス維持可否
   - 表構成: table_company_overview + table_mcr_trend + table_earnings_history + chart_price_1y

## アクションアイテム

- [ ] note.com下書き(n361a30299cd5)にカバー画像・ハッシュタグ設定して公開（4/20推奨） (優先度: 高)
- [ ] UNH Q1 2026決算発表(4/21寄前)後に実績レビュー記事を作成（MCR・ガイダンス実績確認） (優先度: 高, 期限: 2026-04-22)

## 次回の議論トピック

- 4月21日の決算発表後: MCR実績 vs 予想（88%以下でポジティブ / 90%超でネガティブ）
- UNH決算レビュー記事の作成タイミングと構成

## 参考情報（リサーチ結果）

### コンセンサス予想（2026-04-15時点）
- EPS (GAAP): $6.48 (NASDAQ), adj: $6.62 (Yahoo), $7.27 (Zacks)
- 売上収益: 約$110-111B
- FY2026ガイダンス: adj EPS ~$17.75（中央値）

### MCR予想レンジ
- 強気シナリオ: ~87%（季節的低点 + 不採算MA撤退効果）
- 弱気シナリオ: 90%超（冬季医療費増加継続）

### 重要イベント
- 2026-04-06: CMS 2027年MA報酬率+2.48%最終決定
- 2026-04-08: UNH株+9〜10%急騰（$314.19）
- 2026-04-21: Q1 2026決算発表（寄り前）

### earnings記事品質チェックポイント（新規追加）
1. Billion金額の単位確認（B→億ドルの10倍計算を必ず実施）
2. CMS等の政策発表日と市場反応日の区別
3. CEO経歴の正確性確認（創業者 ≠ 長期在任者）
4. Q1 MCRは季節的低点（元旦効果：免責額リセット後の受診抑制）
