# 議論メモ: research-neo4j Entity廃止 DB移行実行

**日付**: 2026-04-03
**参加**: ユーザー + AI

## 背景・コンテキスト

Project #107 (Entity廃止・ラベル/ノード正規化) の全15 Issue (#302-#316) はコード側で CLOSED 済みだったが、
実際の DB 移行は未実行だった。feature/issues-302-308 ブランチにスクリプトは存在するが main 未マージ & DB 未適用。

本セッションで DB 移行を直接実行し、設計を反映した。

## 実施内容

### 1. #304 異ラベル同名マージ

- C判定10件の人手レビュー完了（A: 8件、B: 2件に確定）
  - A判定: DINKS世帯→Person, Netflix→Company, Preferred Networks→Company, 医療費控除→Topic, 日本株式市場→Topic, 確定申告→Topic, 資産形成→Topic, note→Company
  - B判定: IDR (Concept/UnitOfMeasure), getrichslowly.org (Domain/Topic)
- A判定54件（59マージ操作）を `apoc.refactor.mergeNodes` で一括実行
- `apoc.create.removeLabels` で不要ラベル除去
- 結果: 14,578 → 14,519 ノード (-59)、リレーション損失 7件のみ

### 2. ABOUT/MENTIONS → RELATES_TO

- ABOUT 5,343件 + MENTIONS 915件 = 6,258件を RELATES_TO に変換
- プロパティなし（CREATE+DELETE 方式）
- 変換後: ABOUT/MENTIONS ともに 0件

### 3. Entity レガシー削除

- Entity 制約 3件削除 (entity_id, entity_ticker, unique_entity_key)
- Entity インデックス 4件削除 (embedding, fulltext, fulltext_v2, type_idx)
- `cypher-shell` 直接実行（MCP write endpoint が DDL を拒否するため）

### 4. NODE KEY 制約導入

- 13ラベル全てに `name IS NODE KEY` 制約を作成
- 事前の重複チェックで全ラベル 0件確認済み

### 5. レガシープロパティ除去

- entity_id: 1,623件 REMOVE
- entity_type: 1,622件 REMOVE
- entity_key: 0件（既に除去済み）

## 最終検証結果

| 成功基準 | 結果 |
|---------|------|
| Entity ラベルのノードが 0 件 | 0件 Pass |
| 13ラベル全てに NODE KEY 制約 | 13件 Pass |
| ABOUT/MENTIONS が 0 件 | 0件 Pass |
| Entity 制約/インデックス残存なし | 0件 Pass |
| entity_id/entity_key/entity_type 残存なし | 0件 Pass |

**DB規模**: 14,519 ノード / 480,365 リレーション

## アクションアイテム

- [ ] feature/issues-302-308 ブランチを main にマージ（優先度: 高）
- [ ] docs/project/project-29/project.md のステータス更新（優先度: 中）
- [ ] /kg-quality-check で移行後の品質検証（優先度: 中）
- [ ] dec-2026-03-30-entity-multilabel を superseded に更新（優先度: 低）→ 実施済み

## 判定記録

- `data/migration/20260402_cross_label_same_name_judgments.json` (A=54, B=27, C=0)
