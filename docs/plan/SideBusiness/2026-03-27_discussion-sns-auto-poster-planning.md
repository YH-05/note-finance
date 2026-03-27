# 議論メモ: SNS 自動投稿スクリプト 計画完了

**日付**: 2026-03-27
**参加**: ユーザー + AI
**Neo4j**: `disc-2026-03-27-sns-auto-poster-design`
**GitHub Project**: [#104](https://github.com/users/YH-05/projects/104)
**計画書**: `docs/project/project-27/project.md`

## 背景・コンテキスト

みつき・キャリアお姉さんの SNS 投稿（毎日 5+3=8 スロット）を手動から自動化するため、
`scripts/auto_poster.py` + `launchd plist` の設計・計画を `/plan-project` ワークフローで実施。
設計書 `docs/plan/2026-03-27_sns-auto-poster-design.md` を起点に実行。

## 議論のサマリー

### リサーチで発見した主要事項
- `ThreadsPoster.for_account()` / `InstagramPoster.post_carousel()` — 追加実装不要で直接 import 利用可
- 全依存（tenacity / filelock / boto3 / httpx）が pyproject.toml に既存
- launchd plist テンプレートとして `com.note-finance.scrape-news.plist` を踏襲可能
- **ギャップ**: `instagram_caption.md` が実際の drafts ディレクトリに存在しない
- **ギャップ**: `publish_to_note.py` は `articles/` 向け設計で mitsuki の `note_article.md` に未対応

### ユーザー確認事項（HF1）
1. Instagram キャプション → career-sister-draft スキルを拡張して生成
2. note.com 投稿 → 初回から実装（--creator-mode 追加）
3. NAS 未マウント時ロック → `/tmp/note-finance-auto-poster.lock` にフォールバック

## 決定事項

1. **Instagram キャプション方針**（`dec-2026-03-27-ig-caption-fallback`）
   - `instagram_caption.md` 優先、不在時は `threads_post.md` フォールバック
   - career-sister-draft スキル拡張は Issue #267 として分離

2. **note.com 投稿**（`dec-2026-03-27-note-creator-mode`）
   - `publish_to_note.py` に `--creator-mode` オプション追加で初回から実装
   - DraftPublisher の `articles/` 依存は事前確認必須（リスク high）

3. **NAS ロックフォールバック**（`dec-2026-03-27-nas-lock-fallback`）
   - `/tmp/note-finance-auto-poster.lock` にフォールバック
   - マルチマシン運用時は NAS マウント必須と WARNING で明示

4. **アーキテクチャ**（`dec-2026-03-27-auto-poster-arch`）
   - 7コンポーネント: AutoPosterConfig / SlotMatcher / DraftReader / AccountPoster / StateUpdater / NasLockManager / NasSyncer

5. **launchd 設定**（`dec-2026-03-27-launchd-design`）
   - `StartCalendarInterval` に 8 スロット（07:00/07:30/12:00/12:30/15:00/19:00/20:30/22:00）

## アクションアイテム（GitHub Issues）

### Wave 1（開始可能）
- [ ] [#266](https://github.com/YH-05/note-finance/issues/266) auto_poster.py 基本構造 (優先度: 高)
- [ ] [#267](https://github.com/YH-05/note-finance/issues/267) career-sister-writer スキル拡張 (優先度: 中)

### Wave 2（Wave 1 完了後）
- [ ] [#268](https://github.com/YH-05/note-finance/issues/268) mitsuki Threads 投稿 + StateUpdater (優先度: 高)
- [ ] [#269](https://github.com/YH-05/note-finance/issues/269) career_sister Threads 投稿 (優先度: 高)
- [ ] [#270](https://github.com/YH-05/note-finance/issues/270) launchd plist 作成 (優先度: 中)

### Wave 3
- [ ] [#271](https://github.com/YH-05/note-finance/issues/271) career_sister Instagram カルーセル投稿
- [ ] [#272](https://github.com/YH-05/note-finance/issues/272) リトライ + エラーハンドリング

### Wave 4
- [ ] [#273](https://github.com/YH-05/note-finance/issues/273) マルチマシン対応（NasLockManager + NasSyncer）
- [ ] [#274](https://github.com/YH-05/note-finance/issues/274) sync_nas.sh 拡張
- [ ] [#275](https://github.com/YH-05/note-finance/issues/275) publish_to_note.py --creator-mode

## 次回の議論トピック

- Wave 1 実装完了後の動作確認結果
- DraftPublisher の `articles/` 依存の調査結果（Issue #275 実装前に必要）
- career-sister-draft スキル拡張の具体的な実装方法

## 参考情報

- 元設計書: `docs/project/project-27/original-plan.md`
- セッションデータ: `.tmp/plan-project-20260327-160956/`
- worktree: `/Users/yukihata/Desktop/.worktrees/note-finance/feature-prj104`
