# 議論メモ: note.com 引用リンクをカード表示で貼るルール改訂

**日付**: 2026-05-06
**参加**: ユーザー + AI (Claude Opus 4.7 1M)
**Discussion ID**: `disc-2026-05-06-note-link-card-rule`
**関連ファイル**: `.claude/rules/article-quality-standards.md`, `scripts/note_publisher/markdown_parser.py`

## 背景・コンテキスト

ユーザーから株投資ラボの note.com 記事執筆ルールの追加要望:

> 参考文献や情報を入れる時（例：マッキンゼーのレポートによると...）、引用の文章の段落と次の段落との間に参照したリンクを貼り付けるようにして。なお、URLをそのまま貼るのではなく、note上でリンク情報がカードとして表示されるようにして。

調査の結果、既存ルールに **重大な機能不全** が判明したため全面改訂を行った。

## 議論のサマリー

### 発見した重大な問題

`scripts/note_publisher/markdown_parser.py:54` に以下のコメントが既にあった:

```python
# AIDEV-NOTE: Inline link pattern [text](url) — note.com does not render
# markdown links, so these are stripped to plain text during conversion.
_INLINE_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\([^)]+\)")
```

`_strip_inline_markdown` が投稿パイプライン内で `[text](url)` を `text` のみに変換し、**URLを完全に除去**する実装。

一方、`.claude/rules/article-quality-standards.md` ルール2（旧版）は `[テキスト](URL)` 形式のマークダウンリンクを推奨していた。つまり:

> ルール通りに書いた記事は note.com 上で URL が消える

という二重不整合状態が継続していた。

### note.com のリンクカード化仕様（ヘルプセンター確認）

- URL を **段落として独立** させた行のみ自動カード化される
- URL 前後に他の文字（句読点・空白・テキスト）が混在するとカード化されない
- 短縮URL（bit.ly等）や非対応サービスはテキストリンクにフォールバック
- 1段落に1URL限定（複数並べると自動埋め込み無効化）

参考:
- https://www.help-note.com/hc/ja/articles/360019596133
- https://www.help-note.com/hc/ja/articles/360008882854
- https://note.com/fladdict/n/n6012cf1b49fd

## 決定事項

### Decision A (`dec-2026-05-06-001`): マークダウンリンク `[text](url)` を全面禁止

**Status**: active
**Context**: note.com 投稿パイプライン (`markdown_parser.py::_strip_inline_markdown`) が `[text](url)` をプレーンテキストに変換し URL を除去するため、マークダウンリンクは note.com 上で機能しない。記事の信頼性・トレーサビリティを担保するためには、note.com の仕様に合致する別形式が必要。

**内容**:
- 記事内で `[テキスト](URL)` 形式のインラインマークダウンリンクを使用しない
- article-critique はマークダウンリンクの残存を検出してエラーにする
- finance-article-writer / article-draft / article-revise は新規生成時にマークダウンリンクを作らない

### Decision B (`dec-2026-05-06-002`): 引用ソースは「URL単独段落」で貼る

**Status**: active
**Context**: ユーザー指示「引用の段落と次の段落の間に参照リンクを貼り、note上でカードとして表示」に基づき、note.com の自動カード化仕様に整合する形式を採用する。

**内容**:
- 引用段落の直後に **空行 → URL単独段落 → 空行 → 次段落** の構造で配置
- URL 段落には他の文字（句読点・空白・テキスト）を一切混ぜない
- 1段落に1URL。複数ソース引用時は段落を分ける
- オリジナルの長い URL を使用（短縮URLはカード化されない）

**配置パターン例**:

```markdown
マッキンゼーのレポートによると、生成AI市場は2030年までに年率40%で成長し、世界経済への寄与額は2.6〜4.4兆ドルに達する見込みです。

https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier

一方、ガートナーの分析では...
```

## アクションアイテム

- [x] `.claude/rules/article-quality-standards.md` ルール2を全面改訂（マークダウンリンク禁止・URL独立段落必須） (優先度: 高) — 完了
- [x] `~/.claude/.../memory/feedback_article_quality.md` 項目2を改訂 (優先度: 高) — 完了
- [ ] `act-2026-05-06-001`: 既存記事の点検バッチ作成（`articles/**/revised_draft.md` で `\[.*\]\(http` 残存を grep 検出） (優先度: 中)
- [ ] `act-2026-05-06-002`: `article-critique` の批評観点に「マークダウンリンク残存検出」「引用直後にURL段落があるか」を明示的に追加 (優先度: 中)
- [ ] `act-2026-05-06-003`: `finance-article-writer` / `article-draft` / `article-revise` スキルの内部プロンプトを確認し、URL段落形式で生成するよう更新が必要か判定 (優先度: 中)
- [ ] `act-2026-05-06-004`: 既存ノードへの本Discussion保存（**Neo4j未起動のため保留**。次回起動時に下記Cypherを再投入） (優先度: 低)

## 次回の議論トピック

- `markdown_parser.py` の挙動を変更すべきか: `[text](url)` を投稿時に「text\n\nurl」（テキスト + 段落URL）へ自動変換する案。これがあれば既存記事の人手修正が不要になる。
- 既存記事の一括バッチ修正の方針（修正→再投稿 vs 放置 vs 新規記事のみ新ルール適用）

## 参考情報

- note公式ヘルプ: [テキスト記事に埋め込みできるサービス一覧](https://www.help-note.com/hc/ja/articles/360019596133)
- note公式ヘルプ: [文章にリンクを設定する](https://www.help-note.com/hc/ja/articles/360008882854)
- 深津貴之氏: [記事内でのサイトの埋め込み（β）](https://note.com/fladdict/n/n6012cf1b49fd)

## Neo4j 投入用 Cypher（次回起動時に実行）

```cypher
// Discussion
MERGE (d:Discussion {discussion_id: 'disc-2026-05-06-note-link-card-rule'})
SET d.title = 'note.com 引用リンクをカード表示で貼るルール改訂',
    d.date = date('2026-05-06'),
    d.summary = 'マークダウンリンクが投稿時に剥がれる重大な機能不全を発見。引用ソースをURL単独段落で貼る方式に全面改訂。',
    d.topics = ['note.com', 'リンクカード', '記事品質', 'markdown_parser', '引用フォーマット'],
    d.doc_path = 'docs/plan/SideBusiness/2026-05-06_discussion-note-link-card-rule.md',
    d.created_at = datetime();

// Decision A
MERGE (decA:Decision {decision_id: 'dec-2026-05-06-001'})
SET decA.content = 'マークダウンリンク [text](url) を記事内で全面禁止する',
    decA.context = 'scripts/note_publisher/markdown_parser.py::_strip_inline_markdown が投稿時にプレーンテキスト変換しURLを除去するため、note.com上で機能しない',
    decA.decided_at = date('2026-05-06'),
    decA.status = 'active',
    decA.created_at = datetime();

// Decision B
MERGE (decB:Decision {decision_id: 'dec-2026-05-06-002'})
SET decB.content = '引用ソースは引用段落の直後にURL単独段落として配置する（空行で挟む）',
    decB.context = 'note.comの仕様で単独段落のURLのみが自動リンクカード化される。ユーザー指示2026-05-06に基づく',
    decB.decided_at = date('2026-05-06'),
    decB.status = 'active',
    decB.created_at = datetime();

// ActionItem A
MERGE (a1:ActionItem {action_id: 'act-2026-05-06-001'})
SET a1.description = '既存記事の点検バッチ作成（articles/**/revised_draft.md でマークダウンリンク残存を grep 検出）',
    a1.priority = 'medium',
    a1.status = 'pending',
    a1.created_at = datetime();

// ActionItem B
MERGE (a2:ActionItem {action_id: 'act-2026-05-06-002'})
SET a2.description = 'article-critique の批評観点にマークダウンリンク残存検出と引用直後URL段落チェックを明示追加',
    a2.priority = 'medium',
    a2.status = 'pending',
    a2.created_at = datetime();

// ActionItem C
MERGE (a3:ActionItem {action_id: 'act-2026-05-06-003'})
SET a3.description = 'finance-article-writer / article-draft / article-revise の内部プロンプトをURL段落形式で生成するよう更新が必要か判定',
    a3.priority = 'medium',
    a3.status = 'pending',
    a3.created_at = datetime();

// リレーション
MATCH (d:Discussion {discussion_id: 'disc-2026-05-06-note-link-card-rule'})
MATCH (decA:Decision {decision_id: 'dec-2026-05-06-001'})
MATCH (decB:Decision {decision_id: 'dec-2026-05-06-002'})
MATCH (a1:ActionItem {action_id: 'act-2026-05-06-001'})
MATCH (a2:ActionItem {action_id: 'act-2026-05-06-002'})
MATCH (a3:ActionItem {action_id: 'act-2026-05-06-003'})
MERGE (d)-[:RESULTED_IN]->(decA)
MERGE (d)-[:RESULTED_IN]->(decB)
MERGE (d)-[:PRODUCED]->(a1)
MERGE (d)-[:PRODUCED]->(a2)
MERGE (d)-[:PRODUCED]->(a3);
```
