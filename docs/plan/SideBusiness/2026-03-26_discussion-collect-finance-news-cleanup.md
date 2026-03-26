# 議論メモ: collect_finance_news ワークフロー廃止

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

GitHub Issueを作成するワークフローが不要になったことを受け、`collect_finance_news` 系統のスクリプト・コマンド・スキルを廃止した。

## スクリプト構成の整理

調査の結果、金融ニュース関連スクリプトは以下の2レイヤーに分かれていた：

### 収集レイヤー（維持）
- `scrape_finance_news.py` — Web直接スクレイピング（CNBC/NASDAQ等）→ NASにraw JSON保存。launchd で6時間ごとに自動実行。`news_scraper` パッケージを使用。

### Issue作成レイヤー（廃止）
旧世代（モノリシック）:
- `collect_finance_news.py` — RSS読み込み→キーワードフィルタ→GitHub Issue作成（テーマ分類・Status設定なし）

新世代（セッション分離型）:
- `prepare_news_session.py` — RSS読み込み→日付フィルタ・重複チェック→session JSON生成
- `collect_finance_news_{index/stock/macro/sector/ai}.py` — session JSON読み込み→テーマ別フィルタ→Issue作成・Status設定

## 決定事項

1. **collect_finance_news 系統を廃止**
   GitHub Issue作成ワークフローが不要になったため、スクリプト6本・コマンド・スキルを `trash/collect_finance_news/` に移動。

2. **scrape_finance_news.py は維持**
   rawデータ収集（NASへのJSON保存）はIssue作成とは別レイヤーのため影響なし。

## 実施した変更

**trash/collect_finance_news/ に移動:**
- `scripts/collect_finance_news.py`
- `scripts/collect_finance_news_index.py`
- `scripts/collect_finance_news_stock.py`
- `scripts/collect_finance_news_macro.py`
- `scripts/collect_finance_news_sector.py`
- `scripts/collect_finance_news_ai.py`
- `.claude/commands/collect-finance-news.md`
- `.claude/skills/finance-news-workflow/`
- `.agents/skills/finance-news-workflow/`

**参照削除:**
- `scripts/__init__.py` — docstring
- `pyproject.toml` — `collect-finance-news` エントリーポイント
- `AGENTS.md` — automation パッケージ行
- `.claude/rules/development-process.md` — テーブル行
- `.claude/rules/subagent-data-passing.md` — 関連ファイル節
- `.claude/commands/generate-market-report.md` / `save-to-research-graph.md` / `emit-research-queue.md` — 参照行

## アクションアイテム

- [ ] `prepare_news_session.py` の用途を確認し、不要なら trash/ に移動（優先度: 低）
  テーマ別スクリプト（_stock/_macro/_sector/_ai）が廃止済みのため、セッション生成の用途が消失している可能性が高い。

## 次回の議論トピック

- `prepare_news_session.py` と `session_utils.py` の扱い（廃止 or 転用）
