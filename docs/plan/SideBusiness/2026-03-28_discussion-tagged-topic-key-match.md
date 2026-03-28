# 議論メモ: save-to-research-graph TAGGEDフェーズのtopic_keyマッチング推奨

**日付**: 2026-03-28
**発見経緯**: ASEANテレコム規制機関調査のKG投入検証（Phase 3c）

## 背景・コンテキスト

`/save-to-research-graph` スキルのPhase 3aでTAGGEDリレーション（Source→Topic, Fact→Topic）を投入する際、既存Topicノードへの紐付けが84件欠落した。

### 根本原因

Topicノードの構造:
```cypher
MERGE (t:Topic {topic_key: $topic_key})
ON CREATE SET t.topic_id = $topic_id  -- 初回作成時のみUUIDを設定
SET t.name = $name, t.category = $category
```

- 既存TopicノードはON CREATEで設定された**古いtopic_id**を保持し続ける
- graph-queueは実行ごとに**新規UUID**をtopic_idに生成する
- TAGGED MERGEが `MATCH (t:Topic {topic_id: $to_id})` でMATCHしようとすると、既存ノードには新UUID != 旧UUIDなので**サイレントに失敗**する

### 影響範囲（2026-03-28 ASEANセッション）

| 既存Topic | 旧topic_id | 欠落数 |
|-----------|-----------|--------|
| ASEAN Telecom Regulation | `asean-telecom-regulation` | 28件 |
| Telecom Regulation | `telecom-regulation` | 28件 |
| Spectrum Allocation | `spectrum-allocation` | 28件 |
| **合計** | | **84件** |

欠落したリレーション: TAGGED(Source→Topic) 39件 + TAGGED(Fact→Topic) 45件

事後修復: `topic_key`でMATCHしてMERGE再実行で解消。

## 決定事項

**save-to-research-graphスキルのTAGGEDフェーズ（Phase 3a.1/3a.2）でTopicのMATCHキーを`topic_id`から`topic_key`に変更する。**

```cypher
-- 修正前（問題あり）
MATCH (t:Topic {topic_id: $to_id})
MERGE (s)-[:TAGGED]->(t)

-- 修正後（推奨）
MATCH (t:Topic {topic_key: $to_key})
MERGE (s)-[:TAGGED]->(t)
```

graph-queue JSONのrelations.tagged / tagged_factも、`to_id`フィールドではなく`to_key`フィールドを使うよう合わせて修正する必要がある。

## アクションアイテム

- [ ] `.claude/skills/save-to-research-graph/SKILL.md` のPhase 3a.1/3a.2 TAGGEDフェーズのCypherを修正 (優先度: 高)
- [ ] `scripts/emit_research_queue.py` のweb-researchマッパーでrelations.tagged/tagged_factに`to_key`フィールドを追加 (優先度: 高)

## 参考

- 検証クエリで再現可能: `MATCH (t:Topic {topic_key: 'ASEAN Telecom Regulation::regulatory'}) RETURN t.topic_id` → スラッグ形式IDが返る
- MERGEのマッチキーはUNIQUE制約のあるビジネスキー（`topic_key`）を使うべきという原則の再確認
