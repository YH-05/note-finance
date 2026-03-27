# 議論メモ: みつきプロジェクト 次のタスク確認・topic_tag対応

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

みつきアカウントの運用基盤（ペルソナ・投稿アルゴリズム・スキル・コマンド・week_2026-03-31ドラフト）が全て整備完了した後、
次のアクションを確認。あわせてThreadsの「トピックを追加」機能のAPI対応を実施。

## 議論のサマリー

- 本日（3/27）完了済みの作業を確認（リサーチ、ペルソナ、基盤、ドラフト生成）
- 次のアクションとして「自己紹介投稿作成」を選択
- persona.md に確定済みの初回投稿テンプレートがあることを確認
- Threads「トピックを追加」機能のAPI（topic_tag パラメータ）対応を決定・実施

## 決定事項

1. **自己紹介投稿**: `persona.md` の「自己紹介投稿（初回投稿テンプレート）」をそのまま使用
2. **topic_tag 対応**:
   - `poster.py` の `_create_container()` / `post_text()` / `post_image()` / `post_carousel()` に `topic_tag: str | None = None` パラメータを追加
   - CLI に `--topic-tag` 引数を追加
   - カテゴリ別デフォルト:
     - タロット・星座・note誘導 → `ASTROLOGY_METAPHYSICS`
     - Tips・ENG・Story → `MENTAL_HEALTH_AWARENESS`
   - `mitsuki-draft.md` のフロントマター仕様に `topic_tag` を追加
   - `mitsuki-publish.md` でフロントマターから読み取り `--topic-tag` に渡す

## アクションアイテム

- [ ] Threads に自己紹介投稿を出す（persona.md 初回投稿テンプレートを使用） (優先度: 高)
- [ ] note アカウントの表示名・Bio 設定（persona.md note プロフィールセクション参照） (優先度: 高)
- [ ] week_2026-03-31 ドラフトをレビューして投稿準備 (優先度: 高)

## 実施済み変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/creator/poster.py` | `topic_tag` パラメータ対応（全メソッド + CLI） |
| `.claude/commands/mitsuki-draft.md` | フロントマター仕様にtopic_tag追加・カテゴリ別デフォルト表追加 |
| `.claude/commands/mitsuki-publish.md` | Step 4 に topic_tag 読み取り・`--topic-tag` 渡し追加 |

## 次回の議論トピック

- /mitsuki-publish コマンドの設計（スロット別スケジュール投稿）
- note 記事 SEO 戦略（タイトル・見出し設計）
- 10本無料記事達成後の有料移行タイミング（現在 note_count=7、残り3本）
- 自己紹介投稿後の反応に応じたコンテンツ方針微調整
