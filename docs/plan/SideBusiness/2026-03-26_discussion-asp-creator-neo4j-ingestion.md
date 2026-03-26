# 議論メモ: 33 ASP creator-neo4j 投入完了

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

副業/アフィリエイト領域のナレッジグラフ構築として、33社のアフィリエイトASP全社を調査し、creator-neo4j（creator-2.0スキーマ）に投入するタスク。前セッションから継続して2セッションにわたり完了した。

対象33社:
- **グループA（16社）**: A8.net, もしもアフィリエイト, afb, バリューコマース, 楽天アフィリエイト, Amazonアソシエイト, Google AdSense, 忍者AdMax, medi8, i-mobile, nend, Zucks, アクセストレード, JANet, リンクシェア, TCSアフィリエイト
- **グループB（12社）**: インフォトップ, インフォカート, フェルマ, マネートラック, ふくろうラボ, Smart-C, Zucks Affiliate, レントラックス, アイモバイルアフィリエイト, AD.TRACK, seedApp, Circuit X
- **グループC（5種）**: 直ASP, 代理店クローズド案件, インフルエンサー限定ASP, LINE/リスト特化非公開案件, 海外ASP（ClickBank/Digistore24）

## 投入内容サマリー

### Phase 2 ノード投入

| ノード | 件数 |
|--------|------|
| Fact | 32件 |
| Tip | 30件 |
| Entity | 46件（既存含む） |
| Concept | 多数（既存含む） |
| Source | 多数 |
| Domain | 多数 |

### Phase 3 リレーション投入

| リレーション | 新規作成 |
|---|---|
| IS_A (Concept → ConceptCategory) | 21件 |
| SERVES_AS (Entity → Concept) | 44件 |
| ABOUT Fact/Tip → Concept | 34+32件 |
| FROM_SOURCE Fact/Tip → Source | 29+20件 |
| IN_GENRE Fact/Tip → Genre | 29+30件 |
| MENTIONS Fact/Tip → Entity | 30+24件 |
| FROM_DOMAIN Source → Domain | 33件 |
| ENABLES Concept → Concept | 5件 |
| REQUIRES Concept → Concept | 7件 |
| RELATES_TO Concept → Concept | 7件 |
| RELATED_TO Concept → Concept | 3件 |

### Phase 4 検証結果

- 全 Fact/Tip: ABOUT・FROM_SOURCE・IN_GENRE が各1件、孤立なし
- DB全体（投入後）: Concept 4,363 / Fact 986 / Tip 835 / Entity 827 / Story 413

## 決定事項

1. **dec-2026-03-26-asp-ingestion-complete**: 33社のASPデータをcreator-neo4j（creator-2.0）に投入完了。全コンテンツノードの接続性を確認。
2. **dec-2026-03-26-asp-creator20-schema**: ASPデータの管理にcreator-2.0スキーマを採用。ConceptCategory（MonetizationMethod/AcquisitionChannel）でASP固有Conceptを分類。

## アクションアイテム

- [ ] **[高]** creator-neo4j のASPデータを活用して副業/アフィリエイト記事の初稿を生成する（`act-2026-03-26-asp-article-draft`）
- [ ] **[中]** article-research で creator-neo4j ASPデータを検索するワークフローを整備（`act-2026-03-26-asp-kg-search-workflow`）

## 次回の議論トピック

- ASPデータを使った具体的な記事テーマの決定（比較記事 vs. 入門記事 vs. 上級者向け）
- `/topic-discovery` でASP関連トピックを抽出して記事計画を立てる

## 技術メモ

- Group C の `about_fact` に `Entity → Fact` パターン（スキーマ外）が混在していたため、`Fact → Concept` の ABOUT のみ投入しスキップ
- Group B の Source ノードは `name` フィールドを使用（`title` でなく）
- ClickBank は既存 entity_id `2aa172af-2a3d-558f-9391-aac3e7270c96` を引き継いで MERGE
- MERGE により冪等性保証済み（グループ間の重複ファクト・エンティティも問題なし）
