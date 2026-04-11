# 議論メモ: 決算シーズンの読み方フレームワーク — investment_education 全工程完走

**日付**: 2026-04-11
**参加**: ユーザー + AI

## 背景・コンテキスト

Q1 2026決算シーズン開幕（JPMorgan Chase が2026年4月14日にQ1決算発表予定）に合わせたタイムリーな投資教育記事を作成。
EPS・売上・ガイダンスの3軸スコアリングフレームワークを初心者投資家向けに解説する記事を全工程実行。

## 記事情報

- **タイトル**: 決算シーズンの読み方：EPS・売上・ガイダンス3軸スコアリングフレームワーク
- **カテゴリ**: investment_education
- **文字数**: 約9,790字（目標8,000〜10,000字）
- **下書きURL**: https://editor.note.com/notes/na706043c885d/edit/
- **公開日**: 2026-04-11投稿（note.com下書き）

## 実行ワークフロー

### Phase 1: リサーチ（12ソース）

- research-neo4j照会 → investment_educationカテゴリのKGデータなし（全ギャップ HIGH）
- Tavily Web検索で12ソース収集
- 主要ソース: SBI証券, moomoo, Investopedia, Forbes, Fund Garage, Money Plus, HEDGE GUIDE

### Phase 2: 初稿作成

- finance-article-writer → investment_education rules 適用
- 構成: はじめに → 3軸全体像 → 軸1(EPS) → 軸2(売上) → 軸3(ガイダンス) → CC → 株価反応 → 日本株比較 → FAQ → まとめ

### Phase 3: 批評（全工程 full mode）

6エージェント並列実行、総合スコア **75/100**

| 項目 | スコア |
|------|--------|
| コンプライアンス | 95/100 ✅ |
| 構成 | 82/100 |
| 読みやすさ | 78/100 |
| 事実正確性 | 78/100 |
| データ正確性 | 59/100 ❌ |
| ライター規約 | 59/100 ❌ |

### Phase 4: 修正（10件）

HIGH優先度修正:
- AMD コンセンサス $1.24→$1.32、Beat率 +23%→+16%、URL修正
- Snap の説明修正（「市場予想Miss・EBITDA -94%」追記）
- 「なぜ重要なのか」セクション追加（~350字）
- 「実践ガイド」3ステップセクション追加

MEDIUM優先度修正:
- 決算短信提出先「金融庁」→「東京証券取引所（TDnet）」
- Micron コンセンサス $9.00→約$8.6
- FAQ Q3 投資推奨表現を中立化
- データ期間注記追加

LOW優先度修正:
- まとめセクション400字以内に短縮
- 長段落を2文に分割

## 決定事項

1. **記事タイトル確定・下書き投稿完了**: 「決算シーズンの読み方：EPS・売上・ガイダンス3軸スコアリングフレームワーク」。JPMorgan 4/14決算に合わせたタイムリーな切り口。note.com下書き投稿済み。
2. **批評スコア75/100で承認**: 全HIGH項目修正後に承認。下書きURLは https://editor.note.com/notes/na706043c885d/edit/

## アクションアイテム

- [ ] note.comでカバー画像・ハッシュタグを設定して公開する（優先度: 高）
- [ ] research-neo4jにリサーチデータを投入する（`/save-to-research-graph`）（優先度: 中）
- [ ] X投稿文を生成して配信する（`/x-post @articles/investment_education/2026-04-11_earnings-season-reading-guide/`）（優先度: 中）

## 参考情報

- `articles/investment_education/2026-04-11_earnings-season-reading-guide/` — 記事ディレクトリ
- `02_draft/revised_draft.md` — 修正版（note.com投稿済み）
- `03_published/article.md` — 公開アーカイブ
- `01_research/research_note.md` — 12ソースのリサーチノート
- `02_draft/critic.md` — 批評レポート（スコア詳細）
