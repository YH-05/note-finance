# 議論メモ: 保留 ActionItem 実行セッション + /article-full E2E 検証完了

**日付**: 2026-05-07
**参加**: ユーザー + AI (Claude Opus 4.7 1M)
**Discussion ID**: `disc-2026-05-07-pending-actions-execution`
**親議論**:
- `disc-2026-05-06-note-link-card-rule`
- `disc-2026-05-06-article-full-fully-automated`

## 背景・コンテキスト

2026-05-06 に2件の議論で計9件の ActionItem が登録された:
- link-card-rule 議論: `act-001/002/003/004`
- article-full 議論: `act-011/012/013/014/015`

このうち高優先度4件（`act-011/013/002/003/014/012`）の実行・確認を本セッションで進めた。

## 議論のサマリー

ユーザー指示「保留中のaction itemの実行に進んで」を起点に、E2E検証以外の中優先度4件をまず処理し、最後にユーザーが `/article-full` の実機テストを実行。

### 処理した ActionItem

| ID | 内容 | 結果 |
|---|---|---|
| `act-2026-05-06-001` | 既存記事のマークダウンリンク残存検出 | **検出完了**: revised_draft.md 46件・1992マッチ。in_progress |
| `act-2026-05-06-002` | article-critique のチェック項目追加 | **completed** |
| `act-2026-05-06-003` | writer/reviser プロンプト更新 | **completed** |
| `act-2026-05-06-014` | article-init の無人モード対応 | **completed** |
| `act-2026-05-06-012` | /article-full E2E 検証（ユーザー実行） | **completed** |

### 検出結果（act-001）

```bash
grep -rEn '(^|[^!])\[[^]]+\]\(https?://[^)]+\)' articles/ \
  | grep -E '(revised_draft|first_draft)\.md:'
```

- マッチ行数: 1992
- 影響 revised_draft.md ファイル数: 46（macro_economy 6・investment_education 6・stock_analysis 7・asset_management 17・earnings 10）

### 更新したファイル

| ファイル | 変更内容 |
|---|---|
| `.claude/skills/finance-article-writer/references/common-rules.md` | ソースURL貼り方セクション全面改訂、データ・ソースチェックリスト更新 |
| `.claude/agents/finance-reviser.md` | 記事品質チェックに機械変換指示を追加 |
| `.claude/skills/article-revise/SKILL.md` | 品質ルール#2（ソースURL）を URL 単独段落方式に更新 |
| `.claude/commands/article-critique.md` | 品質チェック項目に grep 検出コマンドと URL 段落配置チェックを追加 |
| `.claude/commands/article-init.md` | argument-hint に無人モード用引数追加、「実行モード」セクション新設 |

これにより**新規記事は新ルールで自動生成**される基盤が整った。

## 決定事項

### Decision A (`dec-2026-05-07-existing-articles-policy`): 既存46記事は能動的バッチ修正をしない方針

**Status**: active
**Context**: 既存46記事のマークダウンリンク残存（1992行）を一括機械変換するスクリプトを作るより、再投稿時（既存記事の修正・再公開タイミング）に finance-reviser が個別に新ルール形式へ変換する方が安全・低コスト。記事は note.com 上では既に投稿済みで、URLが消失した状態のまま。能動的に直すと再投稿の負荷が大きい。

**内容**:
- 既存46記事は note.com 上で URL 消失状態のまま放置（読者影響は限定的）
- 各記事を将来修正・再投稿するタイミングで finance-reviser が新ルールへ機械変換
- act-001 は in_progress のまま運用継続（46件すべて再投稿完了で completed に変更）

### Decision B (`dec-2026-05-07-article-full-validated`): /article-full の完全自動実行モードを正式運用とする

**Status**: active
**Context**: 2026-05-06 の `disc-2026-05-06-article-full-fully-automated` で決定した完全自動化が、ユーザー実行 E2E 検証で正常動作することを確認した。HF 全廃と対話入力自動補完が無人実行で機能する。

**内容**:
- `/article-full` は完全自動・無人実行モードを標準として運用
- バッチ記事生成・スケジュール実行に利用可能（cron / launchd 等で起動可）
- 検証時の問題点があれば追加 ActionItem として登録（現時点では報告なし）

## アクションアイテム

- [x] `act-2026-05-06-002` article-critique チェック項目追加（**completed**）
- [x] `act-2026-05-06-003` writer/reviser プロンプト更新（**completed**）
- [x] `act-2026-05-06-014` article-init 無人モード対応（**completed**）
- [x] `act-2026-05-06-012` /article-full E2E 検証（**completed**, ユーザー実行）
- [ ] `act-2026-05-06-001` 既存記事のリンク残存点検（**in_progress**, 46件再投稿完了で完了扱い）
- [ ] `act-2026-05-07-001`: act-2026-05-06-004 の優先度判断（`markdown_parser.py` で `[text](url)` を「text + 段落URL」へ自動変換する案）。実装すれば既存46記事の note.com 上の挙動も改善するが、スコープが大きい (優先度: 中)
- [ ] `act-2026-05-07-002`: act-2026-05-06-015 の優先度判断（`--skip-hf` 後方互換ガード追加）。短時間で完了、影響は cron / 過去のスクリプト互換のみ (優先度: 低)
- [ ] `act-2026-05-07-003`: 数本の新規記事を新ルールで生成し、note.com 上でリンクカード化が実際に表示されるか目視確認 (優先度: 中)

## 次回の議論トピック

- `act-2026-05-06-004`（markdown_parser 自動変換）の実装可否判断
  - 実装すれば既存記事の人手修正不要化
  - 反面、変換ロジックが誤動作すると本文破壊のリスク
  - `.bak` バックアップ必須
- 数本の新規記事生成後の note.com リンクカード化目視確認結果
- 既存46記事のうち、再投稿が想定される記事の優先度付け
- `/article-full` バッチ実行の運用設計（cron / launchd 連携）

## 参考情報

- 検出コマンド（残存マークダウンリンク）:
  ```bash
  grep -rEn '(^|[^!])\[[^]]+\]\(https?://[^)]+\)' articles/ \
    | grep -E '(revised_draft|first_draft)\.md:'
  ```
- 関連 Discussion:
  - `disc-2026-05-06-note-link-card-rule` — リンクカード化ルール改訂
  - `disc-2026-05-06-article-full-fully-automated` — /article-full 完全自動化

## Neo4j 投入完了状況

ActionItem 進捗は本セッション内で随時 Neo4j に反映済み。本 Discussion ノード自体は次のクエリで投入する。
