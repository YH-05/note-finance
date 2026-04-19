# 議論メモ: 2026-04-19 トピック発掘と防衛・航空宇宙記事の公開

**日付**: 2026-04-19
**参加**: ユーザー + AI
**種別**: 作業進捗の記録（project-discuss 「進捗を保存して」呼び出し）

## 背景・コンテキスト

2026年4月中旬の市場環境（S&P 500が史上初の7,000突破、イラン停戦ラリー、Q1 2026決算週入り）を踏まえ、新規記事トピックの発掘と即時執筆を並行実施。研究用 Neo4j (research-neo4j bolt://localhost:7688) およびメモ用 Neo4j (note-neo4j bolt://localhost:7687) はいずれも停止中だったため、Neo4j 関連の保存は `.tmp/` および `docs/plan/` にファイルで退避した。

## 今日のサマリー

### フロー1: `/topic-discovery` によるトピック提案

- Neo4j 未起動で Phase 0（KGマイニング）と Phase 5.3（Neo4j投入）をスキップ
- Tavily による Web検索 11クエリを実行
- 既存50記事のカテゴリ分布を集計: asset_management 15 / macro_economy 10 / earnings 10 / stock_analysis 9 / investment_education 5 / market_report 2
- Top 5 トピックを5軸評価でスコアリング:

| # | トピック | カテゴリ | スコア |
|---|---------|---------|-------|
| 1 | S&P500が7,000を超えた『停戦ラリー』 | market_report | 45 |
| 2 | 金価格$5,000時代が視野に | macro_economy | 44 |
| 3 | 防衛・航空宇宙の『地政学プレミアム』 | stock_analysis | 42 |
| 4 | ビットコイン現物ETF復活フロー | investment_education | 41 |
| 5 | インド株 最速8ヶ月の資金復帰 | stock_analysis | 40 |

- 保存: `.tmp/topic-suggestions/2026-04-19_0958.json` / `data/topic-history/suggestions.jsonl`

### フロー2: `/article-full` による #3 防衛記事の全工程実行

- トピック: 防衛・航空宇宙セクターの地政学プレミアムを分解する
- Phase 1: フォルダ作成 `articles/stock_analysis/2026-04-19_defense-aerospace-geopolitical-premium/`
- Phase 2: Tavily 10クエリで GE/RTX/LMT/NOC/ITA/PPA/マクロを収集 (ソース18件、Key Facts 18件)
- Phase 3: 初稿 8,130字生成
- Phase 4: 4エージェント並列批評（fact 78/compliance 40 FAIL/readability 72/structure 82）→ revised_draft 7,333字
  - コンプライアンス critical 対応（投資助言表現除去・標準免責/挨拶差し替え・禁止記号削除）
  - 4社比較表と ITA/PPA 比較表を画像化（`/generate-table-image`）
- Phase 5: note.com 下書き投稿成功 → `https://editor.note.com/notes/nee09a9b15580/edit/`
- `03_published/article.md` にコピー、`meta.yaml` 更新

## 決定事項

1. **今後の記事候補は上位5件で確定**（残り #1 / #2 / #4 / #5）。優先順位は note.com 上の反応を見てから再評価する。
2. **Neo4j 未起動時のフォールバック運用を実証**: Neo4j が停止していても、`/topic-discovery` と `/article-full` は `.tmp/` + `docs/plan/` への退避で完走できることを確認。復旧後は `.tmp/research-input/article-research-defense-aerospace-20260419.json` と `.tmp/research-input/` 配下の JSON を `emit_research_queue.py --command web-research` で後から投入する。
3. **`/generate-table-image` の列数上限は3列**。4列以上のテーブルは「項目 / メトリクス群1 / メトリクス群2」の3列に集約する運用で今後も統一。

## アクションアイテム

- [ ] (優先度: 中) Neo4j 起動後、research-neo4j に今日の Web 調査結果を投入
  - 入力: `.tmp/research-input/article-research-defense-aerospace-20260419.json`
  - 手順: `uv run python scripts/emit_research_queue.py --command web-research --input <file>` → `/save-to-research-graph`
- [ ] (優先度: 中) Neo4j 起動後、`/topic-discovery` 2026-04-19 セッションも同様に投入
  - 入力: `.tmp/topic-suggestions/2026-04-19_0958.json` から入力 JSON を構築
- [ ] (優先度: 中) note.com で下書き `nee09a9b15580` を確認・カバー画像設定・公開
- [ ] (優先度: 低) トピック #1 (S&P 7000 マーケットレポート) の着手判断。市場が連続最高値を更新中なら今週中に執筆、調整入りなら延期。
- [ ] (優先度: 低) トピック #2 (金$5000) の早期着手検討。macro_economy カテゴリの強化として有力。

## 次回の議論トピック

- 防衛記事公開後の読者反応（スキ数・PV）を踏まえた「金融＋地政学」ジャンル継続の可否
- market_report カテゴリ（残り 2本）を定期化するかのペース設計
- Neo4j の起動/停止ポリシー（アドホック vs 常時運用）と代替運用ルートの明文化

## 参考情報

- 今週の市場文脈: S&P500 4/15に7,000、4/17に7,100突破。イラン停戦期待が主ドライバー
- Trump FY27予算 $1.5兆 (Defense $1.1兆) が構造的な防衛テーマ
- RTX Q1 2026決算は 2026-04-22（火）に発表予定
