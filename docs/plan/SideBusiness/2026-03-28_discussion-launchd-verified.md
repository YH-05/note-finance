# 議論メモ: launchd 全ジョブ登録済み確認

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

`act-2026-03-28-launchd-install`（launchd インストール作業）の完了確認を実施。

## 確認内容

`launchctl list | grep note-finance` の出力:

```
com.note-finance.auto-poster-career-sister   (exit 0)
com.note-finance.auto-poster-mitsuki         (exit 0)
com.note-finance.auto-poster-kuroto-area     (exit 0)
com.note-finance.scrape-federal-reserve      (exit 0)
com.note-finance.scrape-hacker-news          (exit 0)
com.note-finance.scrape-zero-hedge           (exit 0)
com.note-finance.scrape-reuters-jp           (exit 0)
com.note-finance.scrape-techcrunch           (exit 0)
com.note-finance.scrape-kabutan              (exit 0)
com.note-finance.scrape-jetro                (exit 0)
com.note-finance.scrape-ars-technica         (exit 0)
com.note-finance.scrape-the-verge            (exit 0)
com.note-finance.scrape-news                 (exit 78) ← 要確認
```

auto-poster 3本 + スクレイパー群すべてロード済み。

## 決定事項

1. launchd インストール作業は完了済み（`act-2026-03-28-launchd-install` → completed）

## 残課題

- `com.note-finance.scrape-news` の exit code 78 を調査（設定ファイル不在の可能性）

## アクションアイテム（更新）

- [x] launchd インストール: 確認済み・完了
- [ ] scrape-news の exit 78 原因調査（低優先度）
