# 議論メモ: earnings カテゴリ新設 + quants DB 連携

**日付**: 2026-04-05
**参加**: ユーザー + AI
**Discussion ID**: `disc-2026-04-05-earnings-category-creation`

## 背景・コンテキスト

quantsプロジェクト（`/Users/yukihata/Desktop/quants/`）で以下のデータパイプラインが稼働中:

- NASDAQ calendar から決算発表予定を取得
- 発表予定銘柄について Alpha Vantage / SEC EDGAR / yfinance で企業データ・財務データ・株価データを取得
- launchd で定期実行、NAS (`/Volumes/personal_folder/Projects/quants/data/`) に蓄積

ユーザーから「決算公表を控える企業についてのレポートを作成し、note.com に投稿するロジックを構築したい」という要望。既存の note-finance 側 5カテゴリ（macro_economy / stock_analysis / asset_management / investment_education / market_report）ではカバーできないため、新カテゴリの追加とワークフロー整備が必要。

## データソース調査結果

NAS `/Volumes/personal_folder/Projects/quants/data/sqlite/` の実態調査:

| DB | テーブル | 行数 / 銘柄数 | 用途 |
|---|---|---|---|
| nasdaq_calendar.db | nc_earnings_calendar | 381行（2026-03-30〜2026-04-17） | EPS予想・発表時間・会計四半期末 |
| sec_edgar.db | se_financial_statements | 355行 / 181銘柄 | 財務5指標（revenue/net_income/total_assets/total_liabilities/operating_cashflow） |
| yfinance.db | yf_daily_prices | 48,666行 / 199銘柄 / 1年 | 日次 OHLCV |
| alphavantage.db | av_earnings | 1,180行 / 17銘柄 | 過去EPSサプライズ履歴 |
| alphavantage.db | av_company_overview | 8銘柄 / 46カラム | 会社概要・セクター・PER・アナリストレーティング |

**判明事項**: `av_income_statements` / `av_balance_sheets` / `av_cash_flows` は 0 行。これは Alpha Vantage 無料枠（25 calls/day）の制限下で他の優先データに枠を振るため **意図的に未収集**。財務データは SEC EDGAR を優先使用する。

## 議論のサマリー

ユーザーから提示された方針:

1. `.env` の `DATA_DIR` を実データのある方（`/Volumes/personal_folder/Projects/quants/data`）に修正する（plist は別PC運用のため変更不要）
2. `av_income/balance/cashflow` の 0 行は意図的 → SEC EDGAR を財務データの優先ソースとする
3. カバーする銘柄範囲は**決算発表 3-5 日前**を優先（NASDAQ calendar DB から特定）
4. レポート観点は**決算プレビュー**に寄せる。発表後の振り返りではない
5. note カテゴリは `earnings` を新設
6. レポートテンプレートの詳細設計は今回保留（後で詳細設計）

## 決定事項

| # | Decision ID | 決定内容 |
|---|---|---|
| 1 | `dec-2026-04-05-earnings-category` | note.com金融記事に「earnings」カテゴリを新設し、許可カテゴリを 5 → 6 に拡大（macro/stock/asset/education/report/earnings） |
| 2 | `dec-2026-04-05-sec-edgar-priority` | 財務データは SEC EDGAR を優先使用し、AV income/balance/cashflow は参照しない |
| 3 | `dec-2026-04-05-earnings-coverage-scope` | earnings 記事は NASDAQ calendar から発表 3-5 日後の銘柄を特定して優先カバーする |
| 4 | `dec-2026-04-05-quants-datadir-fix` | quants の .env `DATA_DIR` を `/Volumes/personal_folder/Projects/quants/data` に修正 |
| 5 | `dec-2026-04-05-earnings-template-deferred` | earnings 記事の詳細レポートテンプレートは保留し、references/earnings.md は暫定スキャフォールドのみ |

## 今回の実装完了事項

### quants 側

- `.env`: `DATA_DIR` を `/Volumes/personal_folder/Projects/quants/data` に修正
  （`FRED_HISTORICAL_CACHE_DIR` も同様に修正）
- `uv run --env-file .env python -m market.pipeline --status` で正しい queue_stats を確認
  （av_earnings: 17/12/352、sec_edgar: 201/180、yfinance: 200/181）

### note-finance 側

| ファイル | 変更内容 |
|---|---|
| `articles/earnings/` | ディレクトリ新設（`.gitkeep`） |
| `.claude/commands/article-init.md` | カテゴリ選択肢（8番目）、シンボル/決算日/期間入力、デフォルト値（earnings_preview / intermediate / 4000字）追加 |
| `.claude/commands/article-research.md` | earnings ルーティング、quants DB 連携セクション追加（NASDAQ calendar + SEC EDGAR + yfinance + AV earnings/overview） |
| `.claude/commands/article-draft.md` | カテゴリリストに earnings 追加 |
| `.claude/commands/article-full.md` | `--category` 説明・推奨設定テーブル更新 |
| `.claude/skills/finance-article-writer/SKILL.md` | 対象カテゴリ・参照ファイル表に earnings 追加 |
| `.claude/skills/finance-article-writer/references/earnings.md` | 暫定スキャフォールド作成（文字数 4000-5000字、データソース優先順位、セクション構成案、中立性ルール、チェックリスト） |

### メモリ更新

- `feedback_no_experience_articles.md`: 5 → 6 カテゴリに更新
- `project_kabushiki_labo_categories.md`: 株投資ラボ 5 → 6 カテゴリに更新
- `MEMORY.md`: 対応エントリ更新

## アクションアイテム

| # | Action ID | 内容 | 優先度 |
|---|---|---|---|
| 1 | `act-2026-04-05-001` | earnings 記事のレポートテンプレート詳細設計（セクション構成・文字数・フロー・決算プレビュー観点の論点整理）を実施し、references/earnings.md を本設計版に更新 | 高 |
| 2 | `act-2026-04-05-002` | article-research の earnings フロー用に、quants SQLite DB から発表 3-5 日後銘柄のプレビュー用データを取得するヘルパースクリプト/スキル整備 | 高 |
| 3 | `act-2026-04-05-003` | テンプレート確定後、NASDAQ calendar から 3-5 日後の決算銘柄を1本選定し、`/article-full --category earnings` で初回記事を試作 | 中 |
| 4 | `act-2026-04-05-004` | `/Volumes/personal_folder/Quants/data/sqlite/nasdaq_calendar.db`（.env 修正前の副作用で生成された空DB）を trash/ に移動 | 低 |
| 5 | `act-2026-04-05-005` | topic-discovery スキルが earnings カテゴリをトピック候補生成時に考慮するよう更新（NASDAQ calendar ベースのトピック提案） | 中 |

## 次回の議論トピック

1. **earnings レポートテンプレート詳細設計**
   - セクション構成の確定（発表概要 / 過去実績 / EPS サプライズ履歴 / 株価モメンタム / 注目ポイント / リスク / まとめ）
   - 文字数ターゲット（暫定 4000-5000字）の妥当性
   - 決算プレビュー特有の中立性ルール（「ビート見込み」「ミス可能性」等の予測断定禁止）の具体化
   - サプライズ履歴・モメンタム・アナリストコンセンサスなど、どのメトリクスを一軸で整理するか

2. **銘柄選定ロジック**
   - 3-5日前銘柄のうち、どの基準で記事化対象を絞るか（時価総額 / 出来高 / アナリストカバレッジ / セクター分散 等）
   - 1日あたりの投稿本数、曜日分散

3. **quants DB → note-finance ブリッジ**
   - article-research の earnings フロー用にヘルパースクリプトを新設するか、investment-research スキルに統合するか

## 参考情報

- quants pipeline CLI: `uv run --env-file .env python -m market.pipeline --status`
- CollectionQueue 優先度計算: `priority = max(0, 30 - |days_until_earnings|)`
- SEC EDGAR 経由の財務5指標: revenue, net_income, total_assets, total_liabilities, operating_cashflow

## 保存先

| リソース | パス |
|---|---|
| note-neo4j Discussion | `disc-2026-04-05-earnings-category-creation` |
| note-neo4j Decision | `dec-2026-04-05-earnings-category`, `dec-2026-04-05-sec-edgar-priority`, `dec-2026-04-05-earnings-coverage-scope`, `dec-2026-04-05-quants-datadir-fix`, `dec-2026-04-05-earnings-template-deferred` |
| note-neo4j ActionItem | `act-2026-04-05-001` 〜 `act-2026-04-05-005` |
| ドキュメント | `docs/plan/2026-04-05_earnings-category-creation.md`（このファイル） |
