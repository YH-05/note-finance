# 議論メモ: スクレイピング出力先のUGREEN NAS統一

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

プロジェクト内のスクレイピング出力先がローカル（`data/scraped/`）とNAS（`/Volumes/personal_folder/`）に分散していた。
UGREEN NAS（SMB: `//Yuki@100.70.5.35/personal_folder`）に統一して一元管理する。

### NAS接続状況（調査時点）

| マウント | パス | 種別 |
|---------|------|------|
| NeoData (APFS) | `/Volumes/NeoData` | ローカルディスク/USB |
| personal_folder (SMB) | `/Volumes/personal_folder` | UGREEN NAS |
| nas | `/Volumes/nas` | 空 |

## 議論のサマリー

### 調査フェーズ

1. **スクレイピング系スクリプト**の出力先を調査
   - `scrape_finance_news.py`: `/Volumes/personal_folder/finance-news/` → ローカル `data/scraped/`
   - `scrape_jetro.py`: `/Volumes/personal_folder/jetro-news/` → ローカル `data/scraped/jetro/`
   - `scrape_wealth_blogs.py`: ローカル `data/scraped/wealth/` のみ
   - YouTube Transcript CLI: `data_paths.get_path("raw/youtube_transcript")` 経由

2. **市場データ系スクリプト**の出力先を調査
   - `collect_market_performance.py`, `collect_interest_rates.py` 等
   - `_script_utils.resolve_output_dir()` → `data_paths.get_path(default_sub)` 経由

3. **中央パス管理**: `data_paths` パッケージ（`DATA_ROOT` 環境変数でオーバーライド可）

### 決定

ユーザーが明確に方針を指定:
- **スクレイピング**: `personal_folder/scraped/{ソース名}/`
- **市場データ**: `personal_folder/data/{カテゴリ}/`
- **全スクリプト**をNAS統一

## 決定事項

1. **スクレイピング出力先**: `/Volumes/personal_folder/scraped/{ソース名}/` に統一
   - `finance-news/`, `jetro/`, `wealth/`, `youtube_transcript/`
   - NAS未マウント時はローカルフォールバック

2. **市場データ出力先**: `/Volumes/personal_folder/data/{カテゴリ}/` に統一
   - `_script_utils.resolve_output_dir()` でNAS優先ロジック追加
   - NAS未マウント時は `data_paths.get_path()` にフォールバック

## 実装済み変更

| ファイル | 変更内容 |
|---------|---------|
| `scripts/scrape_finance_news.py` | DEFAULT_NAS_OUTPUT → `scraped/finance-news/` |
| `scripts/scrape_jetro.py` | DEFAULT_NAS_OUTPUT → `scraped/jetro/` |
| `scripts/scrape_wealth_blogs.py` | NASフォールバック追加（`scraped/wealth/`） |
| `scripts/_script_utils.py` | `resolve_output_dir` にNAS優先ロジック追加 |
| `src/youtube_transcript/cli/_cli_group.py` | NASフォールバック追加 |
| `tests/scripts/test_script_utils.py` | NAS対応にテスト更新 |

### テスト結果

- `data_paths`: 25 passed
- `_script_utils`: 5 passed
- `news_scraper` + `youtube_transcript`: 425 passed, 1 failed（既存バグ、今回の変更と無関係）

## NASディレクトリ構造

```
/Volumes/personal_folder/
├── scraped/
│   ├── finance-news/    # CNBC/NASDAQ ニュース
│   ├── jetro/           # JETRO 貿易ニュース
│   ├── wealth/          # 資産形成ブログ記事
│   └── youtube_transcript/  # YouTube字幕データ
├── data/
│   └── market/          # 市場パフォーマンスデータ
└── ...
```

## Neo4j ノード

- Discussion: `disc-2026-03-19-nas-output-unification`
- Decision: `dec-2026-03-19-002` (スクレイピング出力先NAS統一)
- Decision: `dec-2026-03-19-003` (市場データ出力先NAS統一)
