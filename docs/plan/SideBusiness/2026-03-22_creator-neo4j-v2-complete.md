# creator-neo4j v2 再設計 完了レポート

**日付**: 2026-03-22
**Phase A〜E 全完了**

## 実施サマリー

本日1セッションで、creator-neo4j の根本的な再設計（オントロジー定義→パイプライン実装→データ移行→品質検証→運用改修）を完了した。

## Phase 別成果

### Phase A: 設計（4タスク）
- A-1: 目的定義（記事素材検索 + ギャップ発見 + クロスジャンルパターン）
- A-2: オントロジー設計（14 ConceptCategory: What層9 + How層5）
- A-3: スキーマ設計（10ノード・11リレーション）
- A-4: Entity正規化ルール（Aliasノード + 4層ファジーマッチング）

### Phase B: パイプライン実装（4タスク）
- B-1: entity-extraction-prompt-v2.md（Entity/Concept分離抽出）
- B-2: scripts/entity_linker.py（3層マッチング: 完全一致→APOC→Embedding）
- B-3: scripts/emit_creator_queue_v2.py（schema creator-2.0）
- B-4: save-to-creator-graph guide-v2.md（10ノード11リレーションのMERGEパターン）

### Phase C: 既存データ移行（4タスク）
- C-1: Entity 88件再分類（29 Entity + 41 Concept + 18 削除）
- C-2: 全621コンテンツ ABOUT接続済み（Topic→Concept移行で自動達成）
- C-3: Source authority_level null 0件に（official 13/media 23/social 121/blog 169）
- C-4: 旧ラベル全廃止（Topic/Service/Monetization/Usecase/Account → Concept/Entity）

### Phase D: 品質保証（4タスク）
- D-1: オントロジー適合全パス
- D-2: 重複16件マージ
- D-3: 孤立Content 0件
- D-4: カバレッジ計測 → How層がほぼ空と判明

### Phase E: 運用改修（3タスク）
- E-1: SKILL.md v2パイプライン化（Phase 3→3.5→4）
- E-2: gap-analysis-queries-v2.md（6クエリ、ConceptCategory×ジャンル）
- E-3: Phase 4.5（既に実装済み）

## 最終スキーマ

### ノード（8種、稼働中）
Genre(3), ConceptCategory(14), Concept(1,209), Entity(43), Fact(339), Tip(221), Story(61), Source(326)

### リレーション（稼働中）
ABOUT(2,414), IS_A(1,209), IN_GENRE(986), FROM_SOURCE(562), MENTIONS(34)

### 新規インフラ
- APOC Core インストール済み
- Full-Text Index 3本（entity/concept/alias）
- UNIQUE制約 11個
- multilingual-e5-small ベンチマーク済み（470MB, CPU 0.14s/8件）

## 主要Decision（本日確定）
1. オントロジーファースト（データ投入より概念定義を先行）
2. 14 ConceptCategory（What 9 + How 5、データ駆動で拡張可能）
3. Entity/Concept分離（固有名詞 vs 一般概念、SERVES_ASで接続）
4. Aliasノード（プロパティではなくリレーション、Full-Text Index対応）
5. 4層ファジーマッチング（LLM正規化→Alias+APOC→Embedding）
6. multilingual-e5-small採用（baseより全面的に優れる）
7. Source domainのみリレーション化（type/authority/languageはプロパティ）
8. How層重点拡充（EmotionalHook/CopyFramework/Objection がほぼ空）

## 残タスク
- **Phase F**: 活用（記事素材クエリ設計、パターン発見クエリ、記事フロー統合）→ 次回セッション
- **Skill仮分類619件の精緻化** → enrichment運用で段階的に
- **Domain/Aliasノードの初期データ投入** → 次回enrichment時
- **How層コンテンツの重点収集** → 次回enrichment時
