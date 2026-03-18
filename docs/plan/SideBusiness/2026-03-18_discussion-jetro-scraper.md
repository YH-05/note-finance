# 議論メモ: JETRO海外ビジネス情報スクレイパー計画

**日付**: 2026-03-18
**参加**: ユーザー + AI
**ワークフロー**: `/plan-project @docs/plan/2026-03-18_jetro-overseas-business-scraper.md`

## 背景・コンテキスト

JETROの「海外ビジネス情報」セクションから3カテゴリ（国・地域別/テーマ別/産業別）の全コンテンツをスクレイピングし、既存の `src/news_scraper/` パッケージに統合するプロジェクト。plan-project ワークフロー（4フェーズ: リサーチ→計画→タスク分解→GitHub登録）を完了。

## 議論のサマリー

### Phase 0: 方向確認
- プロジェクトタイプ: **package**（src/news_scraper/ 配下）
- 目的: **新規作成**

### Phase 1: リサーチ結果
- 既存パターンを網羅的に調査（cnbc.py, nasdaq.py, unified.py, types.py 等）
- コードベース全体で `async_playwright` のみ使用、`sync_playwright` 使用例なし
- 新規依存追加不要（feedparser, httpx, lxml, trafilatura, playwright は全て既存）
- `ScraperConfig.use_playwright` フラグが既に存在

### Phase 2: 計画承認
- 2層アーキテクチャ（RSS + Playwright Crawler）
- 12ファイル（新規10 + 変更2）

### Phase 3: タスク分解
- 9タスク / 4 Wave / 10-14時間

## 決定事項

1. **アーキテクチャ**: 2層スクレイピング構成（Layer 1: feedparser+httpx / Layer 2: async_playwright+asyncio.run()）
2. **パターン準拠**: cnbc.py パターンに厳密に従う。SOURCE_REGISTRY に lazy import ラッパーで登録
3. **DOM調査タイミング**: CSSセレクタの確定は実装フェーズ（Wave 3, Issue #180）で実施。フォールバックリスト形式で設計
4. **プロジェクト構成**: 9タスク/4Wave、GitHub Project #86、Issue #175-#183

## アクションアイテム

- [ ] Wave 1 基盤タスク実装: #175, #176, #177, #178 (優先度: 高)
- [ ] Wave 2 Layer 1 実装: #179 jetro.py (優先度: 高)
- [ ] Wave 3 Crawler 実装: #180, #181 (優先度: 中)
- [ ] Wave 4 CLI + docs: #182, #183 (優先度: 中)

## GitHub リソース

| リソース | リンク |
|---------|--------|
| GitHub Project | [#86](https://github.com/users/YH-05/projects/86) |
| 計画書 | `docs/project/project-17/project.md` |
| 元プラン | `docs/project/project-17/original-plan.md` |

## Issue 一覧

| Wave | Issue | タイトル |
|------|-------|---------|
| 1 | [#175](https://github.com/YH-05/note-finance/issues/175) | `_jetro_config.py` 定数・設定 |
| 1 | [#176](https://github.com/YH-05/note-finance/issues/176) | `jetro-categories.json` カテゴリマスタ |
| 1 | [#177](https://github.com/YH-05/note-finance/issues/177) | `types.py` / `unified.py` 型拡張 |
| 1 | [#178](https://github.com/YH-05/note-finance/issues/178) | `test_jetro.py` テスト骨格 |
| 2 | [#179](https://github.com/YH-05/note-finance/issues/179) | `jetro.py` Layer 1 RSS |
| 3 | [#180](https://github.com/YH-05/note-finance/issues/180) | `_jetro_crawler.py` Playwright |
| 3 | [#181](https://github.com/YH-05/note-finance/issues/181) | `test_jetro_crawler.py` テスト |
| 4 | [#182](https://github.com/YH-05/note-finance/issues/182) | `scrape_jetro.py` CLI |
| 4 | [#183](https://github.com/YH-05/note-finance/issues/183) | `project.md` ドキュメント |

## Neo4j 保存情報

- Discussion: `disc-2026-03-18-jetro-scraper-planning`
- Decision: `dec-2026-03-18-001` ~ `dec-2026-03-18-004`
- ActionItem: `act-2026-03-18-001` ~ `act-2026-03-18-004`

## 次回の議論トピック

- Wave 1 実装完了後のレビュー
- Wave 3 の DOM 調査結果とセレクタ確定
