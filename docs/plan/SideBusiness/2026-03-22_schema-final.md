# 議論メモ: creator-neo4j A-3 スキーマ最終確定

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 全ノード定義（9種）

### Genre（既存維持）
- genre_id: STRING (UNIQUE) — "career", "beauty-romance", "spiritual"
- name: STRING

### ConceptCategory（新規、14種、拡張可能）
- name: STRING (UNIQUE) — PascalCase
- name_ja: STRING
- layer: STRING — "what" | "how"
- created_at: DATETIME

#### What層（9種）
MonetizationMethod(収益化手段), AcquisitionChannel(集客チャネル), Skill(スキル・技能), Audience(ターゲット層), RevenueModel(収益モデル), SuccessMetric(成果指標), ContentFormat(コンテンツ形式), Regulation(法規制), Milestone(時間軸目安)

#### How層（5種）
PersuasionTechnique(説得技法), EmotionalHook(感情トリガー), CopyFramework(文章構成パターン), Objection(読者の反論・障壁), Transformation(変化パターン)

### Concept（新規、Topic から移行）
- concept_id: STRING (UNIQUE)
- name: STRING (UNIQUE)
- description: STRING（任意）
- aliases: LIST&lt;STRING&gt;
- embedding: LIST&lt;FLOAT&gt;（384次元, e5-small）
- created_at: DATETIME
- updated_at: DATETIME

### Entity（既存改修）
- entity_id: STRING (UNIQUE)
- entity_key: STRING (UNIQUE) — "{name}::{entity_type}"
- name: STRING
- entity_type: STRING — platform, person, company, organization
- aliases: LIST&lt;STRING&gt; ← NEW
- embedding: LIST&lt;FLOAT&gt; ← NEW（384次元）
- created_at: DATETIME
- updated_at: DATETIME

### Fact（既存維持）
- fact_id: STRING (UNIQUE)
- text: STRING
- category: STRING — statistics, market_data, research, trend
- confidence: STRING — high, medium, low
- created_at: DATETIME

### Tip（既存維持）
- tip_id: STRING (UNIQUE)
- text: STRING
- category: STRING — strategy, tool, process, mindset
- difficulty: STRING — beginner, intermediate, advanced
- created_at: DATETIME

### Story（既存維持）
- story_id: STRING (UNIQUE)
- text: STRING
- outcome: STRING — success, failure, mixed, ongoing
- timeline: STRING
- created_at: DATETIME

### Source（既存改修）
- source_id: STRING (UNIQUE)
- url: STRING
- title: STRING
- source_type: STRING — web, reddit, blog, report
- authority_level: STRING — official, media, blog, social
- language: STRING — ja, en ← NEW
- published_at: DATETIME ← NEW
- collected_at: DATETIME

### Domain（新規）
- name: STRING (UNIQUE) — "note.com"
- country: STRING — "jp", "us"
- category: STRING — "ugc_platform", "news", "social", "official"
- trust_score: FLOAT — 0.0〜1.0（任意）
- created_at: DATETIME

## 全リレーション定義（12種）

| # | リレーション | From | To | プロパティ | 多重度 |
|---|------------|------|-----|-----------|--------|
| 1 | IS_A | Concept | ConceptCategory | — | N:1 |
| 2 | SERVES_AS | Entity | Concept | context（任意） | N:M |
| 3 | ABOUT | Fact/Tip/Story | Concept | — | N:M |
| 4 | MENTIONS | Fact/Tip/Story | Entity | — | N:M |
| 5 | IN_GENRE | Fact/Tip/Story | Genre | — | N:1 |
| 6 | FROM_SOURCE | Fact/Tip/Story | Source | — | N:1 |
| 7 | FROM_DOMAIN | Source | Domain | — | N:1 |
| 8 | ENABLES | Concept | Concept | context（任意） | N:M |
| 9 | REQUIRES | Concept | Concept | context（任意） | N:M |
| 10 | COMPETES_WITH | Concept | Concept | — | N:M |

## 制約・インデックス

### UNIQUE制約（10個）
- Genre.genre_id, Entity.entity_id, Entity.entity_key, Fact.fact_id, Tip.tip_id, Story.story_id, Source.source_id（既存7個）
- ConceptCategory.name, Concept.concept_id, Concept.name（新規3個）

### インデックス（4個）
- Entity.entity_type（既存）
- ConceptCategory.layer（新規）
- Full-Text: Entity.name（新規、ファジーマッチング第3層）
- Full-Text: Concept.name（新規、ファジーマッチング第3層）

## 廃止対象
- Topic ラベル → Concept にリラベル
- Topic.genre_id → 削除（Concept はジャンル中立）
- Topic の IN_GENRE → Content に移動後削除
- RELATES_TO → ENABLES/REQUIRES/COMPETES_WITH に分離
- Service(16件), Account(3件) → Entity 移行 or Archived

## 構造図

```
                    ConceptCategory (14種, 拡張可能)
                         ↑ IS_A
Genre ←── IN_GENRE ── Fact/Tip/Story ── ABOUT ──→ Concept
                         │                          ↑ SERVES_AS
                         │ FROM_SOURCE               Entity
                         ↓                          (aliases, embedding)
                       Source ── FROM_DOMAIN ──→ Domain

          Fact/Tip/Story ── MENTIONS ──→ Entity
          Concept ── ENABLES/REQUIRES/COMPETES_WITH ──→ Concept
```

## ファジーマッチング4層（別ドキュメント参照）
→ `2026-03-22_fuzzy-matching-design.md`

## 次のタスク
- A-4: Entity 正規化ルール
- B-1: Entity 抽出プロンプト改修
- B-2: Entity リンキング実装（4層マッチング）
