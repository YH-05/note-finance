# 議論メモ: NASストレージ構造の再設計とデータ移行

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

金融ニューススクレイピングのデータが複数箇所に分散していた：
- NAS: `/Volumes/personal_folder/scraped/finance-news/` (CNBC+NASDAQ混合)
- ローカル: `data/raw/rss/` (RSSフィード48件)
- ローカル: `data/scraped/wealth/` (ブログ記事)
- ローカル: `.tmp/` (セッションファイル、状態DB)

## 議論のサマリー

1. 対象サイトの全体像を調査（1000+ URL、8カテゴリ）
2. スクリプト → 対象サイトのマッピングを整理
3. 出力形式（JSONスキーマ、ディレクトリ構造）を文書化
4. NASストレージの再設計と移行を実施

## 決定事項

1. **CNBC/NASDAQ分離**: `finance-news/` の混合保存を廃止し、`cnbc/` と `nasdaq/` に分離
2. **全データNAS統合**: RSS、セッション、ブログデータをすべてNASに集約
3. **NAS新ディレクトリ構造**:

```
/Volumes/personal_folder/scraped/
├── cnbc/{date}/news_{time}.json       # CNBC記事
├── nasdaq/{date}/news_{time}.json     # NASDAQ記事
├── jetro/{date}/news_{time}.json      # JETRO
├── rss/feeds.json + {feed_id}/        # RSSフィードデータ
├── sessions/                          # セッションファイル・状態DB
├── wealth/{domain}/{slug}.md          # ブログ記事
└── youtube_transcript/                # YT文字起こし
```

4. **ローカルフォールバック維持**: NAS未マウント時は従来のローカルパスにフォールバック

## 変更ファイル

| ファイル | 変更内容 |
|---|---|
| `scripts/scrape_finance_news.py` | ソース別分離保存 |
| `scripts/scrape_wealth_blogs.py` | セッション/DB → NAS sessions/ |
| `scripts/prepare_news_session.py` | セッション → NAS sessions/ |
| `scripts/convert_scraped_news.py` | ドキュメントのパス更新 |
| `src/rss/cli/main.py` | デフォルトデータディレクトリ → NAS rss/ |
| `src/rss/mcp/server.py` | 同上 |

## 移行済みデータ

- RSS: 50ファイル → NAS `rss/`
- セッション: 17ファイル → NAS `sessions/`
- CNBC記事: 2ファイル → NAS `cnbc/`
- JETRO分離分: 1ファイル → NAS `jetro/`

## アクションアイテム

- [ ] 旧 `finance-news/` ディレクトリの削除（低優先度）
- [ ] ローカル `data/raw/rss/` と `.tmp/` セッションファイルの削除確認（低優先度）
- [ ] launchd plist がfinance-newsパスを参照していないか確認（中優先度）

## Neo4j保存先

- Discussion: `disc-2026-03-19-nas-storage-restructure`
- Decisions: `dec-2026-03-19-002`, `dec-2026-03-19-003`, `dec-2026-03-19-004`
- ActionItems: `act-2026-03-19-001`, `act-2026-03-19-002`, `act-2026-03-19-003`
