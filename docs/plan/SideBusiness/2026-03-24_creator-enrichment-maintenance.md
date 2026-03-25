# creator-neo4j enrichment 3サイクル + 品質改善 + e5-large切替

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j（副業・美容・スピリチュアルのナレッジグラフ）の自動拡充と品質改善を一連の流れで実施。

## 実施内容

### 1. creator-enrichment 3サイクル（15:52-17:30）

| サイクル | ジャンル | Fact | Tip | Story | Entity | Concept |
|---------|---------|:----:|:---:|:-----:|:------:|:-------:|
| 1 | spiritual | 3 | 3 | 4 | 11 | 32 |
| 2 | beauty-romance | 3 | 3 | 4 | 7 | 25 |
| 3 | career | 3 | 3 | 4 | 10 | 23 |
| **合計** | | **9** | **9** | **12** | **28** | **80** |

- Tavily API リミット超過 → 全サイクル WebSearch + Reddit フォールバック
- Story 12件（成功7・失敗3・混合2）を確保

### 2. 品質チェック（84.5点 B）

| カテゴリ | スコア | 前回 | 差分 |
|---------|:------:|:----:|:----:|
| Completeness | 82.7% | 73.8 | +8.9 |
| Consistency | 98.0% | 100.0 | -2.0 |
| Structural | 95.0% | 90.0 | +5.0 |
| Orphan | 80.0% | 75.6 | +4.4 |
| Content Balance | 72.0% | 75.9 | -3.9 |
| Source Quality | 87.0% | 95.3 | -8.3 |
| Taxonomy | 74.0% | 66.6 | +7.4 |

### 3. グループB修正

| 修正 | Before | After |
|------|--------|-------|
| Concept重複 | 15ペア | 0（apoc.refactor.mergeNodes） |
| Entity重複 | 4ペア | 0（3マージ + 1マルチロールskip） |
| source_type null | 185件 | 0件 |
| Entity孤立率 | 87.2% | 33.4%（MENTIONS +350件） |

### 4. ABOUT リンク改善（L1/L2/L3）

| レベル | 手法 | ABOUT追加 | 結果 |
|--------|------|:---------:|------|
| L1 | 分割キーワード部分一致（→・×括弧） | +390 | 有効 |
| L2 | Entity→SERVES_AS ブリッジ | +49 | 有効 |
| L3 | embedding cosine (e5-small) | +4,482 → ロールバック | **false positive 70-80%、見送り** |
| L3 | embedding cosine (e5-large) | 未実行 | TP率47%、見送り判断 |

### 5. e5-large 切替

- intfloat/multilingual-e5-small (384d) → **intfloat/multilingual-e5-large (1024d)**
- 全ノード ~5,200件を re-embed（M3 CPU で約2分20秒）
- Vector Index 5本を 1024d で再作成
- entity_linker.py も e5-large に更新
- ruri (cl-nagoya) はクロスリンガル非対応のため不採用

## 決定事項

1. **e5-large 全切替** — Entity Linking + 重複検出の精度向上のため。16GB M3 Macで問題なく動作
2. **L3 ABOUT 見送り** — ABOUT未接続Conceptはtaxonomyノードとして機能しており、embedding マッチングの false positive率が高すぎる
3. **Concept語順正規化ルール** — 「A・B」形式をUnicode順ソート、英語はTitle Case・単数形に統一

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `.env` | NEO4J_CREATOR_PASSWORD 追加 |
| `scripts/creator_embed_nodes.py` | e5-large対応、Content embed対応 |
| `scripts/entity_linker.py` | e5-large対応 |
| `.claude/skills/creator-enrichment/SKILL.md` | Entity Linker コマンド修正 |
| `.claude/skills/creator-enrichment/references/entity-extraction-prompt-v2.md` | 語順正規化ルール追加 |

## 残存課題

- Story比率 11-15%（目標25%）→ 次回enrichmentで自動改善
- ABOUT未接続Concept 1,494件 → enrichmentで自然接続を待つ
- ジャンル誤分類（v1 How層データ）→ cross_genre フラグで対応検討
- creator_embed_nodes.py の --force バグ（同一バッチ繰返し）→ 要修正
