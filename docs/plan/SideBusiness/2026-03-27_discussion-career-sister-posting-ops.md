# 議論メモ: career_sister 3/27(木) 投稿オペレーション

**日付**: 2026-03-27
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-27-career-sister-posting-ops

## 背景・コンテキスト

week_2026-03-24 の下書き（3/24月〜3/26水）は既に投稿完了。
本日 3/27(木) から残り4日分（木〜日）の投稿オペレーションを開始。

投稿ツールチェーン:
- `uv run python -m src.creator.poster threads --text <投稿文>`
- `R2ImageHost.upload_batch()` で画像をR2にアップロード
- `uv run python -m src.creator.poster instagram --image-urls <URLs>`
- `meta.json` の status を `published` に更新

## 実施内容

### 朝スロット（Instagram付き） — 投稿完了 ✅

| 項目 | 内容 |
|------|------|
| カテゴリ | 有益/型3/T3 |
| タイトル | 年収交渉で盛大にやらかした話 |
| Instagram | カルーセル 7枚 |
| Threads | https://www.threads.com/@career_sister/post/DWXmPy_EowJ |
| Instagram | https://www.instagram.com/p/DWXmev1EnJG/ |
| 投稿時刻 | 2026-03-27 10:02 JST |

## 決定事項

1. **dec-2026-03-27-career-sister-manual-posting**: `/career-sister-publish` による手動投稿オペレーションを標準フローとして継続。Threads→R2→Instagram の順序。

## アクションアイテム

- [x] **昼スロット投稿**: 「今のスキル、他の業界じゃ使えないんじゃ…」Threadsのみ (優先度: 高) ✅ 完了
  - Threads: https://www.threads.com/@career_sister/post/DWX44PVkp8M (2026-03-27 12:45 JST)
- [ ] **夜スロット投稿**: 「キャリアチェンジで一番大変だったこと」エンゲージメント投票 (優先度: 高)
  - ファイル: `creator/career_sister/drafts/week_2026-03-24/day_4_thu/slot_3_evening/threads_post.md`

## 週間残り投稿スケジュール

| 日付 | 朝 | 昼 | 夜 |
|------|-----|-----|-----|
| 3/27(木) | ✅ 投稿済 | ✅ 投稿済 | 未投稿 |
| 3/28(金) | 未投稿 | 未投稿(IG付) | 未投稿 |
| 3/29(土) | 未投稿(IG付) | 未投稿 | 未投稿 |
| 3/30(日) | 未投稿 | 未投稿(IG付) | 未投稿 |
