# 議論メモ: Paranoia YouTubeチャンネルのコンテンツ収集パイプライン設計

**日付**: 2026-03-25
**参加**: ユーザー + AI

## 背景・コンテキスト

Paranoia_パラノイア【有益】（YouTube約7万人登録）は、海外の自己啓発・ビジネス系インフルエンサーの情報を日本語で紹介するチャンネル。このチャンネルが扱うテーマの情報をcreator-neo4jに蓄積し、新規Threadsアカウントやnote記事での発信に活用したい。

### Paranoiaの主要テーマ（動画140本の分析結果）

| テーマ | 具体例 |
|--------|--------|
| 成功者の習慣・マインドセット | Alex Hormozi, Iman Gadzhi の教え |
| モーニング/ナイトルーティン | 朝60分ルーティン、ナイトルーティン |
| 生産性・集中力 | Deep Work, Flow State |
| 行動心理学・交渉術 | 元FBI交渉人テクニック |
| 健康・ウェルネス習慣 | 砂糖断ち、SNSデトックス |
| ストイシズム・禁欲主義 | 実践的ストア哲学 |

## 議論のサマリー

1. 当初はYouTube字幕の直接スクレイピングを検討
2. ユーザーの意図は「Paranoiaが扱うテーマの情報」を収集すること
3. 既存のcreator-enrichmentパイプラインに新ジャンルを追加する方式に決定
4. `self-development` ジャンルをcreator-enrichment-config.jsonに追加済み

## 決定事項

1. **収集方式**: YouTube直接スクレイピングではなく、既存Web検索ツールでテーマベース収集
2. **ジャンル追加**: `self-development`（自己啓発・生産性）をcreator-enrichment-config.jsonに追加
   - 英語12本 + 日本語12本の検索クエリ
   - 8つのSubreddit（r/selfimprovement, r/getdisciplined, r/productivity等）
   - 5つのWebFetchサイト（note.com, hatenablog.com, medium.com）
   - Entity重点: person, concept, technique, platform
3. **発信先**: Threadsアカウント + note記事（詳細は蓄積後に設計）
4. **権限設定**: creator-enrichment実行時の全アクションをユーザー確認なしで自動許可（settings.local.json更新済み）

## アクションアイテム

- [ ] `/creator-enrichment --genre self-development` を実行してデータ収集開始 (優先度: 高)
- [ ] 収集後に `/creator-quality-check` で品質検証 (優先度: 中)
- [ ] Threads/note向けの発信ペルソナ・トーン・投稿頻度を設計 (優先度: 中)

## 次回の議論トピック

- 収集データの品質レビューと検索クエリの調整
- Threads発信ペルソナの設計（career-sister-writerのようなスキル化）
- note記事のカテゴリ・テンプレート設計

## 設定ファイル変更

- `data/config/creator-enrichment-config.json` に `self-development` ジャンルを追加
- `.claude/settings.local.json` にcreator-enrichment用の全権限を追加（WebFetch全ドメイン、Reddit/RSS/Tavily/browser-use MCP全ツール、sequential-thinking）
