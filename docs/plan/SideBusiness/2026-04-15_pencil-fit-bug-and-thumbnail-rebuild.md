# 議論メモ: Pencil fit modeバグ回避とearnings記事サムネイル一括再生成

**日付**: 2026-04-15
**参加**: ユーザー + AI

## 背景・コンテキスト

TSLA Q1 2026 決算プレビュー記事の株価チャート（手書きの概略推移）が不正確だったことから始まった一連の作業。チャートを正しいスクリプト（`scripts/generate_earnings_chart.py`）で再生成する過程で、earnings記事サムネイルの企業ロゴが歪んで表示される問題（BLK のロゴ上方に縦棒が並ぶアーティファクト等）を発見。Pencil の `fill.mode: "fit"` のレンダリングバグであることを実測検証で特定し、回避策を実装。8社のロゴと 9 記事のサムネイルを全再生成した。

## 議論のサマリー

### 1. TSLAチャート修正

- 元のチャート: 手書きの「概略推移（参考値）」で実データではなかった
- まず yfinance で実データの週次終値チャートに差し替え
- ユーザー指摘: earnings専用の `scripts/generate_earnings_chart.py` を使うべき
- 反復: 期間1年→5年、アノテーション全四半期→直近4四半期、S&P500破線→実線

### 2. サムネイル ロゴ歪みの発見

- ユーザー指摘: BLK・NFLX サムネイルでロゴが歪んで見える
- 検証: BLK(6.9:1)/JPM(7.0:1)/NFLX(2.15:1) で発生、UNH(13:1)/TSLA(0.77:1) は問題なし
- 元ロゴ自体は無加工で正常 → Pencil 描画段階で歪みが入っている
- Pencil の 3 モード(`stretch`/`fill`/`fit`)を全て実測したが、`fit` でも極端なアスペクト比で縦方向ストレッチ的なアーティファクトが残ることを確認

### 3. 加工なしで貼れるか議論

- スキーマ上は `mode: "fit"` がアスペクト比保持のはず
- 実装上は壊れているため、原画像そのままでは無理
- 透明パディングで Logo Container 比率(1.2:1)に揃えれば「画像本体は無加工 + 余白追加だけ」で実質「そのまま貼る」に近い体験

### 4. 一括再生成

- 8社のロゴを `--pad-ratio 1.2` で再パディング
- 9記事のサムネイルを `mcp__pencil__batch_design` + `export_nodes` で全再生成
- 長社名（JPMorgan Chase & Co. / Taiwan Semiconductor）はテンプレ枠超過 → 短縮形（JPMorgan Chase / TSMC）で表示

## 決定事項

1. **ロゴパディング**: `scripts/fetch_company_logo.py` に `--pad-ratio FLOAT` と `_pad_to_aspect_ratio()` を追加。earnings サムネイル生成時は `--pad-ratio 1.2` を必須化（`SKILL.md` Step 2 に明記）
2. **TSLA決算チャート構成**: 期間 5 年（デフォルト）+ 直近 1 年（4 四半期）の決算日アノテーション
3. **S&P500線**: 累積リターンパネルで破線(`linestyle="--"`)を削除し実線で描画

## アクションアイテム

- [x] `--pad-ratio 1.2` を SKILL.md に必須化（高）→ `act-2026-04-15-pad-ratio-skill-doc`
- [x] 8社（BLK/JPM/TSM/GE/NFLX/TSLA/UNH/IBM）のキャッシュロゴを 1.2:1 に再パディング（高）→ `act-2026-04-15-logos-bulk-padded`
- [x] 9記事のサムネイル全再生成（高）→ `act-2026-04-15-thumbnails-9-rebuilt`
- [x] TSLA `chart_price_1y.png` を `generate_earnings_chart.py` で5年+直近4四半期+SP500実線で再生成（高）→ `act-2026-04-15-tsla-chart-real-data`
- [ ] 長社名 DISPLAY_NAME マップを `article-earnings-thumbnail` スキル内に正式実装（中）→ `act-2026-04-15-display-name-extend-jpm-tsm`

## 次回の議論トピック

- DISPLAY_NAME マップの実装方式（meta.yaml に `display_name` 追加 vs スキル内ハードコード）
- Pencil バグレポートを公式に提出するか
- 他カテゴリ（macro/stock_analysis 等）のサムネイルにも同様のロゴ歪みリスクがないか検証

## 参考情報

- 影響を受けるロゴアスペクト比の閾値: 約 2.15:1 〜 7:1（中間ゾーン）。13:1 等の極端な横長は細すぎて目立たず、縦長(<1:1)は問題なし
- パディング後のロゴサイズ例: BLK 960×139 → 960×800、TSLA 960×1242 → 1490×1242
- 短縮社名運用: 既存の `dec-2026-04-15-thumbnail-display-name-manual` 決定を踏襲
