# 設計メモ: プレビュー→レビュー逆方向リンク機構

**日付**: 2026-04-16
**関連**: `disc-2026-04-16-article-earnings-review-skill` / `act-2026-04-16-008`
**ステータス**: 設計段階（実装は次フェーズ）

## 背景

`article-earnings-review` スキルでレビュー記事を作成すると、レビュー記事冒頭にプレビュー記事への note.com リンクは自動で埋め込まれる（`preview_ref.note_url` → §0）。
一方、**逆方向**、すなわちプレビュー記事内に「レビュー版はこちら」リンクを追記する仕組みは現時点では未実装。

既存のプレビュー読者にレビュー記事を周知するために、この逆方向リンクの運用を設計する。

## 要件

1. レビュー記事の `publish` 成功時にトリガーされる
2. プレビュー記事の note.com 下書き／公開済みページに「レビュー版はこちら」リンクを1行追記する
3. プレビュー記事のローカル `revised_draft.md` / `03_published/article.md` も同じ内容で同期更新する
4. プレビュー記事の `meta.yaml` に `review_ref` フィールドを追加（逆方向メタデータ）
5. 冪等性: 同じレビュー記事URLが既に追記されている場合は二重追記しない

## 設計方針

### 実装方式: 方式B（ローカル + note.com の両方更新）

検討した3方式:

| 方式 | 内容 | 採否 |
|------|------|------|
| A: md 編集＋再投稿 | ローカル md を編集し、`/article-publish` でプレビュー記事を再投稿 | ✗ note.com 側の下書きURL が変わる可能性があり、記事URLの永続性を破る |
| **B: 両方更新** | note.com エディタを Playwright で開き冒頭にリンクを挿入 + ローカル md も同じ内容で更新 | ○ 採用。既存 `publish-to-note` スキルの Playwright 基盤を流用 |
| C: 別記事でお知らせ | 「レビュー版はこちら」という短いお知らせ記事を投稿 | ✗ 記事数が膨らむ、SEO・回遊率で劣る |

### リンク配置の位置

プレビュー記事冒頭（`#` タイトル直後）に1段落を追加:

```markdown
# 【🇺🇸米株決算】BlackRock（BLK）Q1 2026 決算プレビュー

> 🆕 **決算発表後のレビュー記事を公開しました**: [BlackRock Q1 2026 決算レビュー](https://note.com/kabushiki_labo/n/xxx)

（以下、本文）
```

- 引用ブロック（`>`）で視覚的に区別
- 🆕 絵文字で新着性を表現
- `kabushiki_labo` は固定、URL は `review_ref.note_url` から取得

### meta.yaml への review_ref 追加

プレビュー記事の meta.yaml に以下を追記:

```yaml
review_ref:
  path: articles/earnings/2026-04-15_blk-q1-2026-earnings-review/
  note_url: https://note.com/kabushiki_labo/n/xxx
  linked_at: '2026-04-15T12:00:00Z'
```

## ワークフロー統合

`/article-earnings-review` コマンドの Phase 5（publish）の直後に **Phase 6: プレビュー逆方向リンク** を追加:

```
Phase 5: レビュー記事を note.com に下書き投稿
↓
Phase 6: プレビュー逆方向リンク
├─ プレビュー側 meta.yaml に review_ref を追記
├─ プレビュー側 revised_draft.md / article.md の冒頭にリンク段落を挿入（冪等）
└─ note.com のプレビュー下書きを Playwright で開き、冒頭にリンクを挿入
    （下書きの場合は DOM 操作で挿入 + 保存。公開済みの場合は編集→保存）
```

### 冪等性の確保

- Phase 6 実行前に meta.yaml の `review_ref.note_url` と今回のレビューURLを比較
- 一致する場合は「既に適用済み」としてスキップ
- markdown 側も `review_ref.note_url` の文字列を grep して存在確認

### 失敗時の挙動

- Phase 6 失敗はレビュー記事本体の成功をロールバックしない
- エラーを `.tmp/preview-backlink-failures.log` に記録し、手動再実行を促す

## 実装タスク（次フェーズ）

1. `.claude/skills/article-earnings-review/scripts/inject_preview_backlink.py` 作成
   - 入力: プレビューディレクトリ、レビューURL
   - 処理: meta.yaml 追記 + ローカル md 冒頭挿入（冪等）
2. `publish-to-note` スキルに「既存下書きの冒頭挿入モード」を追加（または新規 `inject-to-note-draft` スキル）
3. `/article-earnings-review` コマンドの Phase 5 完了後に上記を呼ぶ Phase 6 を追加
4. Phase 6 を `--skip-backlink` フラグで無効化できるようにする（テスト時用）

## オープンクエスチョン

- プレビュー記事が既に**公開済み**（note.com 上で public）の場合、編集→再保存すると SNS シェア済みのURLは不変か？ → 要確認（note.com の仕様上、記事 ID は不変）
- 複数のレビュー記事（例: Q1/Q2/Q3 プレビュー全てにレビュー追記）が蓄積する場合、冒頭が重くならないか → リンクは常に「最新のレビュー1本のみ」に上書きする方針
- SEO 影響: 既存記事を編集すると note.com の公開日時が更新される可能性があり、検索順位への影響あり得る → note.com の仕様依存、実測で確認

## 保存

本設計メモのパス: `docs/plan/SideBusiness/2026-04-16_preview-to-review-backlink-design.md`
