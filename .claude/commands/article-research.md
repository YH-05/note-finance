---
description: カテゴリに応じたリサーチを実行します。
argument-hint: @<article_dir>
---

カテゴリに応じたリサーチを実行します。
research-neo4jから既存データを照会し、情報ギャップを特定した上でWeb検索を行い、結果をNeo4jに永続化します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| @article_dir | ○ | - | 記事ディレクトリのパス（`articles/{category}/{YYYY-MM-DD}_{slug}/`） |

## 引数の解釈ルール

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-research @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/
```

## 処理フロー

```
Step 0: KG既存データ照会 + ギャップ分析（全カテゴリ共通）
├── research-neo4j から関連 Entity/Topic/Fact/Claim を照会
├── 5観点でギャップを特定（鮮度/センチメント偏り/カバレッジ/未回答Q/数値データ）
└── 01_research/kg_gap_report.md に出力

Step 1: meta.yaml 読み込み
├── category を取得
└── カテゴリ別追加パラメータを取得

Step 2: カテゴリ別リサーチ実行（ギャップ優先検索）
├── stock_analysis    → investment-research スキル
├── macro_economy     → investment-research スキル
├── quant_analysis    → investment-research スキル
├── investment_education → investment-research スキル
├── asset_management   → asset-management-workflow Phase 1
├── side_business (type: case_study)  → Web検索 + Reddit + RSS（事例収集+パターン抽出）
├── side_business (type: experience)  → experience-db-workflow Phase 1-2
└── market_report     → generate-market-report Phase 2-3

Step 3: 結果保存・ステータス更新
├── 01_research/ にリサーチ成果物を保存
└── meta.yaml の workflow.research = "done"

Step 4: KG永続化（全カテゴリ共通）
├── 検索結果から入力 JSON を構築
├── emit_graph_queue.py --command web-research で graph-queue 生成
├── /save-to-graph で Neo4j に投入
└── 01_research/kg_ingestion_report.md に投入結果を記録
```

## 実行手順

### Step 0: KG既存データ照会 + ギャップ分析

参照: `.claude/skills/investment-research/references/kg-gap-analysis.md`

1. **テーマからキーワード抽出**

   `meta.yaml` の `topic` フィールドからキーワードを抽出する。

   ```
   例: "日銀利上げの円相場への構造的影響" → ["日銀", "BOJ", "利上げ", "円", "金利"]
   ```

2. **research-neo4j 照会**

   `mcp__neo4j-research__research-read_neo4j_cypher` を ToolSearch でロードし、以下を照会:

   - 関連 Entity ノード（名前・エンティティタイプ・Fact/Claim件数）
   - 関連 Topic ノード（カテゴリ・ソース件数）
   - ソース鮮度（最新 published_at）
   - 既存 Fact の時系列（直近20件）
   - Claim のセンチメント分布（bullish/bearish/neutral）
   - 未回答 Question ノード（status: open/investigating）

   **Neo4j未起動時**: 警告を出力してStep 0をスキップし、Step 1に進む。

3. **ギャップ分析**

   | ギャップ種別 | 判定条件 | 優先度 |
   |------------|---------|--------|
   | stale_data | 最新ソース < today - 30d | HIGH |
   | missing_bear_case | bullish > 0, bearish == 0 | MEDIUM |
   | missing_bull_case | bearish > 0, bullish == 0 | MEDIUM |
   | no_coverage | 必要エンティティの fact/claim が0件 | HIGH |
   | open_questions | 未回答 Question ノード存在 | HIGH/MEDIUM |
   | missing_financials | company/etf/index の FDP が0件 | MEDIUM |

4. **ギャップレポート出力**

   `01_research/kg_gap_report.md` に以下を出力:
   - 既存データサマリー（エンティティ数、ファクト数、クレーム数、ソース数）
   - 特定されたギャップ一覧（優先度別）
   - ギャップ解消用の推奨検索クエリ

### Step 1: meta.yaml 読み込み

1. **記事ディレクトリの解決**

   引数から記事ディレクトリを特定し、`meta.yaml` を読み込みます。

   ```yaml
   # 以下のフィールドを確認
   category: "stock_analysis"    # 必須
   symbols: [...]                # stock_analysis, quant_analysis
   fred_series: [...]            # macro_economy
   theme: "..."                  # side_business
   date_range: { start, end }   # stock_analysis, macro_economy, quant_analysis
   ```

2. **ステータス確認**

   `workflow.research` が既に `"done"` の場合は再実行の確認を行います：

   ```
   リサーチは既に完了しています。再実行しますか？ (y/n)
   ```

### Step 2: カテゴリ別リサーチ実行

Step 0 で特定されたギャップ情報を各スキルに渡し、**ギャップ解消を優先した検索**を行う。

#### stock_analysis / macro_economy / quant_analysis / investment_education

既存の `investment-research` スキルに処理を委譲します。

```
実行内容:
- Phase 0: KGギャップ情報を受け取り、検索クエリの優先順位を調整
- Phase 1: マルチソース検索（ギャップ解消クエリを優先配分）
  - finance-market-data（シンボル/指標データ）
  - finance-web（Web検索）
  - finance-wiki（Wikipedia参照）
  - finance-sec-filings（SEC開示情報、stock_analysis時）
- Phase 2: ファクト整理（KG既存ファクトとの重複チェック含む）
- Phase 3: 論点抽出（ギャップ解消確認含む）
- Phase 4: リサーチノート出力
```

出力先: `01_research/` 配下に各成果物を保存

#### asset_management

既存の `asset-management-workflow` スキルの Phase 1 に処理を委譲します。

```
実行内容:
- JP RSSプリセットからソース収集
- テーマ別キーワードマッチング
- 公開日時フィルタリング
- ソースキュレーション
```

出力先: `01_research/` 配下にセッションデータとソースを保存

#### side_business

既存の `experience-db-workflow` スキルの Phase 1-2 に処理を委譲します。

```
実行内容:
- Phase 1: ソース収集（Reddit + RSS + Web検索 + note.com巡回）
- Phase 2: 合成パターン生成（experience-synthesizer）
```

出力先: `01_research/` 配下にソースと合成データを保存

#### market_report

既存の `generate-market-report` コマンドの Phase 2-3 に処理を委譲します。

```
実行内容:
- 市場データ収集（yahoo_finance, FRED）
- ニュース検索（RSS/Tavily またはローカルJSON）
- データ整理・分析
```

出力先: `01_research/` 配下に市場データとニュースを保存

### Step 3: 結果保存・ステータス更新

3. **meta.yaml の更新**

   ```yaml
   workflow:
     research: "done"    # ← 更新
   updated_at: "YYYY-MM-DD"
   ```

4. **リサーチ結果の報告**

   ```markdown
   ## リサーチ完了

   ### 記事情報
   - **トピック**: {topic}
   - **カテゴリ**: {category}

   ### KGギャップ分析
   - 特定ギャップ: {n}件
   - 解消済み: {n}件
   - 残存: {n}件

   ### 収集結果
   - ソース数: {source_count}件
   - 主張/ポイント: {claims_count}件
   - データファイル: {file_count}件

   ### 出力先
   `articles/{category}/{YYYY-MM-DD}_{slug}/01_research/`

   ### 次のステップ
   1. リサーチ結果を確認
   2. ドラフト作成: `/article-draft @articles/{category}/{YYYY-MM-DD}_{slug}/`
   ```

### Step 4: KG永続化

参照: `.claude/skills/emit-research-queue/SKILL.md`
参照: `.claude/rules/neo4j-write-rules.md`

Step 2 で収集した検索結果を research-neo4j に永続化する。

1. **入力JSON構築**

   検索結果から以下の構造の入力JSONを構築する:

   ```json
   {
     "session_id": "article-research-{slug}-{YYYYMMDD-HHMM}",
     "research_topic": "{meta.yaml の topic}",
     "as_of_date": "{today}",
     "sources": [
       {
         "url": "{URL}",
         "title": "{タイトル}",
         "authority_level": "{official|analyst|media|blog|social}",
         "published_at": "{YYYY-MM-DD}",
         "source_type": "{web|news|blog}"
       }
     ],
     "entities": [
       { "name": "{名前}", "entity_type": "{company|index|...}" }
     ],
     "topics": [
       { "name": "{トピック名}", "category": "{macro|equity|...}" }
     ],
     "facts": [
       {
         "content": "{ファクト内容}",
         "source_url": "{出典URL}",
         "confidence": 0.9,
         "about_entities": [
           { "name": "{entity}", "entity_type": "{type}" }
         ]
       }
     ]
   }
   ```

   **投入前チェックリスト** (`.claude/rules/neo4j-write-rules.md` 準拠):
   - [ ] 全ソースに `authority_level` が設定されているか
   - [ ] 全ファクトの `source_url` が `sources` 内の URL と一致するか
   - [ ] ソースが3件以上あるか（少なすぎる場合は投入をスキップ）

2. **graph-queue JSON 生成**

   ```bash
   uv run python scripts/emit_graph_queue.py \
     --command web-research \
     --input .tmp/research-input/{session_id}.json
   ```

3. **Neo4j 投入**

   `/save-to-graph` スキルを呼び出す。

4. **投入結果の記録**

   `01_research/kg_ingestion_report.md` に投入結果を記録:
   - 投入ノード数（Source, Entity, Topic, Fact）
   - 投入リレーション数
   - ギャップ解消状況

   **Neo4j未起動時**: 警告を出力してStep 4をスキップ。入力JSONは `.tmp/research-input/` に保持し、後から手動で投入可能。

## エラーハンドリング

### meta.yaml が見つからない

```
エラー: meta.yaml が見つかりません

指定パス: {article_dir}

対処法:
- /article-init でフォルダを初期化してください
- パスが正しいか確認してください
```

### カテゴリが不明

```
エラー: 不明なカテゴリです: {category}

有効なカテゴリ:
- asset_management, side_business, macro_economy
- stock_analysis, market_report, quant_analysis, investment_education
```

### Neo4j未起動

```
警告: research-neo4j (bolt://localhost:7688) に接続できません

KG照会・永続化をスキップしてリサーチを続行します。
検索結果の入力JSONは .tmp/research-input/ に保存されます。
Neo4j起動後に手動で投入可能です:
  uv run python scripts/emit_graph_queue.py --command web-research --input .tmp/research-input/{session_id}.json
  /save-to-graph --source web-research
```

### データ収集失敗

```
エラー: データ収集中に問題が発生しました

失敗した処理: {failed_step}
エラー内容: {error_message}

対処法:
1. ネットワーク接続を確認
2. シンボル/指標名が正しいか確認
3. 再実行: /article-research @{article_dir}
```

## 関連コマンド

- **前提コマンド**: `/article-init`
- **後続コマンド**: `/article-draft`
- **統合コマンド**: `/article-full`
- **使用スキル**: investment-research, asset-management-workflow, experience-db-workflow, emit-research-queue, save-to-graph
