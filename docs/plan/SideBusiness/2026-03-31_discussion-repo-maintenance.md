# 議論メモ: リポジトリメンテナンス — ブランチ整理 & Issue クリーンアップ

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

note-finance リポジトリに不要なブランチとオープン Issue が蓄積していたため、一括整理を実施した。

## 実施内容

### ブランチ整理

全ブランチの PR マージ状況・差分を確認し、main ブランチ 1 本構成に整理。

| 種別 | ブランチ | 理由 |
|------|---------|------|
| ローカル削除 | feature/prj104 | main にマージ済み |
| ローカル削除 | feature/prj103 | main にマージ済み |
| ローカル削除 | feature/prj84 | main にマージ済み |
| ローカル削除 | feature/prj85 | main にマージ済み |
| ローカル削除 | feature/todo-2026-03-17-remaining | PR#147 マージ済み |
| ローカル+worktree削除 | worktree-agent-a3f980c5 | main との差分ゼロ確認済み |
| リモート削除 | feature/kg-v3-ontology-redesign | PR#238 マージ済み |
| リモート削除 | feature/prj86 | PR#197 マージ済み |
| リモート削除 | feature/todo-2026-03-17-remaining | PR#147 マージ済み |
| リモート削除 | refactor/article-workflow-unification | PR#94 マージ済み |
| リモート削除 | refactor/weekly-report-local-json-only | PR#9 マージ済み |

**worktree 確認**: `worktree-agent-a3f980c5` は main より 67 コミット遅れだが、branch 固有の未マージコミットは 0 件（差分なし）を git diff で確認後に削除。

### Issue クリーンアップ

オープン Issue 4 件を調査し全件クローズ。

| Issue | タイトル | 判断 | 根拠 |
|-------|---------|------|------|
| #149 | [Wave1] _html_utils.py テスト実装 | 実装済みクローズ | test_html_utils.py 330行・30テストケース・全 pass |
| #155 | [Wave2] reuters_jp.py テスト実装 | 実装済みクローズ | test_reuters_jp.py 644行・48テストケース・全 pass |
| #158 | [Wave3] minkabu.py テスト実装 | 実装済みクローズ | test_minkabu.py 385行・22テストケース・全 pass |
| #208 | 欠落リレーション修復 3バッチ | 対応不要クローズ | 下記参照 |

**#208 クローズ根拠**:
- コミット `096f6b8`（2026-03-27）で ABOUT/TAGGED/EXTRACTED_FROM 欠落の根本原因を修正済み
- KG v3.0 移行完了（PR #238, #294）により、旧 v2 データの修復は不要
- 対象 235 件 vs 新規 5000+件/月 という費用対効果の観点からも優先度低

## 決定事項

1. note-finance リポジトリを **main ブランチ 1 本構成**に整理（ローカル 6 本 + リモート 5 本を削除）
2. Issue #208（欠落リレーション修復 3 バッチ）を**対応不要**と判断してクローズ

## アクションアイテム

なし（全て完了作業）

## 次回の議論トピック

- 特になし
