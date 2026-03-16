---
description: 新規記事フォルダを作成し、カテゴリ別テンプレートから初期構造を生成します。
argument-hint: [トピック名] [--category <category>]
---

新規記事フォルダを作成し、統一ワークフローの準備をします。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| トピック名 | ○ | - | 記事のテーマ（例: 新NISAつみたて投資枠の活用法、テスラ決算分析） |
| --category | - | 対話で選択 | カテゴリ（asset_management / side_business / macro_economy / stock_analysis / market_report / quant_analysis / investment_education） |

## 処理フロー

### Phase 1: 記事情報の収集

1. **トピック名の確認**

   引数からトピック名を取得。指定がない場合はユーザーに質問します。

   ```
   記事のトピックを教えてください（例: 新NISAつみたて投資枠の活用法）:
   ```

2. **カテゴリの選択**

   --category が指定されていない場合、以下から選択してもらいます：

   ```
   カテゴリを選択してください:
   1. asset_management   (投資初心者・NISA・資産形成)
   2. side_business      (副業・体験談・事例分析)
   3. macro_economy      (マクロ経済・経済指標)
   4. stock_analysis     (個別銘柄分析)
   5. market_report      (週次レポート)
   6. quant_analysis     (クオンツ分析)
   7. investment_education (投資教育・基礎知識)
   ```

3. **英語スラッグの生成**

   トピック名から英語のスラッグ（kebab-case）を生成します：

   - 小文字、ハイフン区切り
   - 特殊文字を除去
   - 例: `新NISAつみたて投資枠の活用法` → `new-nisa-tsumitate-guide`
   - 例: `テスラ決算分析` → `tsla-earnings-analysis`
   - 例: `2026年3月第2週 米国市場週間レビュー` → `us-market-weekly-2026w11`

   生成したスラッグをユーザーに確認：

   ```
   英語スラッグ: {topic_slug}
   この名前でよろしいですか？ (y/n または修正案を入力)
   ```

4. **カテゴリ別追加入力**

   **stock_analysis / quant_analysis の場合**:
   ```
   対象シンボルを入力してください（カンマ区切り）
   例: AAPL,^GSPC,USDJPY=X
   ```

   **macro_economy の場合**:
   ```
   対象FRED指標を入力してください（カンマ区切り）
   例: GDP,CPIAUCSL,FEDFUNDS
   ```

   **side_business の場合**:
   ```
   テーマを選択してください:
   1. konkatsu   (婚活)
   2. sidehustle (副業)
   3. shisan     (資産形成)
   ```

   続けて記事タイプを選択（sidehustle / shisan の場合）:
   ```
   記事タイプを選択してください:
   1. case_study    (事例分析型 - テンプレートA/B/C) ← デフォルト
   2. experience    (体験談 - 合成パターン法)
   ```

   `case_study` 選択時、テンプレートを選択:
   ```
   テンプレートを選択してください:
   1. B: ジャンル横断共通点分析
   2. C: AI一人スタートアップ事例分析
   3. A: ジャンル別事例分析
   ```

   ※ konkatsu は常に `experience`（合成パターン法）を使用

   **stock_analysis / macro_economy / quant_analysis の場合**:
   ```
   分析期間を入力してください
   開始日 (YYYY-MM-DD):
   終了日 (YYYY-MM-DD):
   ```

### Phase 2: フォルダ作成と初期化

5. **フォルダパスの決定**

   形式: `articles/{category}/{YYYY-MM-DD}_{topic-slug}/`

   例:
   - `articles/asset_management/2026-03-15_new-nisa-tsumitate-guide/`
   - `articles/stock_analysis/2026-03-15_tsla-earnings-analysis/`
   - `articles/market_report/2026-03-15_us-market-weekly-2026w11/`

6. **重複チェック**

   同名フォルダが既に存在しないことを確認します。
   存在する場合はエラーを表示し、処理を中断します。

7. **ディレクトリ作成**

   ```bash
   mkdir -p articles/{category}/{YYYY-MM-DD}_{topic-slug}/01_research
   mkdir -p articles/{category}/{YYYY-MM-DD}_{topic-slug}/02_draft
   mkdir -p articles/{category}/{YYYY-MM-DD}_{topic-slug}/03_published
   ```

8. **テンプレートのコピー**

   テンプレートファイルを2段階でオーバーレイします：

   ```bash
   # 共通テンプレート
   cp -r template/_common/* articles/{category}/{YYYY-MM-DD}_{topic-slug}/

   # カテゴリ固有テンプレート（共通を上書き）
   cp -r template/{category}/* articles/{category}/{YYYY-MM-DD}_{topic-slug}/
   ```

   テンプレートが存在しない場合はスキップし、空のディレクトリ構造のみ作成します。

### Phase 3: meta.yaml の初期化

9. **meta.yaml の生成**

   `articles/{category}/{YYYY-MM-DD}_{topic-slug}/meta.yaml` を以下の内容で作成します：

   ```yaml
   article_id: "{YYYY-MM-DD}_{topic-slug}"
   topic: "{トピック名}"
   category: "{category}"
   type: "{カテゴリ別デフォルト}"
   target_audience: "{カテゴリ別デフォルト}"
   target_wordcount: {カテゴリ別デフォルト}

   # カテゴリ別フィールド（該当する場合のみ）
   symbols: [...]           # stock_analysis, quant_analysis
   fred_series: [...]       # macro_economy
   theme: "..."             # side_business
   date_range:              # stock_analysis, macro_economy, quant_analysis
     start: "YYYY-MM-DD"
     end: "YYYY-MM-DD"

   # type: case_study の場合（side_business）
   case_study:
     template_type: "B"     # A / B / C
     template_label: "ジャンル横断共通点分析"

   status: "init"
   created_at: "YYYY-MM-DD"
   updated_at: "YYYY-MM-DD"

   workflow:
     research: "pending"
     draft: "pending"
     critique: "pending"
     revision: "pending"
     publish: "pending"

   human_feedback:
     hf1_topic_approved: true
     hf3_claims_reviewed: false
     hf5_draft_reviewed: false
     hf6_final_approved: false
   ```

### カテゴリ別デフォルト設定

| カテゴリ | type | target_audience | target_wordcount |
|----------|------|-----------------|-----------------|
| asset_management | column | beginner | 4000 |
| side_business (case_study) | case_study | intermediate | 7000 |
| side_business (experience) | experience | intermediate | 7000 |
| macro_economy | column | intermediate | 4000 |
| stock_analysis | data_analysis | intermediate | 4000 |
| market_report | market_report | intermediate | 5000 |
| quant_analysis | data_analysis | advanced | 4000 |
| investment_education | column | beginner | 3500 |

### Phase 4: 完了報告

10. **成功メッセージの表示**

    ```markdown
    ## 新規記事フォルダを作成しました

    ### 記事情報

    - **トピック**: {トピック名}
    - **カテゴリ**: {category} ({category_label})
    - **種別**: {type}
    - **対象読者**: {target_audience}
    - **目標文字数**: {target_wordcount}字
    - **作成日**: {YYYY-MM-DD}
    - **フォルダ**: `articles/{category}/{YYYY-MM-DD}_{topic-slug}/`

    ### 作成されたファイル

    - メタデータ: `meta.yaml`
    - リサーチ: `01_research/`
    - 原稿: `02_draft/`
    - 公開: `03_published/`

    ### 次のステップ

    1. **リサーチ開始**: `/article-research @articles/{category}/{YYYY-MM-DD}_{topic-slug}/`
    2. **全工程一括**: `/article-full @articles/{category}/{YYYY-MM-DD}_{topic-slug}/`

    ### フィードバックポイント

    このワークフローには以下のフィードバックポイントがあります：
    - [HF1] トピック承認 ✓ 完了
    - [HF3] 主張採用確認（リサーチ後）
    - [HF5] 初稿レビュー（執筆後）
    - [HF6] 最終確認（公開前）
    ```

## 後方互換性

旧形式（`articles/{category}_{seq}_{theme}/`）のフォルダも検出可能です。
パス解決時は新形式（`articles/{category}/{YYYY-MM-DD}_{topic-slug}/`）を優先し、
見つからない場合は旧形式にフォールバックします。

## エラーハンドリング

### articles/ ディレクトリが存在しない場合

```bash
mkdir -p articles/{category}/
```

自動的に作成してから処理を続行します。

### 重複するフォルダが存在する場合

```
エラー: 記事フォルダが既に存在します

既存フォルダ: articles/{category}/{YYYY-MM-DD}_{topic-slug}/

対処法:
- 別の英語スラッグを使用してください
- または既存フォルダを削除してから再実行してください
```

### テンプレートフォルダが存在しない場合

```
警告: テンプレートフォルダが見つかりません
パス: template/{category}/

空のディレクトリ構造で作成を続行します。
```

## 関連コマンド

- **後続コマンド**: `/article-research`, `/article-draft`, `/article-full`
- **旧コマンド**: `/new-finance-article`（このコマンドで置き換え）
