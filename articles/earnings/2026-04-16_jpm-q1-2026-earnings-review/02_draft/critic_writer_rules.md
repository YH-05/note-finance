# Writer Rules 批評レポート — JPM Q1 2026 決算レビュー

**スコア**: 94 / 100
**判定**: PASS（軽微な指摘のみ）

## 主要チェック結果

| 項目 | 結果 | 備考 |
|---|---|---|
| タイトル完全一致 | PASS | H1・frontmatter ともに「【🇺🇸米株決算】JPMorgan Chase（JPM）Q1 2026 決算レビュー」 |
| §0 プレビュー公開URL | PASS | L25 に `https://note.com/kabushiki_labo/n/nc0427e9a06a1` を埋込済み |
| focus_points 4項目の順序一致 | PASS | §2.1 NII → §2.2 IB → §2.3 Card NCO → §2.4 Dimon マクロ、meta.yaml 順序と完全一致 |
| マークダウン表の画像化 | PASS | 決算ハイライト表は `images/table_highlights.png` として画像化、本文中にマークダウン表残存なし |
| 根拠データへのソースURL埋込 | PASS | EPS サプライズ、Markets Revenue 最高、NII 引き下げ、NCO率、$50B 開示、Warsh 支持等、主要数値すべてに出典リンクあり |
| frontmatter 完備 | PASS | title / article_id / category / symbol / fiscal_quarter / fiscal_year / market / earnings_date / announcement_time / as_of_date / status すべて充足 |
| closing-greeting.md 挿入 | PASS | L174 に snippet 本文一致 |
| disclaimer.md 挿入 | PASS | L178 に免責事項掲載 |
| 文字数（目標4000-5000, 最大5500） | PASS | 本文実質 約4,700字（URL・見出し除く）で範囲内 |

## 軽微な指摘（low severity）

1. **WR-CL001 (low)**: §4 株価反応の解釈で、earnings.md 推奨の `/generate-chart-image` による発表前後10営業日株価チャート画像が未挿入。文章ベースの記述のみ（-2点）。
2. **WR-FM001 (low)**: frontmatter の `symbol` が単数形だが meta.yaml は `symbols` 配列。スキーマ上どちらも許容だが、meta.yaml との整合性のため `symbols: [JPM]` とするのが望ましい（-2点）。
3. **WR-CC001 (low)**: `meta.yaml.type: earnings_review` が frontmatter 側に未反映（-2点）。

指摘 3件すべて low severity のため、publish 可能品質と判断。

出力ファイル: `/Users/yukihata/Desktop/note-finance/articles/earnings/2026-04-16_jpm-q1-2026-earnings-review/02_draft/critic_writer_rules.md`
