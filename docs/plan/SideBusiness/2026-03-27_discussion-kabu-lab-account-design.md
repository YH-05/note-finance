# 議論メモ: 株投資ラボ アカウント設計

**日付**: 2026-03-27
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-27-kabu-lab-account-design
**前回の議論**: disc-2026-03-27-finance-article-category-refocus（カテゴリ再編）

---

## 背景・コンテキスト

- 金融記事カテゴリ再編（5カテゴリ確定）が完了した状態で、アカウントとしての要件を正式定義
- 他の3ブランド（career_sister/みつき/self-dev）はcreator-neo4jベースだが、金融記事執筆は性質が異なる
- research-neo4jに銘柄・マクロ調査データが大量蓄積済み → そこから記事・投稿を生成するのが自然

---

## 決定事項

### dec-2026-03-27-kabu-lab-name
**アカウント名を「株投資ラボ」に確定**

### dec-2026-03-27-kabu-lab-platform
**プラットフォーム: note.com（既存）+ Threads（新規作成）**

- note.com: 既存アカウントを継続使用（5カテゴリ体制）
- Threads: 株投資ラボとして新規作成予定
- Instagram は含まない（投資コンテンツとの親和性から除外）

### dec-2026-03-27-kabu-lab-monetization
**収益化を主目的とする**

- 具体的な収益モデル（ASP/有料記事/メンバーシップ）は別途策定

### dec-2026-03-27-kabu-lab-neo4j
**データ基盤は research-neo4j（creator-neo4j ではない）**

| 比較 | 株投資ラボ | 他3ブランド（career_sister/みつき/self-dev） |
|------|------------|----------------------------------------------|
| データ基盤 | research-neo4j | creator-neo4j |
| データ内容 | 銘柄・マクロ調査 Fact/Claim/Entity | クリエイター知識・SNS戦略 |
| 記事生成 | topic-discovery → article-init → article-draft | creator-enrichment → 投稿文生成 |
| 投稿生成 | research-neo4j → Threads 投稿文 | creator-neo4j → career-sister-writer 等 |

既存ワークフロー（topic-discovery / article-init / article-draft / article-critique / article-publish）はいずれも research-neo4j 接続済みのため、そのまま活用可能。

---

## アカウント全体設計

| 項目 | 内容 |
|------|------|
| アカウント名 | 株投資ラボ |
| プラットフォーム | note.com + Threads |
| カテゴリ | macro_economy / stock_analysis / asset_management / investment_education / market_report |
| データ基盤 | research-neo4j（bolt://localhost:7688） |
| 目的 | 収益化 |
| Threads状態 | 新規作成待ち |

---

## アクションアイテム

- [ ] Threadsアカウント作成（株投資ラボ） (優先度: 高) `act-2026-03-27-kabu-lab-001`
- [ ] 収益化モデル策定（ASP/有料記事/メンバーシップの優先順位と具体案） (優先度: 高) `act-2026-03-27-kabu-lab-002`
- [ ] research-neo4j → note記事/Threads投稿文生成ワークフローの動作確認・整備 (優先度: 中) `act-2026-03-27-kabu-lab-003`

---

## 次回の議論トピック

- 収益化モデルの具体案（投資コンテンツに合うASP案件・有料記事戦略）
- Threads投稿文の生成ワークフロー設計（research-neo4j → x-post-generator との接続）
- 株投資ラボのブランドトーン・投稿スタイル設計

---

## 関連ドキュメント

- カテゴリ再編: `docs/plan/SideBusiness/2026-03-27_discussion-finance-category-refocus.md`
- KGワークフロー統合: `docs/plan/SideBusiness/2026-03-26_discussion-note-finance-workflow-kg-integration.md`
- 3ブランド体制: `docs/plan/SideBusiness/2026-03-27_discussion-3brand-role-design.md`
