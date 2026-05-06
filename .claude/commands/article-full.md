---
description: 記事作成の全工程（初期化→リサーチ→ドラフト→批評→投稿）を完全自動で一気通貫実行します。
argument-hint: [トピック名] [--category <category>] [--skip-publish]
---

記事作成の全工程を **完全自動・無人実行** する統合コマンドです。
途中のヒューマンフィードバック（HF）は一切要求せず、最後まで一気通貫で走り切ります。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| トピック名 | ○※ | - | 記事のテーマ（例: 新NISAつみたて投資枠の活用法） |
| @article_dir | ○※ | - | 既存記事ディレクトリ（途中から再開する場合） |
| --category | - | 必須指定推奨 | カテゴリ（asset_management / life_planning / side_business / macro_economy / stock_analysis / market_report / quant_analysis / investment_education / earnings） |
| --skip-publish | - | false | 投稿をスキップ（批評・修正で完了） |
| --mode | - | full | 批評モード（quick / full） |

※ トピック名または @article_dir のいずれかを指定
※ カテゴリ未指定かつトピック名のみ指定の場合は、カテゴリを自動推定する（停止せず継続）

## 完全自動化の方針

このコマンドは **無人実行（unattended execution）** を前提に設計されています。

- **承認待ちなし**: HF1/HF3/HF5/HF6 のような対話的な承認ステップは存在しません
- **対話入力なし**: トピック名・カテゴリ・スラッグ等の不足情報は全て自動推定で補完
- **エラー時も継続**: クリティカルでないエラーは記録のみで処理続行（クリティカル時のみ中断）
- **完了まで一気通貫**: Phase 1 → 2 → 3 → 4 → 5 を切れ目なく直列実行

進捗は各 Phase 完了時にログ出力するのみで、ユーザー入力は一切要求しません。

## 処理フロー

```
Phase 1: 記事フォルダ作成（自動）
└── /article-init
    ├── トピック名（引数 or 自動生成）
    ├── カテゴリ（引数 or 自動推定）
    ├── スラッグ自動生成
    ├── カテゴリ別追加入力は全てデフォルト値で自動補完
    └── meta.yaml 生成

Phase 2: リサーチ実行（自動）
└── /article-research
    ├── カテゴリ別リサーチ
    │   ├── stock/macro/quant → investment-research
    │   ├── asset_management → investment-research
    │   ├── life_planning → investment-research（一次出典RSS）
    │   ├── side_business → experience-db-workflow
    │   └── market_report → generate-market-report
    └── 01_research/ に成果物保存

Phase 3: ドラフト作成（自動）
└── /article-draft
    ├── カテゴリ別ライター実行
    └── 02_draft/first_draft.md 出力

Phase 4: 批評・修正（自動）
└── /article-critique --mode {mode}
    ├── カテゴリ別批評（並列）
    ├── 02_draft/critic.json, critic.md
    ├── リバイザー実行
    ├── 02_draft/revised_draft.md
    ├── Step 4.4: 表・チャート画像ポストプロセス（全カテゴリ必須）
    └── Step 4.5: 決算サムネイル生成（earnings のみ）

Phase 5: 投稿（自動 / --skip-publish でスキップ可能）
└── /article-publish
    ├── Step 1.5: 残存マークダウン表 gate（閾値超過で中止）
    ├── ドライラン確認
    ├── note.com 下書き投稿
    └── 03_published/article.md
```

## 実行手順

### Phase 1: 記事フォルダ作成

1. **パラメータの解析**

   引数からトピック名と各オプションを取得します。

   既存の記事ディレクトリが `@article_dir` で指定されている場合:
   - `meta.yaml` を読み込み
   - 未完了のフェーズから再開

2. **記事フォルダ作成（無人モード）**

   `/article-init` の機能を **対話なし** で実行：

   - トピック名: 引数で指定がなければ `@article_dir` の slug から逆引き、それも無ければエラー終了
   - カテゴリ: `--category` 未指定時はトピック名から自動推定（推定ロジックは finance-article-writer の judge_category を使用）
   - スラッグ: トピック名から英語スラッグを自動生成
   - カテゴリ別追加入力（シンボル・指標・テーマ・期間）は **空欄またはデフォルト値** で meta.yaml を生成
   - 入力不足によるユーザー質問は一切行わない

3. **進捗ログ出力（HF承認は不要）**

   ```
   [Phase 1 完了] 記事フォルダを作成しました
   - トピック: {topic}
   - カテゴリ: {category}
   - フォルダ: articles/{category}/{YYYY-MM-DD}_{slug}/
   → Phase 2 (リサーチ) へ自動継続...
   ```

### Phase 2: リサーチ実行

4. **リサーチワークフロー開始**

   `/article-research @{article_dir}` を **対話なし** で実行。

   カテゴリに応じたリサーチスキルへ自動委譲。途中の承認・確認は要求しない。

5. **進捗ログ出力（HF承認は不要）**

   ```
   [Phase 2 完了] リサーチが完了しました
   - ソース数: {source_count}件
   - 主張/ポイント: {claims_count}件
   → Phase 3 (ドラフト作成) へ自動継続...
   ```

### Phase 3: ドラフト作成

6. **初稿作成**

   `/article-draft @{article_dir}` を **対話なし** で実行。

7. **進捗ログ出力（HF承認は不要）**

   ```
   [Phase 3 完了] 初稿が完成しました
   - 文字数: {word_count}字（目標: {target_wordcount}字）
   - セクション数: {section_count}
   → Phase 4 (批評・修正) へ自動継続...
   ```

### Phase 4: 批評・修正

8. **批評と修正の実行**

   `/article-critique @{article_dir} --mode {mode}` を **対話なし** で実行。

   カテゴリに応じた批評エージェントを並列実行 → リバイザーが revised_draft.md を生成 → 表・チャート画像ポストプロセスまで一気に完了させる。

9. **進捗ログ出力（HF承認は不要）**

   ```
   [Phase 4 完了] 批評・修正が完了しました
   - 総合: {overall}/100
   - コンプライアンス: {compliance}/100
   - 事実正確性: {fact}/100
   → Phase 5 (投稿) へ自動継続...
   ```

   **コンプライアンス fail の場合のみ** 投稿フェーズに進まずエラー終了する（後述「エラーハンドリング」参照）。

### Phase 5: 投稿

10. **note.com 投稿（自動）**

    `--skip-publish` が指定されていない場合のみ:

    `/article-publish @{article_dir}` を **対話なし** で実行。

    - ドライラン確認は内部で自動実施
    - 残存マークダウン表 gate も自動判定
    - note.com に下書き投稿
    - 03_published/article.md に最終版コピー

## 完了報告

```markdown
## 記事作成完了（完全自動実行）

### 記事情報
- **トピック**: {topic}
- **カテゴリ**: {category} ({category_label})
- **フォルダ**: `articles/{category}/{YYYY-MM-DD}_{slug}/`

### 生成ファイル

**01_research/** (リサーチ成果物)
- {カテゴリ別のファイル一覧}

**02_draft/** (執筆成果物)
- first_draft.md
- critic.json
- critic.md
- revised_draft.md

**03_published/** (公開成果物)
- article.md

### 最終スコア
| 項目 | スコア |
|------|--------|
| 総合 | {overall}/100 |
| コンプライアンス | {compliance}/100 |
| 事実正確性 | {fact}/100 |
| 構成 | {structure}/100 (full時) |
| データ正確性 | {data}/100 (full時) |
| 読みやすさ | {readability}/100 (full時) |

### ワークフロー状態

**meta.yaml の workflow:**
- research: done ✓
- draft: done ✓
- critique: done ✓
- revision: done ✓
- publish: {done|pending}

**human_feedback:** 完全自動実行のため全て auto-approved

### 次のステップ

{--skip-publish の場合:}
1. revised_draft.md を最終確認（必要なら手動で）
2. note.com に下書き投稿:
   /article-publish @articles/{category}/{YYYY-MM-DD}_{slug}/

{投稿済みの場合:}
1. note.com で下書きを確認: {note_url}
2. カバー画像・タグを設定
3. 公開ボタンで公開
```

## 使用例

### 基本的な使用（完全自動）

```bash
# トピックとカテゴリを指定して全自動実行（推奨）
/article-full "テスラ決算分析" --category stock_analysis

# トピックのみ指定（カテゴリは自動推定）
/article-full "新NISAつみたて投資枠の活用法"

# 投稿なし（批評・修正まで自動実行）
/article-full "米雇用統計解説" --category macro_economy --skip-publish
```

### 既存記事から再開（自動）

```bash
# 未完了フェーズから完全自動で続行
/article-full @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/
```

### オプション付き

```bash
# クイック批評モード（速報向け）
/article-full "市場アップデート" --category market_report --mode quick
```

## カテゴリ別推奨設定

| カテゴリ | 推奨 mode | 理由 |
|---------|-----------|------|
| asset_management | full | 初心者向け、読みやすさ重視 |
| life_planning | full | CFP相当品質、業際規制チェック必須 |
| side_business | full | 体験談、共感度・リアリティ重視 |
| macro_economy | full | マクロ経済分析、正確性重視 |
| stock_analysis | full | 企業分析、データ正確性重視 |
| market_report | quick | 定期レポート、速報性重視 |
| quant_analysis | full | 数値分析、データ正確性重視 |
| investment_education | full | 教育コンテンツ、読みやすさ重視 |
| earnings | full | 決算プレビュー、データ正確性重視 |

## 記事品質ルール（全フェーズ共通）

参照: `.claude/rules/article-quality-standards.md`

| ルール | 内容 | 適用フェーズ |
|--------|------|-------------|
| 表の画像化 | マークダウン表（3列以上 or 5行以上）を `/generate-table-image` でPNG変換 | draft, critique(Step 4.4), publish(Step 1.5) |
| ソースURL埋め込み | 数値データ・引用に `[テキスト](URL)` リンク | research, draft, critique |
| チャートの画像化 | データ可視化は `/generate-chart-image` でPNG変換 | draft, critique(Step 4.4) |
| サムネイル生成 | earnings カテゴリはサムネイル自動生成 | critique(Step 4.5) |

## エラーハンドリング

完全自動実行のため、エラー時もユーザーへの問い合わせは行わず、以下のルールで自動判定する。

### 継続可能なエラー（warning）

- カテゴリ別追加メタ情報の欠落 → デフォルト値で補完して継続
- 軽微なリサーチ失敗（一部ソース取得失敗） → 取得済みデータで継続
- 批評スコアが低い（70点以下など） → 警告ログ出力のみで継続

### 中断するクリティカルエラー

以下のケースのみ処理を中断し、再開コマンドを案内する:

1. **トピック名・記事ディレクトリが特定不可**
   - メッセージ: `エラー: トピック名または既存記事ディレクトリが特定できませんでした`

2. **コンプライアンス fail**
   - 法令・業際規制違反など、修正必須の問題が検出された場合
   - メッセージ:
     ```
     ⚠️ コンプライアンスチェック失敗（自動実行中断）

     問題:
     1. {critical_issue_1}
     2. {critical_issue_2}

     対処法:
     1. revised_draft.md を手動修正
     2. 再度批評を実行: /article-critique @{article_dir}
     3. 修正後の投稿: /article-publish @{article_dir}
     ```

3. **note.com 投稿失敗**
   - 認証エラー・ネットワークエラー等
   - メッセージ: `エラー: note.com 投稿に失敗しました。/article-publish @{article_dir} で再試行してください`

中断時は `meta.yaml` の `workflow` ステータスを更新し、後から個別コマンドで再開できる状態を保証する。

## 注意事項

1. **完全自動実行**: ユーザー入力・承認待ちは一切発生しません。実行開始後は完了まで放置可能です
2. **品質保証**: HFをスキップする代わりに、批評（critique）プロセスで自動的に品質チェックを行います。コンプライアンス違反等のクリティカル問題が検出された場合は自動中断します
3. **再実行**: meta.yaml の workflow 状態を参照し、未完了のフェーズから自動再開します
4. **対話モードが必要な場合**: 個別コマンド（`/article-init`, `/article-research` 等）を直接実行してください

## 関連コマンド

- **構成コマンド**:
  - `/article-init` - Phase 1 のみ実行（対話モード）
  - `/article-research` - Phase 2 のみ実行
  - `/article-draft` - Phase 3 のみ実行
  - `/article-critique` - Phase 4 のみ実行
  - `/article-publish` - Phase 5 のみ実行

- **補助コマンド**:
  - `/article-status` - 全記事のステータス確認
  - `/finance-suggest-topics` - トピック提案

- **旧コマンド（置き換え対象）**:
  - `/finance-full` → `/article-full`
  - `/asset-management` → `/article-full --category asset_management`
  - `/experience-db-full` → `/article-full --category side_business`
