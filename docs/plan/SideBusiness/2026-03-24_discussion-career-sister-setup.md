# 議論メモ: キャリアお姉さん プロフィール確定・カルーセルテンプレ刷新・初投稿

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

career_sister アカウント（Threads / Instagram）の本格運用開始に向けて、プロフィール文の確定、カルーセルデザインの統一、初投稿の実施を行った。

## 議論のサマリー

### 1. プロフィール文の作成・確定

- Threads / Instagram それぞれ A/B/C の3案を作成
- 両方とも C案（シンプル + 刺さるワンライン）を採用
- 複数回のフィードバックで調整:
  - 「毎日3投稿」「毎日発信中」の表現を削除
  - 絵文字を適度に追加（☝️📈✏️🙌💡）
  - Instagram: 「本音トーク」→「キャリアに役立つ情報」に変更
- Threads Bio はユーザーが最終調整して確定版を反映
- persona.md に両プラットフォームのプロフィールを追記

### 2. カルーセルテンプレートの刷新

- テンプレートが2種類存在していた:
  - `templates/career_sister/carousel.html` (ネイビー系 HTML)
  - `creator/career_sister/templates/carousel-type1-story.pen` (暖色系 Pencil)
- ユーザーの指示で .pen テンプレートを正式採用、ネイビー HTML は廃止（trash/ へ移動）
- .pen デザインに忠実な新 HTML テンプレートを作成:
  - カラー: ベージュ(#FFF8F0) + キャメル(#D4A574)
  - フォント: Nunito
  - サイズ: 1080x1080（正方形）
- render_carousel.py を更新（レンダラー関数 + viewport サイズ）
- 全7カルーセル（48枚）を新デザインで一括再生成

### 3. Threads 初投稿

- #1 月朝「面接の逆質問テク」を Threads に投稿
- API access blocked エラーが一時発生 → Meta 側の一時的制限で復旧
- 投稿成功: https://www.threads.com/@career_sister/post/DWQF-5xE0fO
- meta.json に published_at と permalink を記録

### 4. 月曜分 残り2投稿（#2, #3）

- #2 月昼「年収の悩み投票」→ Threads 投稿成功
  - https://www.threads.com/@career_sister/post/DWQKMqbE5mQ
- #3 月夜「経験の翻訳」→ Threads + Instagram カルーセル投稿成功
  - Threads: https://www.threads.com/@career_sister/post/DWQKTz4k3Ba
  - Instagram: https://www.instagram.com/p/DWQKgUak9G8/
  - R2 に 6枚のカルーセル画像をアップロード → Instagram Graph API でカルーセル投稿

### 5. Threads API 500文字制限の発見

- #3 の投稿文（529文字）で「Param text must be at most 500 characters long」エラー発生
- 405文字に短縮して投稿成功
- `/career-sister-draft` コマンドに文字数制限セクションを追加

## 決定事項

1. **Threads プロフィール Bio 確定**: 転職経験ベースの信頼感を重視した4行構成
2. **Instagram プロフィール Bio 確定**: カルーセル訴求 + Threads 誘導の4行構成
3. **カルーセルテンプレート**: .pen（暖色系）を正式採用、ネイビー HTML は廃止
4. **Threads 初投稿完了**: #1〜#3 全3投稿 + IG カルーセル1本
5. **Threads API 500文字制限**: API 経由では 500 文字上限。下書き生成時に検証必須

## アクションアイテム

- [x] 月曜分の残り2投稿（#2 昼: 年収投票, #3 夜: 経験の翻訳 + IG カルーセル）を投稿する → 完了
- [x] Threads / Instagram アプリで確定済み Bio をプロフィールに手動設定する → 完了
- [ ] Meta API トークンの定期リフレッシュ（cron）を設定し再発防止 (優先度: 中)

## 次回の議論トピック

- 火曜以降の投稿スケジュール運用
- 投稿パフォーマンスのトラッキング（Insights API）
- 500文字制限を考慮した下書き生成の最適化
