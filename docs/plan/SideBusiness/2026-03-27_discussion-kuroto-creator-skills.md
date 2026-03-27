# 議論メモ: 玄人領域クリエイタースキル・コマンド体系の構築

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

3ペルソナクリエイターシステム（career_sister / mitsuki / kuroto_area）において、
career_sisterとmitsukiには既存のスキル・コマンド体系があったが、kuroto_areaには不足していた。
また、3ペルソナ全員のThreads/Instagram/note投稿を品質管理する仕組みも不十分だった。

## 議論のサマリー

### 1. kuroto_area スキル・コマンド体系の構築

kuroto-writerスキル（既存）を基盤として、以下を新規作成:
- `.claude/commands/kuroto-draft.md`: 7日分（42コンテンツ）一括生成コマンド
- `.claude/commands/kuroto-publish.md`: Threads/note投稿コマンド
- `creator/kuroto_area/posting_state.json`: 状態管理ファイル（修正）
- `creator/kuroto_area/posting_algorithm.md`: テーマアルゴリズム（修正）

### 2. note記事頻度の修正

初期実装では「週2本」としていたが、ユーザー指摘により「1日1本（7本/週）」に修正。
関連ファイルを全て更新し、week_2026-03-30の不足分（月・火・木・金・日）を追加生成。

### 3. 6つのプラットフォーム別品質管理スキル

| スキル | ペルソナ | プラットフォーム | 特徴 |
|--------|---------|----------------|------|
| mitsuki-threads | みつき（美月） | Threads | 500字以内、型1-4、タロット/星座/Tips/数秘術 |
| mitsuki-note | みつき（美月） | note | 1,000-8,000字、型N1-N5、心理学的裏付け |
| career-sister-threads | キャリアお姉さん | Threads | 500字以内、型1-5、市場データ週3回必須 |
| career-sister-insta | キャリアお姉さん | Instagram | カルーセル5-10枚、キャプション2,200字以内 |
| kuroto-area-threads | 玄人領域 | Threads | 500字以内、型1-5、です・ます調 |
| kuroto-area-note | 玄人領域 | note | 1,000-8,000字、型N1-N7、哲学×行動科学 |

## 決定事項

1. kuroto-draft コマンドのnote記事生成頻度は1日1本（7本/週）とする
2. 3ペルソナ × プラットフォーム別の品質管理スキルを6本実装する
3. 玄人領域の週次draftsディレクトリ構造は「week_YYYY-MM-DD/day_N_曜/sX_*.md + note_article.md」とする

## 成果物

### 作成ファイル一覧

**スキル（6本）**:
- `.claude/skills/mitsuki-threads/SKILL.md`
- `.claude/skills/mitsuki-note/SKILL.md`
- `.claude/skills/career-sister-threads/SKILL.md`
- `.claude/skills/career-sister-insta/SKILL.md`
- `.claude/skills/kuroto-area-threads/SKILL.md`
- `.claude/skills/kuroto-area-note/SKILL.md`

**コマンド（2本）**:
- `.claude/commands/kuroto-draft.md`
- `.claude/commands/kuroto-publish.md`

**下書き（42コンテンツ）**:
- `creator/kuroto_area/drafts/week_2026-03-30/` 配下
  - 35 Threads投稿（5スロット × 7日）
  - 7 note記事（各日1本）
  - meta.json

## アクションアイテム

- [x] kuroto-draft コマンド作成（完了）
- [x] kuroto-publish コマンド作成（完了）
- [x] 6プラットフォーム別品質管理スキル作成（完了）
- [x] week_2026-03-30 の42コンテンツ生成（完了）
- [x] posting_state.json の note_per_day=1 に修正（完了）

## 次回の議論トピック

- kuroto-area-instaスキルが未実装（Instagram投稿のニーズがあれば）
- kuroto-publishコマンドの実際のThreads/note API連携テスト
- career-sisterのnoteスキル（note投稿）が未実装

## 参考情報

- ペルソナ共通の独立性原則: 3ブランド完全独立（他ペルソナへの言及禁止）
- kuroto_areaのコンセプト: 「静かな自己改造」「設計>意志力」「哲学と科学の両輪」
- Threads API文字数制限: 500字（超過すると500エラー）
