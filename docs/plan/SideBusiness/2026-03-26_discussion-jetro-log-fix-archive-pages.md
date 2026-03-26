# 議論メモ: JETRO スクレイパー ログ修正 & --archive-pages CLI追加

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

`disc-2026-03-23-jetro-scraping-test` の「次回トピック」のうち archive_pages 実運用に向けた準備として実施。
前回テストで RSS / include-content / Playwright の3モード動作確認は完了済み。
今回は2点の問題を解消した。

## 議論のサマリー

### 1. ログ出力バグの発見と修正

**症状**: `uv run python scripts/scrape_jetro.py` を実行しても出力が何もない（exit code 0）

**原因**:
- `_logging.py` の `_ensure_basic_config()` がモジュールロード時に `structlog.configure(processors=[..., wrap_for_formatter], wrapper_class=stdlib.BoundLogger)` で正しく設定
- その後 `main()` が `structlog.configure(wrapper_class=make_filtering_bound_logger(...))` を呼び、`wrapper_class` のみ上書き
- `ProcessorFormatter` 経由の processor chain と `make_filtering_bound_logger` が矛盾し、ログが一切出力されなくなる

**修正** (`scripts/scrape_jetro.py`):
```python
# 変更前
logging.basicConfig(level=...)
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(...))

# 変更後
level = getattr(logging, args.log_level, logging.INFO)
logging.getLogger().setLevel(level)
```

### 2. --archive-pages オプションの追加

**背景**: `collect_news(archive_pages=N)` のロジックは実装済みだったが CLI から指定できなかった

**追加したオプション**:
```
--archive-pages N   地域・分析レポート／調査レポート／ビジネス短信の
                    アーカイブページを N ページ分クロールする（1ページ≒30件）。
                    --regions の指定が必須。Playwright を使用。
```

**利用例**:
```bash
# インドネシアの地域・分析レポート等を3ページ分（約90件）取得
uv run python scripts/scrape_jetro.py --regions id --archive-pages 3

# カテゴリクロール（最新分）＋アーカイブ（過去分）を同時に
uv run python scripts/scrape_jetro.py --categories world --regions id --archive-pages 5 --max-articles 500
```

**アーカイブ対象URL**:
- 地域・分析レポート: `https://www.jetro.go.jp/areareportstop/asia/idn/areareports/`
- 調査レポート: `https://www.jetro.go.jp/reportstop/asia/idn/reports/`
- ビジネス短信: `https://www.jetro.go.jp/biznewstop/asia/idn/biznews/`

## 決定事項

1. **structlog競合はlogging.getLogger().setLevel()のみで解決**: `_logging.py` の設定を後から上書きしてはならない。ログレベル変更は stdlib の `setLevel()` で行う
2. **--archive-pages をCLIに追加**: `collect_news(archive_pages=N)` への橋渡しを実装。地域・分析レポート・調査レポートの過去分大量取得が可能になった

## アクションアイテム

- [ ] archive_pages 実運用テスト: `--regions id --archive-pages 3` を実行し content_type 分布を確認 (優先度: 高)
- [ ] _resolve_regions() のユニットテスト追加（TestResolveRegions クラス）(優先度: 中)
- [ ] 定期実行設定（macOS launchd）の設計・実装 (優先度: 中)

## 次回の議論トピック

- archive_pages 実運用テスト結果の確認
- NAS 保存パスの運用設計（パス構造、保持期間）
- 定期実行設定（macOS launchd .plist 作成）
- 日本株ニュース HTML スクレイパー計画への着手判断

## Neo4j 保存情報

- Discussion: `disc-2026-03-26-jetro-log-fix-archive-pages`
- Decision: `dec-2026-03-26-jetro-log-fix`, `dec-2026-03-26-archive-pages-cli`
- ActionItem: `act-2026-03-26-jetro-001`, `act-2026-03-26-jetro-002`, `act-2026-03-26-jetro-003`
- 前回 Discussion: `disc-2026-03-23-jetro-scraping-test` → `FOLLOWED_BY` → 今回
