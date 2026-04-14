# 議論メモ: 原油$200×XLE 記事 — article-full 全工程完走

**日付**: 2026-04-14
**参加**: ユーザー + AI

## 背景・コンテキスト

/topic-suggest → /topic-discovery でトピック発掘 → /article-full で全工程（research → draft → critique → revision → publish）を完走。stock_analysis カテゴリの最新ワークフロー実地検証を兼ねた。

## セッションの流れ

1. **/topic-suggest**: 既存38記事の分布と RSS/Reddit 調査 → 3候補
2. **/topic-discovery**: KG 既存データ + Web 8件検索 → 5候補スコアリング、トップは「原油$200×XLE」(48点)
3. **/article-init**: `articles/stock_analysis/2026-04-14_oil-200-xle-strategy/` 作成
4. **/article-full**: 以下のフェーズを段階実行、各 HF ゲートでユーザー承認
   - Phase 2 Research: Web 8検索でギャップ解消 → KG に Source 12 / Fact 12 投入
   - Phase 3 Draft: 初稿 9,511字（戦略 A〜D 全4型収録）
   - Phase 4 Critique/Revision: **91/100**、優先修正5件全反映 → 9,274字
   - Phase 5 Publish: 表画像2枚生成 → note.com 下書き投稿成功

## 決定事項

1. **$200シナリオは「テールリスク」として明示的に位置付ける** — Goldman $98 / Citi $150 を一次根拠とし、$200 は複合条件達成時の到達点として提示。投資銀行の正式ベースケースとして扱わない
2. **stock_analysis 記事の文字数基準は 8,000〜10,000字を運用基準として確定** — 今回は 9,274字で範囲内通過
3. **戦略提示は A〜D の4型セットで標準化** — XLEコア / E&P集中 / USO戦術 / ヘッジ、それぞれ「特徴・想定配分・ねらい・留意点」を必須項目とする
4. **マークダウン表は `/generate-table-image` で画像化し、列数上限は3列** — 上限超過時はティッカー+企業名を1列に結合する運用で対応

## アクションアイテム

- [ ] note.com 下書きにカバー画像とハッシュタグを設定して公開 (優先度: 高)
- [ ] `/x-post-generator` で X 投稿文を生成 (優先度: 中)
- [ ] `/generate-image-prompt` でサムネ用AIプロンプト生成 (優先度: 中)
- [ ] 4/21 WTI 先物期日後のフォローアップ記事を検討 (優先度: 中)
- [ ] research-neo4j の XLE 関連 FinancialDataPoint 整備（YTDリターン・AUM・分配金）(優先度: 低)

## 次回の議論トピック

- 原油フォローアップ記事の焦点（期日後のスプレッド推移 vs OPEC+増産の実効性）
- エネルギーセクター以外の関連銘柄（航空・運輸ショート視点）への派生記事

## 参考情報

- note 下書き: https://editor.note.com/notes/n3f93dbbc0a7f/edit/
- 記事ルート: `articles/stock_analysis/2026-04-14_oil-200-xle-strategy/`
- 批評スコア: 91/100（writer_rules 94 / compliance 95 / fact 92 / data 90 / structure 88 / readability 87）
- KG 投入: Source 12件・Fact 12件・Entity 13件・Topic 3件
