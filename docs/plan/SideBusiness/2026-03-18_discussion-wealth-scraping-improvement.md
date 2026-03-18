# 議論メモ: Wealth Scraping 改善

**日付**: 2026-03-18
**参加**: ユーザー + AI

## 背景・コンテキスト

ユーザーから3点の要望:
1. zerohedge をスクレイピング対象に追加したい
2. marginalrevolution を除外したい
3. スクレイピングロジックが遅いため見直したい

事前調査で、プロジェクトには4層のスクレイピング基盤が存在することを確認:
- `news_scraper` (CNBC, NASDAQ)
- `scrape_wealth_blogs` (17サイト)
- `report_scraper` (16社の投資レポート)
- `company_scrapers` (AI投資リサーチ 10カテゴリ77社)

## 議論のサマリー

### スクレイピング全体像
プロジェクトの金融情報スクレイピングは非常に充実している。日本語ソース・マクロ経済データAPI・株価データの直接スクレイピングは未対応。

### パフォーマンス問題の分析
backfill モードの主要ボトルネック:
- 18サイトを完全逐次処理（並列化なし）
- monevator.com の rate limit が 240秒/記事
- デフォルト200記事 × rate limit → 膨大な所要時間
- sitemap パースも逐次

改善アプローチとして「ドメイン間並列化」をユーザーが選択。

## 決定事項

1. **zerohedge.com を追加 (v1.2)**
   - Rate limit: 3.0s
   - Backfill tier: B
   - RSS: `https://www.zerohedge.com/fullrss.xml`
   - Sitemap: `https://www.zerohedge.com/sitemap.xml`
   - URL パターン: `/markets/`, `/economics/`, `/geopolitical/`, `/commodities/`
   - 新テーマ "Macro & Markets" を追加（キーワード: macro, geopolitics, central bank, inflation 等）

2. **marginalrevolution は対応不要**
   - v1.1 (2026-03-17) で既に除外済み

3. **backfill モードのドメイン間並列化を実装**
   - `_BackfillState` クラスで共有状態管理
   - `_scrape_site_backfill()` でサイト単位の async 処理を分離
   - `asyncio.Semaphore` + `asyncio.gather` で同ティア内並列処理
   - `--concurrency` / `-j` CLI オプション追加（デフォルト: 4）
   - 見込み改善: 待機時間が約 1/4 に

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `src/rss/config/wealth_scraping_config.py` | zerohedge 追加（4つの辞書）、v1.2 changelog |
| `data/config/wealth-sitemap-config.json` | zerohedge サイト設定追加、v1.2 |
| `data/config/rss-presets-wealth.json` | zerohedge RSS プリセット追加、v1.2 |
| `data/config/wealth-management-themes.json` | "macro_markets" テーマ追加、v1.2 |
| `scripts/scrape_wealth_blogs.py` | `_BackfillState`, `_scrape_site_backfill()`, `--concurrency` オプション |

## テスト結果

- `tests/scripts/test_scrape_wealth_blogs.py`: **53 passed** (2.99s)
- dry-run 確認: zerohedge が B ティアに正しく認識
- config ロード確認: 18サイト、全フィールド正常

## アクションアイテム

- [ ] zerohedge の RSS URL (`fullrss.xml`) の実地動作確認 (優先度: 高)
- [ ] 並列化の本番実行でのパフォーマンス測定 (優先度: 高)
- [ ] 変更のコミット・PR作成 (優先度: 高)
- [ ] monevator (240s delay) の取り扱い検討（除外 or ティア降格）(優先度: 中)
- [ ] sitemap パース結果のキャッシュ導入検討 (優先度: 低)

## 次回の議論トピック

- 日本語金融ニュースソース（日経、Bloomberg Japan等）の追加可否
- wealth scraping の本番運用スケジュール設計
- 並列化後の実測パフォーマンスに基づく追加最適化

## 参考情報

- ZeroHedge: FeedSpot 2025年1位。市場・地政学のシニカル分析。ヘッジファンド界の定番。
- `data/rss_sources/general_finance.json` に ZeroHedge のエントリあり（RSS URL は空欄だった）
