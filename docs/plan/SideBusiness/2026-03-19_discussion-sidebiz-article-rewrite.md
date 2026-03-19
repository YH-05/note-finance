# 議論メモ: side_business既存記事の事例分析型への書き直し

**日付**: 2026-03-19
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-19-sidebiz-article-rewrite

## 背景・コンテキスト

2026-03-09に「副業・資産形成は事例分析型に転換」と決定（disc-2026-03-09-sidebiz-content-pivot）。
2026-03-16に「事例分析型に統一、合成パターン法の体験談は新規作成しない」と正式決定（disc-2026-03-16-sidebiz-article-format）。
ただし既存2本は「そのまま投稿」の予定だった。

今回、ユーザーが「既存記事も事例分析型に書き直す」と指示。

## 実行内容

### 対象記事と変更

| 記事 | 旧形式 | 新形式 | テンプレート |
|------|--------|--------|-------------|
| video-editing-freelance | 合成パターン法（一人称体験談） | 事例分析型（三人称分析者） | テンプレートA |
| ai-micro-sidehustle-triple | 合成パターン法（一人称体験談） | 事例分析型（三人称分析者） | テンプレートA |

### 変更ファイル

- `articles/side_business/2026-03-09_video-editing-freelance/02_draft/revised_draft.md` — 全面書き直し
- `articles/side_business/2026-03-09_video-editing-freelance/meta.yaml` — type: experience → case_study, title更新
- `articles/side_business/2026-03-16_ai-micro-sidehustle-triple/02_draft/revised_draft.md` — 全面書き直し
- `articles/side_business/2026-03-16_ai-micro-sidehustle-triple/meta.yaml` — type: experience → case_study, topic更新

### 品質基準対応

- マークダウン表 → PNG画像（generate_table_image.py）
  - video-editing: `images/table_income_progress.png`
  - ai-micro: `images/table_writing.png`, `table_goods.png`, `table_transcription.png`, `table_monthly_revenue.png`
- 統計データにソースURLをインライン埋め込み
- 分析者視点（三人称）、「です・ます」調

## 決定事項

1. **dec-2026-03-19-001**: 既存2本の合成パターン法記事を事例分析型に書き直し完了（3/16の「そのまま投稿」判断を撤回）

## アクションアイテム

- [ ] **act-2026-03-19-001** video-editing-freelance記事の批評実行（事例分析型4観点） (優先度: 中)
- [ ] **act-2026-03-19-002** ai-micro-sidehustle-triple記事の批評実行（事例分析型4観点） (優先度: 中)
- [ ] **act-2026-03-19-003** sidehustle-003-pendingを事例分析型で新規作成 (優先度: 中)

## メモリ更新

- `feedback_no_experience_articles.md` を新規作成（副業・資産形成は事例分析型に統一、合成パターン法は使わない）

## 参考情報

- 方針転換議論: `2026-03-09_discussion-content-pivot.md`
- 記事形式見直し議論: `2026-03-16_discussion-article-format-revision.md`
- 事例分析型テンプレート: `事例分析型テンプレート_v1.md`
