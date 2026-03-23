# 議論メモ: career_sister 投稿パイプライン構築

**日付**: 2026-03-23
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-23-career-sister-pipeline

## 背景・コンテキスト

Threads×Instagram自動投稿マネタイズ戦略（3アカウント構成）の転職アカウント（career_sister）について、
ペルソナ設計からパイプライン構築、1週間分テスト生成まで一気通貫で実施。

## セッション成果

### Phase 1: ペルソナ設計 + 初回投稿

- ペルソナ確定: 「キャリアお姉さん」/ 姉御肌タメ口 / 大手メーカー4年→ITベンチャー
- 初回投稿 Post 1 を Threads に投稿: https://www.threads.com/@career_sister/post/DWN3DvUE3vF
- ファイル: `creator/career_sister/persona.md`, `initial_posts.md`

### Phase 2: career-sister-writer スキル

- SKILL.md: ペルソナ定義 / 口調ルール / NGリスト / 投稿4パターン / 主張一貫性チェックリスト6項目
- references/post-examples.md: お手本投稿5本
- トリガー: 「キャリアお姉さん」「career_sister」「転職投稿」等

### Phase 3: 投稿パイプライン構築

| コンポーネント | ファイル | 役割 |
|-------------|---------|------|
| HTMLテンプレート | `templates/career_sister/carousel.html` | カルーセル4タイプ（title/content/points/cta） |
| レンダリング | `scripts/render_carousel.py` | Playwright で HTML→PNG (1080x1350px) |
| 下書き生成 | `.claude/commands/career-sister-draft.md` | 1週間分一括生成コマンド |
| 投稿実行 | `.claude/commands/career-sister-publish.md` | 日次投稿コマンド |

### Phase 4: スケジューリングアルゴリズム

- 10投稿サイクル制: カテゴリ比率 7:2:1 を厳密保証
- 日次スケジュール: 朝7時 + 昼12時 + 夜20時（Threads 3本/日 + Instagram 1本/日）
- 型ローテーション: 型1→型2→型4→型3（有益投稿内で循環）
- テーマ8プール: 重複排除 + 均等分散 + 重み付き選択
- 素材↔型マッピング: 型4→Fact、型3→Story、型2→Tip
- ファイル: `creator/career_sister/posting_algorithm.md`, `posting_state.json`

### Phase 5: 1週間分テスト生成

- 期間: 2026-03-24（月）〜 2026-03-30（日）
- Threads: 21本（有益15 / ENG 4 / 収益化 2）
- Instagram: 7本（カルーセル計 48スライド）
- 保存先: `creator/career_sister/drafts/week_2026-03-24/`

## 決定事項

1. **dec-2026-03-23-career-sister-persona**: ペルソナ確定（キャリアお姉さん/姉御肌/大手→ベンチャー）
2. **dec-2026-03-23-first-threads-post**: 初回Threads投稿完了
3. **dec-2026-03-23-career-sister-writer-skill**: ライタースキル作成
4. **dec-2026-03-23-posting-algorithm**: 10投稿サイクル制アルゴリズム採用
5. **dec-2026-03-23-weekly-batch**: 1週間分一括生成方式
6. **dec-2026-03-23-carousel-pipeline**: HTML/CSS+Playwrightカルーセル生成

## アクションアイテム

- [x] ペルソナ設計 + persona.md 作成 (高)
- [x] 初回 Threads 投稿 (高)
- [x] career-sister-writer スキル作成 (高)
- [x] カルーセルテンプレート + レンダリングスクリプト (高)
- [x] /career-sister-draft, /career-sister-publish コマンド作成 (高)
- [x] スケジューリングアルゴリズム設計 (高)
- [x] 1週間分テスト生成（21 Threads + 7 IG + 48スライド） (高)
- [ ] 下書きレビュー→修正→日次投稿開始 (高)
- [ ] ASP登録（A8.net→afb→アクセストレード） (高)
- [ ] posting_state.json 更新 (中)
- [ ] Threads プロフィール文更新 + Post 1 固定投稿設定 (高)

### 追加決定: 予約投稿API調査

7. **dec-2026-03-23-no-scheduled-post-api**: Threads/Instagram APIに予約投稿機能なし（即時公開のみ）。cronスケジューラーは後日検討。当面は手動投稿。

## 次回の議論トピック

- 1週間分の投稿レビューとフィードバック
- 投稿後のエンゲージメント分析（フィードバックループ Phase 2）
- cronベース自動投稿スクリプトの設計（GitHub Actions / VPS / Raspberry Pi）
- 2つ目のアカウント（美容×恋愛）のパイロット準備
- ASP案件選定と収益化投稿への自然なリンク設計
- creator-enrichment でStory素材の補充（3ヶ月で枯渇予測）

## 作成ファイル一覧

| ファイル | 説明 |
|---------|------|
| `creator/career_sister/persona.md` | ペルソナ定義 |
| `creator/career_sister/initial_posts.md` | 初回投稿5本 |
| `creator/career_sister/posting_algorithm.md` | アルゴリズム設計 |
| `creator/career_sister/posting_state.json` | 状態管理 |
| `.claude/skills/career-sister-writer/SKILL.md` | ライタースキル |
| `.claude/skills/career-sister-writer/references/post-examples.md` | お手本投稿 |
| `templates/career_sister/carousel.html` | カルーセルテンプレート |
| `scripts/render_carousel.py` | カルーセルレンダリング |
| `.claude/commands/career-sister-draft.md` | 週次下書き生成コマンド |
| `.claude/commands/career-sister-publish.md` | 日次投稿コマンド |
| `creator/career_sister/drafts/week_2026-03-24/` | 1週間分下書き |
