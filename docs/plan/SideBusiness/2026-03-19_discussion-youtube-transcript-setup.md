# 議論メモ: YouTubeトランスクリプト収集 — チャンネル登録・初回収集・障害対応

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

Wave1-3で実装完了したyoutube_transcriptパッケージの実運用セットアップ。
対象チャンネルの選定・登録、YouTube Data API v3の設定、初回収集の実行と障害対応を行った。

## 議論のサマリー

### 1. 対象チャンネル選定

プロジェクト目的（バイサイドアナリストのリサーチ、note.com金融記事執筆、週次マーケットレポート、資産形成コンテンツ）に合わせて10チャンネルを選定。

初回提案からユーザーのフィードバックで以下を調整:
- **PIVOT除外**: ユーザー判断で除外
- **追加**: Bloomberg Television、CNBC Television、Nasdaq、Goldman Sachs、J.P. Morgan（セルサイド・メディア系の拡充）

### 2. 登録チャンネル一覧（確定版）

| 言語 | チャンネル | UCxxx ID |
|------|----------|----------|
| 🇯🇵 | 日経CNBC | UClVsQnfs-jKkjKmUKUHnT2g |
| 🇯🇵 | 後藤達也・経済チャンネル | UCeLeyHAaZJb4tm0cAMxc60Q |
| 🇯🇵 | 朝倉慶のASK1 | UCax09PmcRoY1R8mfJFBfv0g |
| 🇺🇸 | Bloomberg Television | UCIALMKvObZNtJ6AmdCLP7Lg |
| 🇺🇸 | CNBC Television | UCrp_UI8XtuYfpiqluWLD7Lw |
| 🇺🇸 | Financial Times | UCoUxsWakJucWg46KW5RsvPw |
| 🇺🇸 | Nasdaq | UCDhqADfY8S2N8BfrffZAc2w |
| 🏦 | Goldman Sachs | UCyz6-taovlaOkPsPtK4KNEg |
| 🏦 | J.P. Morgan | UCBnFes2U2diA3QfR5m8l_Tw |
| 🏦 | Aswath Damodaran | UCLvnJL8htRR1T9cbSccaoVw |

### 3. 発見されたバグと修正

#### 3.1 channel add の @handle 未解決問題

**問題**: `yt-transcript channel add --channel-id "@GoldmanSachs"` で登録すると、`uploads_playlist_id` が空のまま保存され、収集時に `400 Bad Request` エラー。

**原因**: `_normalise_to_channel_id()` が @handle をそのまま返し、`_derive_uploads_playlist_id()` が `UC` で始まらないIDには空文字を返す設計。

**修正**: `channel_manager.py` の `add()` メソッドで、IDが `UC` で始まらない場合に YouTube Data API (`ChannelFetcher.get_channel_info()`) を呼んで自動解決するよう修正。

**コミット**: `042abff`

#### 3.2 IpBlocked フォールバック

**問題**: `youtube-transcript-api` による字幕取得で `IpBlocked` エラーが全動画で発生。

**修正**: `collector.py` に `_fetch_with_fallback()` メソッドを追加。`IpBlocked` 検出時に `yt_dlp_fetcher` へ自動フォールバック。一度検出すると以降は直接yt-dlpを使用。

### 4. IPブロック問題

初回収集で YouTube が字幕取得エンドポイントをIPブロック。以下を全て試したが解消せず:

| 方法 | 結果 |
|------|------|
| youtube-transcript-api | IpBlocked |
| youtube-transcript-api + Chrome Cookie | IpBlocked |
| yt-dlp | 429 Too Many Requests |
| yt-dlp + Chrome Cookie + deno | 429 Too Many Requests |

**動画一覧取得（YouTube Data API v3）は正常動作** — 字幕スクレイピングエンドポイントのみブロック。

### 5. 環境セットアップ

- `YOUTUBE_API_KEY` を `.env` に設定済み
- `deno` インストール済み（yt-dlpのJS runtime用）
- `yt-dlp` インストール済み（`uv tool install`）

## 決定事項

1. 対象チャンネル10個を上記の通り確定
2. @handle → UCxxx 自動解決をchannel addに組み込む
3. IpBlocked時のyt-dlpフォールバックを実装
4. IPブロック解除後に `yt-transcript collect --all` で再実行する

## アクションアイテム

- [ ] IPブロック解除後に字幕収集を再実行 (優先度: 高)
- [ ] Webshareプロキシ（月$6）の導入を検討（安定運用が必要な場合） (優先度: 中)
- [ ] collect --all 実行時にcollector内部でchannels.jsonを上書きするバグの調査 (優先度: 中)

## 次回の議論トピック

- 収集成功後のデータ活用方法（KGエクスポート、NotebookLM連携）
- 定期収集スケジュールの設定（scheduler.py）
- 大量チャンネル（Bloomberg/CNBC等）の動画数が膨大な場合の対処（日付フィルタ等）
