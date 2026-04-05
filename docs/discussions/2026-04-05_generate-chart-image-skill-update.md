# 議論メモ: generate-chart-image スキル規約整備

**日付**: 2026-04-05
**参加**: ユーザー + AI

## 背景・コンテキスト

VZ記事（`articles/stock_analysis/2026-03-08_tech-to-high-dividend-vz/`）に登場する全企業（VZ, T, TMUS, NVDA, MSFT, QQQ）の株価チャートをyfinanceから取得し生成する作業を通じて、`/generate-chart-image` スキルのプロット規約の不整備が発覚した。

最初の生成チャートがスキルの規約（SKILL.md）と乖離していたため、規約を正式に整備・文書化した。

## 議論のサマリー

### 問題の経緯

1. 初回チャート生成時、SKILL.mdの冒頭100行のみ参照し、guide.mdを未読のまま独自スタイルでコーディング
2. 出典表記（"出典: Yahoo Finance"）・青系グラデーション・alpha=0.9 など全て規約外のスタイルになっていた
3. ユーザーから「出典のyfinanceは削除して」「このルールに従っていない、なぜか？」と指摘を受け、問題を認識

### 確立したスタイル規約

1. **出典禁止**: `fig.text()` による出典表記・`caption` フィールド使用を禁止。記事本文側でURLリンクとして引用する。
2. **単一ライン青統一**: `color="#2166AC"` または `#2563EB`、`alpha=1.0`、`linewidth=2.0`
3. **複数ラインの透過率**: `alpha=0.6`（60%）統一、`linewidth=1.0`、`marker=False`
4. **複数ラインの色**: `NOTE_LIGHT.palette`（別系統カラー: 青・赤・緑・黄・紫…）を先頭から順に使用。青系グラデーションは禁止（例外: 金利カーブなど順序系列のみ許可）

## 決定事項

1. チャート内への出典記載は一切禁止。記事本文側でURLリンクとして引用する。
2. 単一ラインチャートは常に青（`#2166AC`）で統一する。
3. 複数ラインチャートは `NOTE_LIGHT.palette` の別系統カラーで alpha=0.6 で描画する。
4. ブルー系グラデーションは順序性のある関連系列（年限別金利カーブ等）の例外用途のみとする。

## 完了したアクション

- [x] `SKILL.md` に共通ルール・単一ライン・複数ラインの節を追加（必須ルールとして明記）
- [x] `guide.md` を更新（独立系列→テーマパレット【デフォルト】、順序系列→グラデーション【例外】に再構成）
- [x] VZ記事の全チャート（8枚）を規約準拠で再生成
  - `stock_vz.png`, `stock_att.png`, `stock_tmus.png`, `stock_nvda.png`, `stock_msft.png`, `stock_qqq.png`
  - `stock_telecom_comparison.png`（VZ/T/TMUS比較・別系統カラー）
  - `stock_vz_vs_qqq.png`（VZ vs QQQ比較・別系統カラー）

## 参考情報

- チャートデータ取得: `quantsパッケージ` + yfinance（auto_adjust=True）
- `NOTE_LIGHT.palette` 配色: `#2166AC`(青), `#D6604D`(赤), `#1A9641`(緑), `#FDAE61`(黄), `#762A83`(紫)...
- 関連ファイル: `.claude/skills/generate-chart-image/SKILL.md`, `.claude/skills/generate-chart-image/guide.md`
