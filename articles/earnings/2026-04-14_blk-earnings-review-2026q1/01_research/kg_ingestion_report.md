# KG 投入レポート: BlackRock Q1 2026 決算レビュー

> 投入日時: 2026-04-14 18:13 JST
> session_id: `article-research-blk-earnings-review-2026q1-20260414-1810`
> 対象インスタンス: research-neo4j (bolt://localhost:7687)

## 投入パイプライン

```
emit_research_queue.py → entity_linker.py → neo4j_loader.py
```

- 入力 JSON: `.tmp/research-input/article-research-blk-earnings-review-2026q1-20260414-1810.json`
- graph-queue: `.tmp/graph-queue/web-research/gq-20260414091257-988e9fa4.json`
- resolved: `.tmp/graph-queue/web-research/gq-20260414091257-988e9fa4.resolved.json`
- Loader exit code: 0（成功）

## 投入結果

### ノード
| ラベル | 投入件数（本セッション） | 投入後総件数（BlackRock関連） |
|-------|----------------------|-----------------------------|
| Source | 8 | 10 |
| Fact | 8（うちBlackRock関連リンク10件） | 10 |
| Entity（Company/Product/Person） | 8 | — |
| Topic | 3 | — |

### 主要リレーション
- `Fact-[:RELATES_TO]->Company {name:'BlackRock'}`: 10件
- `Fact-[:EXTRACTED_FROM]->Source`: 投入済み
- `Source-[:ABOUT]->Topic`: 投入済み

### authority_level 分布
- official: 1（BlackRock IR Q4 Release PDF）
- analyst: 3（Zacks/Benzinga/Yahoo）
- media: 4（TradingView/CNBC/Bloomberg/Nasdaq）

## ギャップ解消状況

| ギャップID | 解消 | 備考 |
|----------|-----|-----|
| G1 stale_data | ✅ 部分解消 | published_at 付きソース 8件追加 |
| G2 missing_financials | ✅ 解消 | Q4 2025 実績・Q1 2026 コンセンサスを Fact として投入 |
| G3 no_coverage | ⚠ 発表待ち | Q1 2026 実績ソースは決算発表後に別セッションで投入予定 |
| G4 missing_claim_schema | ❌ 対象外 | 既存データ修正は別タスク |
| G5 fact_content_missing | ❌ 対象外 | 既存データ修正は別タスク |

## 次のアクション

1. **決算発表後（2026-04-14 21:30 JST 以降）**
   - BlackRock IR Q1 2026 プレスリリース URL 取得
   - SEC EDGAR 8-K の `analyze_8k` 実行
   - 実績値と株価反応を以下のコマンドで追加投入:
     ```
     session_id: article-research-blk-earnings-review-2026q1-update-20260414-2200
     ```
2. **ドラフト執筆**: 実績反映後に `/article-draft @articles/earnings/2026-04-14_blk-earnings-review-2026q1/`

## 投入前チェックリスト（実施済み）

- [x] 全ソースに `authority_level` 設定
- [x] 全ファクトの `source_url` が `sources` 内URLと一致
- [x] ソース 3件以上（8件）
- [x] graph-queue JSON の fact_entity リレーションタイプが RELATES_TO
- [x] MATCH クエリで投入前のデータ件数確認（BlackRock Fact: 2→10）
