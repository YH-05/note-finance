# 議論メモ: YouTube動画トランスクリプト自動収集システム

**日付**: 2026-03-18
**参加**: ユーザー + AI

## 背景・コンテキスト

指定したYouTubeチャンネルの全動画トランスクリプトを自動収集するシステムを構築したい。
ウォッチ対象チャンネルを登録し、過去の全動画＋今後の新着動画のトランスクリプトを取得・蓄積する。

## 議論のサマリー

### 1. トランスクリプト取得手段の比較

YouTube公式APIの Captions リソースは自分の動画のみ対応。他人の動画には以下3つの選択肢がある:

| 手段 | 特徴 |
|------|------|
| youtube-transcript-api | Python特化、手軽、生テキスト+タイムスタンプ |
| yt-dlp | CLI/バッチ向き、SRT/VTT形式出力、レート制限耐性高 |
| NotebookLM | AI要約テキスト、手軽だがAPI無し・大量処理不向き |

### 2. NotebookLM CLI の適性評価

既存のNotebookLM CLIツール（`src/notebooklm/`）での取得を検討したが、以下の理由で不採用:
- `content_summary` はAI要約であり生のトランスクリプトではない
- 1ノートブック上限50ソース（チャンネルの数百〜数千本に対応不可）
- Playwright経由のブラウザ操作で大量処理が非常に遅い
- レート制限でブロックされるリスク

### 3. 精度比較: youtube-transcript-api vs NotebookLM

両者とも同じYouTube字幕トラック（手動 or 自動生成）がデータソース。差は後処理:
- youtube-transcript-api: 生データそのまま（原文忠実）
- NotebookLM: GeminiによるAI後処理（読みやすいが不可逆）

用途が「ソースとしての保存・検索」なら生データ取得が安全。

### 4. 採用アーキテクチャ

```
YouTube Data API v3 → チャンネルの動画一覧取得（playlistItems.list, 1 unit/call）
youtube-transcript-api → 各動画のトランスクリプト取得
定期実行 → 新着動画を自動検出・収集
```

## 決定事項

1. **技術スタック**: YouTube Data API v3 + youtube-transcript-api の2段構成を採用
2. **パッケージ設計**: `src/youtube_transcript/` として既存RSSパッケージのパターンに倣う
3. **API quota最適化**: `playlistItems.list`（1 unit/call）を使用、`search.list`（100 units）は避ける
4. **NotebookLM CLI**: トランスクリプト取得には不採用。取得済みテキストの分析・要約段階で活用

## アクションアイテム

- [ ] youtube_transcript パッケージのMVP実装（優先度: 高）
- [ ] Google Cloud Console で YouTube Data API v3 を有効化・APIキー取得（優先度: 高）
- [ ] ウォッチ対象YouTubeチャンネルリストの作成（優先度: 中）

## 次回の議論トピック

- 収集したトランスクリプトの活用方法（ナレッジグラフ連携、NotebookLMへの投入）
- ウォッチ対象チャンネルの選定基準
- 定期実行の仕組み（cron / APScheduler）

## 関連ドキュメント

- 実装計画: `docs/plan/2026-03-18_youtube-transcript-collector.md`
