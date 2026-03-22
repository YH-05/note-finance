# 議論メモ: creator-neo4j ファジーマッチング設計

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 背景・コンテキスト

A-3（スキーマ設計）の一環として、Entity/Concept の MERGE 時にファジーマッチングをどう実現するかを議論。
Neo4j の MERGE は完全一致のみのため、表記揺れ・日英変換・概念類義語への対策が必要。

## 調査結果

### Neo4j 公式ベストプラクティス
- 3段階マッチング：Deterministic → Probabilistic → Graph-based
- APOC ライブラリの文字列類似度関数（Levenshtein, Jaro-Winkler, Sorensen-Dice）
- Full-Text Index + APOC の2段階フィルタが推奨
- Embedding ベースの手法（CNN/Transformer）も紹介されている

### APOC の性質
- **LLM は一切使っていない**（純粋なアルゴリズム）
- 文字列の**形の類似度**（syntactic）であり**意味の類似度**（semantic）ではない
- 日英変換（Instagram vs インスタグラム）はスコア 0.0 → APOC だけでは不可能

### Embedding モデル比較

| モデル | パラメータ | メモリ | 推論速度 | 正解スコア | false positive |
|--------|----------|--------|---------|-----------|---------------|
| static-similarity-mrl-multilingual-v1 | 5M | 20MB | 0.02s | 低（0.08-0.56） | — |
| **multilingual-e5-small** | **118M** | **470MB** | **0.14s** | **高（0.81-0.93）** | **なし** |
| multilingual-e5-base | 278M | 1.1GB | 1.08s | 中（0.78-0.89） | **あり（副業/美容=0.87）** |

## 決定事項

1. **4層マッチング構造**
   - 第1層: LLM 正規化（抽出時、コスト0）
   - 第2層: aliases 完全一致（Cypher、低コスト）
   - 第3層: APOC 文字列類似度（Neo4j内完結、同一言語タイポ対応）
   - 第4層: multilingual-e5-small Embedding（Python側、日英・類義語対応）

2. **multilingual-e5-small 採用**（base より全面的に優れる）

3. **APOC インストール済み**（creator-neo4j に apoc-5.26.21-core.jar）

4. **しきい値**: Levenshtein > 0.8、Sorensen-Dice > 0.85、cosine similarity > 0.8

## スキーマへの追加プロパティ

- `aliases: LIST<STRING>` — Entity, Concept に追加（第2層用）
- `embedding: LIST<FLOAT>` — Entity, Concept に追加（第4層用、384次元）
- Full-Text Index — Entity.name, Concept.name に作成（第3層用）

## 未決事項

- 第4層の全件スキャン問題（Entity が数千件に成長した場合の blocking 戦略）

## 次の議論トピック

- A-3 スキーマ設計の最終確定（ファジーマッチング分を含む）
- A-4 Entity 正規化ルール
