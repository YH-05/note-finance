---
description: 金融記事の編集ワークフローを実行します。初稿作成→批評→修正の一連の処理を自動化します。
---

# 金融記事編集ワークフロー

## パラメータ（ユーザーに確認）

| パラメータ | 必須 | デフォルト | 説明                             |
| ---------- | ---- | ---------- | -------------------------------- |
| article_id | ○    | -          | 記事ID                           |
| mode       | -    | full       | 編集モード（quick/full）         |
| skip_draft | -    | false      | 初稿作成をスキップ（既存の場合） |

## 編集モード

| モード | 実行する批評エージェント                                |
| ------ | ------------------------------------------------------- |
| quick  | fact, compliance                                        |
| full   | fact, structure, compliance, data_accuracy, readability |

## 処理フロー

### 1. リサーチ完了確認

meta.yaml の workflow を確認:

- `research.decisions = "done"` であること
- 完了していなければ、先にリサーチを実行するよう案内する

// turbo

```bash
cat articles/{article_id}/meta.yaml | python -c "import sys,yaml; d=yaml.safe_load(sys.stdin); print(d.get('workflow',{}).get('research','not_done'))"
```

### 2. 初稿作成

`finance-article-writer` の処理として、`decisions.json`, `sources.json`, `claims.json`, `meta.yaml` を入力に `02_draft/first_draft.md` を生成する。

### 3. [HF5] 初稿レビュー（推奨）

初稿が完成したことをユーザーに報告し、確認を促す。

- 文字数、セクション数、使用した主張の件数を表示
- 修正が必要な場合は `first_draft.md` を直接編集してもらう

### 4. 批評（並列実行）

**quick モード**: fact, compliance のみ実行
**full モード**: fact, compliance, structure, data, readability を実行

批評結果を `critic.json`（機械可読）と `critic.md`（人間可読）に出力。

### 5. コンプライアンスチェック

`compliance.status` が `fail` の場合は、ユーザーにcriticalな問題を報告し確認を求める。

### 6. 修正

`finance-reviser` として `first_draft.md`, `critic.json`, `sources.json` を入力に `02_draft/revised_draft.md` を生成。

### 7. [HF6] 最終確認（必須）

修正前後のスコア比較を表示し、ユーザーに最終確認を求める。

- 「承認」→ status = "ready_for_publish"
- 「修正」→ 編集プロセスに戻る

### 8. workflow 更新

```
- writing.revised_draft = "done"
- human_feedback.hf6_final_approved = true
- status = "ready_for_publish"
```

## エラーハンドリング

- **リサーチ未完了**: `/finance-research` を先に実行するよう案内
- **批評エージェント部分失敗**: 必須エージェント（fact, compliance）成功なら続行
- **コンプライアンス fail**: 修正後に再実行を案内
