---
description: 記事作成の全工程（初期化→リサーチ→ドラフト→批評→投稿）を一括実行します。
argument-hint: [トピック名] [--category <category>] [--skip-publish]
---

記事作成の全工程を一括実行する統合コマンドです。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| トピック名 | ○※ | - | 記事のテーマ（例: 新NISAつみたて投資枠の活用法） |
| @article_dir | ○※ | - | 既存記事ディレクトリ（途中から再開する場合） |
| --category | - | 対話で選択 | カテゴリ（asset_management / side_business / macro_economy / stock_analysis / market_report / quant_analysis） |
| --skip-publish | - | false | 投稿をスキップ（批評・修正で完了） |
| --mode | - | full | 批評モード（quick / full） |
| --skip-hf | - | false | ヒューマンフィードバックをスキップ（非推奨） |

※ トピック名または @article_dir のいずれかを指定

## 処理フロー

```
Phase 1: 記事フォルダ作成
├── /article-init
│   ├── トピック名入力
│   ├── カテゴリ選択
│   ├── スラッグ生成
│   ├── カテゴリ別追加入力
│   └── meta.yaml 生成
└── [HF1] トピック承認 ✓

Phase 2: リサーチ実行
├── /article-research
│   ├── カテゴリ別リサーチ
│   │   ├── stock/macro/quant → investment-research
│   │   ├── asset_management → asset-management-workflow
│   │   ├── side_business → experience-db-workflow
│   │   └── market_report → generate-market-report
│   └── 01_research/ に成果物保存
└── [HF3] 主張採用確認

Phase 3: ドラフト作成
├── /article-draft
│   ├── カテゴリ別ライター実行
│   └── 02_draft/first_draft.md 出力
└── [HF5] 初稿レビュー

Phase 4: 批評・修正
├── /article-critique --mode {mode}
│   ├── カテゴリ別批評（並列）
│   ├── 02_draft/critic.json, critic.md
│   ├── リバイザー実行
│   └── 02_draft/revised_draft.md
└── [HF6] 最終確認

Phase 5: 投稿（--skip-publish でスキップ可能）
├── /article-publish
│   ├── ドライラン確認
│   ├── note.com 下書き投稿
│   └── 03_published/article.md
└── 完了報告
```

## 実行手順

### Phase 1: 記事フォルダ作成

1. **パラメータの解析**

   引数からトピック名と各オプションを取得します。

   既存の記事ディレクトリが `@article_dir` で指定されている場合:
   - `meta.yaml` を読み込み
   - 未完了のフェーズから再開

2. **記事フォルダ作成**

   `/article-init` コマンドの全機能を実行：

   - トピック名が指定されていない場合は質問
   - --category が指定されていない場合はユーザーに選択させる
   - 英語スラッグの生成と確認
   - カテゴリ別追加入力（シンボル、指標、テーマ、期間）
   - フォルダ構造と meta.yaml の作成

3. **[HF1] トピック承認**

   ```
   記事フォルダを作成しました。

   - トピック: {topic}
   - カテゴリ: {category}
   - フォルダ: articles/{category}/{YYYY-MM-DD}_{slug}/

   このトピックで続行しますか？ (y/n)
   ```

   --skip-hf が指定されている場合はスキップ。

### Phase 2: リサーチ実行

4. **リサーチワークフロー開始**

   `/article-research @{article_dir}` を実行。

   カテゴリに応じた適切なリサーチスキルに処理を委譲します。

5. **リサーチ結果の確認**

   ```
   リサーチが完了しました。

   収集結果:
   - ソース数: {source_count}件
   - 主張/ポイント: {claims_count}件
   ```

6. **[HF3] 主張採用確認**

   --skip-hf が指定されていない場合:

   ```
   リサーチ結果を確認しますか？ (y/n)

   確認する場合:
   - 01_research/ の成果物を表示
   - 修正が必要な場合は編集を促す
   - 準備ができたら「続行」と入力
   ```

### Phase 3: ドラフト作成

7. **初稿作成**

   `/article-draft @{article_dir}` を実行。

   カテゴリに応じた適切なライターエージェントに処理を委譲します。

8. **[HF5] 初稿レビュー**

   --skip-hf が指定されていない場合:

   ```
   初稿が完成しました。

   - 文字数: {word_count}字（目標: {target_wordcount}字）
   - セクション数: {section_count}

   初稿を確認しますか？ (y/n)
   ```

### Phase 4: 批評・修正

9. **批評と修正の実行**

   `/article-critique @{article_dir} --mode {mode}` を実行。

   カテゴリに応じた批評エージェントを並列実行し、修正版を生成します。

10. **[HF6] 最終確認**

    --skip-hf が指定されていない場合:

    ```
    記事の批評・修正が完了しました。

    最終スコア:
    | 項目 | スコア |
    |------|--------|
    | 総合 | {overall}/100 |
    | コンプライアンス | {compliance}/100 |
    | 事実正確性 | {fact}/100 |

    修正版を確認しますか？ (y/n)

    確認後:
    - 承認: 「承認」と入力 → 投稿フェーズへ
    - 追加修正: 「修正」と入力 → 批評プロセスに戻る
    ```

### Phase 5: 投稿

11. **note.com 投稿**

    --skip-publish が指定されていない場合:

    `/article-publish @{article_dir}` を実行。

    - ドライラン確認
    - note.com に下書き投稿
    - 03_published/article.md に最終版コピー

## 完了報告

```markdown
## 記事作成完了

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

**human_feedback:**
- [HF1] トピック承認: ✓
- [HF3] 主張採用確認: {status}
- [HF5] 初稿レビュー: {status}
- [HF6] 最終確認: {status}

### 次のステップ

{--skip-publish の場合:}
1. revised_draft.md を最終確認
2. note.com に下書き投稿:
   /article-publish @articles/{category}/{YYYY-MM-DD}_{slug}/

{投稿済みの場合:}
1. note.com で下書きを確認: {note_url}
2. カバー画像・タグを設定
3. 公開ボタンで公開
```

## 使用例

### 基本的な使用（推奨）

```bash
# カテゴリを対話で選択
/article-full "新NISAつみたて投資枠の活用法"

# カテゴリを指定
/article-full "テスラ決算分析" --category stock_analysis

# 投稿なし（批評・修正まで）
/article-full "米雇用統計解説" --category macro_economy --skip-publish
```

### 既存記事から再開

```bash
# リサーチ済みの記事からドラフト以降を実行
/article-full @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/
```

### オプション付き

```bash
# クイック批評モード
/article-full "市場アップデート" --category market_report --mode quick

# 全自動実行（非推奨）
/article-full "市場サマリー" --category market_report --skip-hf
```

## カテゴリ別推奨設定

| カテゴリ | 推奨 mode | 理由 |
|---------|-----------|------|
| asset_management | full | 初心者向け、読みやすさ重視 |
| side_business | full | 体験談、共感度・リアリティ重視 |
| macro_economy | full | マクロ経済分析、正確性重視 |
| stock_analysis | full | 企業分析、データ正確性重視 |
| market_report | quick | 定期レポート、速報性重視 |
| quant_analysis | full | 数値分析、データ正確性重視 |

## エラーハンドリング

### 各フェーズのエラー時

エラーが発生したフェーズで処理を中断し、個別コマンドで該当フェーズから再開可能です。

```
エラー: {phase_name}中に問題が発生しました

失敗した処理: {failed_step}
エラー内容: {error_message}

対処法:
1. エラー内容を確認
2. 個別コマンドで該当フェーズから再開:
   {適切なコマンド} @{article_dir}
```

### コンプライアンス fail

```
⚠️ コンプライアンスチェック失敗

この記事には修正が必須の問題が含まれています。

問題:
1. {critical_issue_1}
2. {critical_issue_2}

対処法:
1. revised_draft.md を手動修正
2. 再度批評を実行:
   /article-critique @{article_dir}
```

## 注意事項

1. **初回実行時**: トピック名、カテゴリ、追加パラメータの入力が必要。対話的に進むため時間がかかる場合があります
2. **--skip-hf**: 品質保証のため、通常は使用しないことを推奨します
3. **再実行**: meta.yaml の workflow 状態を参照し、未完了のフェーズから自動再開します

## 関連コマンド

- **構成コマンド**:
  - `/article-init` - Phase 1 のみ実行
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
