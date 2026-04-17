# 議論メモ: 新NISA1800万円 最速5年vs15年分散 記事作成

**日付**: 2026-04-16
**ステータス**: 完了（note.com下書き投稿済み）

## 記事情報

| 項目 | 内容 |
|------|------|
| タイトル | 新NISA1800万円、最速5年vs15年分散｜勝つのはどっち？ |
| カテゴリ | asset_management |
| フォルダ | `articles/asset_management/2026-04-16_nisa-1800man-5years-vs-15years/` |
| 下書きURL | https://editor.note.com/notes/n415113cab7e1/edit/ |
| 文字数 | 約5,800字 |
| コミット | `f8c9d18` |

## 決定事項

1. **結論構成**: 「統計的に5年集中が優位だが、条件付き」という両面提示を採用
2. **シミュレーション前提**: 年率5%/6%/7%の3パターン、年末一括投資、30年後比較
3. **主要エビデンス**: Vanguard 2012（LSI勝率66%）、Morningstar Mind the Gap（行動バイアス年率1.2%損失）
4. **読者向け自己診断**: 4条件（生活防衛資金・家計耐性・下落耐性・投資期間）のチェックリスト形式
5. **タイトル短縮**: 32字（30-38字範囲内）に収める

## 生成ファイル

- `01_research/research.md` — 24ソース、234行のリサーチノート
- `02_draft/first_draft.md` — 初稿（約6,000字）
- `02_draft/revised_draft.md` — 修正版（em-dash除去、挨拶文・免責事項追加）
- `03_published/article.md` — 投稿版コピー
- `images/chart_final_asset_comparison.png` — 棒グラフ（5年集中vs15年分散）
- `images/chart_self_diagnosis_flow.png` — 自己診断4ステップ
- `images/table_comparison.png` — 30年後最終資産比較表
- `images/table_nisa_rules.png` — 新NISA制度パラメータ表

## 主要数値（記事内で使用）

| 項目 | 値 | ソース |
|------|-----|--------|
| LSI勝率 | 66%（米国100%株式） | Vanguard 2012 |
| 30年後差額（年率6%） | +2,016万円（+30.1%） | 自己計算 |
| 行動バイアスコスト | 年率1.2% | Morningstar Mind the Gap 2024 |
| MSCI ACWI期待リターン | 7.0%（USD） | J.P.Morgan 2026 LTCMA |
| コロナショック時オルカン | −33.8% | アルビノ |

## アクションアイテム

- [ ] note.comでカバー画像を設定
- [ ] note.comでハッシュタグ（#新NISA #資産形成 #一括投資 #ドルコスト平均法）を設定
- [ ] 公開ボタンで公開
- [ ] X投稿文を `/x-post-generator` で生成（任意）

## note-neo4j保存（未完了）

note-neo4j未起動のため、以下のノードは次回起動時に保存する:

- Discussion: `disc-2026-04-16-nisa-5y-vs-15y`
- Decision: `dec-2026-04-16-nisa-conditional-conclusion` — 条件付き結論構成の採用
- ActionItem: `act-2026-04-16-001` — note.com公開作業
