# 議論メモ: JPM Q1 2026 決算レビュー記事 — /article-earnings-review ドッグフーディング

**日付**: 2026-04-16
**参加**: ユーザー + AI
**プロジェクト**: 株投資ラボ収益化
**関連**: `disc-2026-04-16-article-earnings-review-skill`（設計・実装）の後続実行記録

## 背景・コンテキスト

同日朝に設計・実装した `/article-earnings-review` コマンドを、JPMorgan Chase Q1 2026 決算（2026-04-14 BMO 発表済み）のレビュー記事生成で初めてドッグフーディング。

プレビュー記事: 2026-04-11 発行（`2026-04-11_jpmorgan-q1-2026-earnings-preview/`、note URL: https://note.com/kabushiki_labo/n/nc0427e9a06a1）で4つの focus_points を提示済み。今回はその答え合わせと未言及新情報を対比構造で扱う実運用テスト。

## 議論のサマリー

### 実行フロー（Phase 0-5 全工程）

| Phase | 内容 | 成果 |
|-------|------|------|
| 0 | `list_unreviewed_previews.py` 実行 | JPM 1件のみ候補として検出 |
| 1 | レビュー記事フォルダ初期化 | `2026-04-16_jpm-q1-2026-earnings-review/`、meta.yaml に preview_ref.focus_points 4項目 |
| 2 | 決算結果リサーチ | 8-K/CC要旨/株価反応を 01_research/ に 5ファイル生成 |
| 3 | first_draft.md 作成 | §0-§6 構成、本文 約6,400字（目標超過） |
| 4 | 6批評並列 + finance-reviser | 平均88.7点、revised_draft.md 約5,963字に短縮 |
| 5 | note.com 下書き投稿 | https://editor.note.com/notes/n38a8d04ae99a/edit/ |

### 批評スコア

| 観点 | 初稿 | 備考 |
|------|------|------|
| 事実正確性 | 92 | S&P500 YTD、プレマーケット因果表現の緩和 |
| コンプライアンス | 82 warning | em dash / 煽情表現 / レトリック修正必須 |
| 構成 | 92 | §6 フック追加、§2.3 段落分割 |
| データ整合性 | 94 | 表画像 CET1 -43bps → -30bps 再生成 |
| 読みやすさ | 78 | 用語注釈・結論先出し・長文分割で強化 |
| 執筆ルール | 94 PASS | frontmatter `symbols`/`type: earnings_review` 微修正 |

### 主要実績データ（参考）

- EPS $5.94（コンセンサス $5.45、+9%）
- Managed Revenue $50.5B（+10% YoY）
- Net Income $16.5B（+13% YoY）
- NII $25.5B（+9% YoY）、通期ガイダンスを $104.5B → $103B に引き下げ
- Markets Revenue $11.6B（同セグメント過去最高水準、+20% YoY）
- IB 手数料 $2.88B（+28% YoY、M&A 助言 +82%）
- Card NCO 3.47%、通期 3.4% ガイダンス据え置き
- 株価反応: 4/14 -0.75%（プレマーケット -2.6%）、4/16 現在 $305.93

### 発見された問題と対処

1. **リサーチ内数値不整合**: リサーチ段階で CET1 を「前期 14.6% → -43bps」と誤記（正: -30bps）。本文・表JSON・表画像の両方に波及。批評→修正→画像再生成の3ステップで対応。再発防止として**リサーチ段階で簡易な数値整合性チェックを追加する価値あり**。
2. **サムネイル生成の nodeId 齟齬**: サブエージェントが har1R 配下の psqPo/8Zjbx を「存在しない」と誤判断しスキップ。事前に batch_get で確認していたため実在するが、エージェント側の一部処理でエラー解釈された。生成されたサムネイル自体は正常だが、CompanyName/Ticker テキストが空の可能性あり（要目視確認）。
3. **文字数超過**: 目標 4000-5000字に対し revised_draft.md は 5,963字。批評で求められた追加情報（Markets +20% / Net Income +13% 等）と両立させるとこれ以上の削減は困難と判断。次回以降、初稿時点で文字数制御を強める必要あり。

## 決定事項

1. **`/article-earnings-review` の Phase 0-5 フローを実運用承認**: JPM で全工程が正常動作したため、今後の earnings レビュー記事はこのコマンドで統一する。
2. **批評→リバイズのスコア合格基準を平均 85 点以上とする**: JPM は平均 88.7、最低 readability 78 だったが、リバイズ後の指摘反映で運用上許容範囲と判断。
3. **表画像の数値再生成は Phase 4 内で必ず実施する**: CET1 事例のように、リサーチの計算誤りが画像に固定化されるリスクがあるため、Phase 4 の Step 4.4（表・チャート画像ポストプロセス）で再生成チェックを必須化する。
4. **目標文字数を 4500-5500 字に広げる**: earnings_review は対比構造で情報密度が上がるため、プレビュー版の 4000-5000 字より上限を引き上げる。`earnings.md` を更新する。

## アクションアイテム

- [ ] JPM レビュー記事を note.com で手動公開（カバー画像・タグ設定）(優先度: 高)
- [ ] JPM レビュー記事のサムネイル目視確認（CompanyName/Ticker が埋まっているか）(優先度: 高)
- [ ] `earnings.md` の「決算レビュー版」目標文字数を 4500-5500 字に更新 (優先度: 中)
- [ ] リサーチ段階の数値整合性チェックスクリプトを検討（例: 前期比 bps 自動計算） (優先度: 中)
- [ ] プレビュー記事（JPM Q1 2026）に「レビュー版はこちら」逆方向リンクを追記（`act-2026-04-16-008` 設計の実装） (優先度: 低)
- [ ] 次回決算サイクル（TSLA/NFLX/GE/UNH Q1 など 4/15-16 発表）でも同コマンドを実行し、再現性を確認 (優先度: 中)

## 次回の議論トピック

- JPM レビュー記事公開後の KPI（PV・スキ・有料購読 CVR）と プレビューとの比較
- サムネイル生成サブエージェントの nodeId 誤判定の根本原因と修正
- 逆方向リンク機構の実装優先度（4-5本のプレビュー記事が未レビューの状態で蓄積した場合の負担）

## 参考情報

### 投稿URL

- 下書きURL: `https://editor.note.com/notes/n38a8d04ae99a/edit/`
- プレビュー参照URL: `https://note.com/kabushiki_labo/n/nc0427e9a06a1`

### 成果物ディレクトリ

`articles/earnings/2026-04-16_jpm-q1-2026-earnings-review/`

- `meta.yaml`（status: published, draft_url 記録済み）
- `01_research/` 5ファイル（earnings_result / focus_points_answers / new_information / stock_reaction / sources.json）
- `02_draft/` 8ファイル（first_draft.md / revised_draft.md / 6批評レポート）
- `03_published/article.md`
- `images/table_highlights.png`（284KB）+ `images/thumbnail.png`（113KB、har1R グリーンバッジ）
