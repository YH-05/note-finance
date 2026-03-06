---
description: 資産形成コンテンツ（note記事+X投稿）を自動生成します。JP RSSソース収集→記事生成→コンプライアンスチェック→結果報告。
argument-hint: [トピック名] [--theme <theme>] [--days <days>] [--no-search] [--skip-hf]
---

# /asset-management - 資産形成コンテンツ生成

投資初心者向けの資産形成コンテンツ（note記事 2000-4000字 + X投稿 280字以内）を自動生成するコマンドです。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| トピック名 | ○ | - | 記事のテーマ（例: 新NISAつみたて投資枠の活用法） |
| --theme | - | 対話で選択 | テーマキー（nisa / fund_selection / asset_allocation / ideco / market_basics / simulation） |
| --days | - | 14 | 過去何日分のRSSを対象とするか |
| --top-n | - | 10 | 各テーマの最大記事数（公開日時の新しい順） |
| --no-search | - | false | Web検索をスキップし、RSSソースのみ使用 |
| --skip-hf | - | false | ヒューマンフィードバック（確認プロンプト）をスキップ |

## テーマ選択

--theme が指定されていない場合、ユーザーに以下から選択させます：

```
テーマを選択してください:

1. nisa           - NISA制度（新NISA、つみたて投資枠、成長投資枠）
2. fund_selection - ファンド選び（インデックスファンド、信託報酬、eMAXIS）
3. asset_allocation - 資産配分（ポートフォリオ、分散投資、リバランス）
4. ideco          - iDeCo・企業型DC（確定拠出年金、節税）
5. market_basics  - 市場の基礎知識（株式市場、経済指標、為替、金利）
6. simulation     - 資産形成シミュレーション（複利、積立、老後資金）

番号またはテーマキーを入力:
```

## 処理フロー

```
Phase 1: ソース収集（2-3分）
├── 環境確認
│   ├── data/config/asset-management-themes.json
│   └── data/config/rss-presets-jp.json
├── Python CLI実行
│   └── prepare_asset_management_session.py
│       ├── JP RSSプリセット読み込み
│       ├── テーマ別キーワードマッチング
│       ├── 公開日時フィルタリング（--days）
│       └── 上位N件選択（--top-n）
├── セッションJSON出力（.tmp/asset-mgmt-*.json）
└── [HF1] ソース確認 ✓

Phase 2: 記事生成（2-4分）
├── asset-management-writer エージェント
│   ├── ソースキュレーション（関連度スコアリング）
│   ├── note記事の初稿（2000-4000字）
│   ├── X投稿（280字以内）
│   └── curated_sources.json 出力
└── [HF2] 初稿確認 ✓

Phase 3: コンプライアンスチェック（1-2分）
├── finance-critic-compliance エージェント
│   ├── 禁止表現スキャン
│   ├── 免責事項確認
│   └── 投資助言的表現チェック
├── asset-management-reviser（fail/warning 時のみ）
│   └── critical/high 問題のみ修正
└── revised_draft.md 出力（修正時のみ）

Phase 4: 結果報告（<30秒）
├── 記事統計サマリー
├── コンプライアンススコア表示
└── 出力ファイル一覧
```

## 実行手順

### Phase 1: ソース収集

1. **パラメータの解析**

   引数からトピック名と各オプションを取得します。

2. **トピック名の確認**

   トピック名が指定されていない場合はユーザーに質問します。

   ```
   記事のトピックを教えてください（例: 新NISAつみたて投資枠の活用法）:
   ```

3. **テーマの選択**

   --theme が指定されていない場合はユーザーに選択させます（上記のテーマ選択フローを使用）。

4. **環境確認**

   ```bash
   # テーマ設定ファイル確認
   test -f data/config/asset-management-themes.json

   # JP RSSプリセット確認
   test -f data/config/rss-presets-jp.json
   ```

5. **Python CLI実行**

   ```bash
   uv run python scripts/prepare_asset_management_session.py \
       --days ${days} \
       --themes ${theme} \
       --top-n ${top_n}
   ```

   出力: `.tmp/asset-mgmt-{YYYYMMDD}-{HHMMSS}.json`

6. **[HF1] ソース確認**

   --skip-hf が指定されていない場合、収集結果を確認：

   ```
   ソース収集が完了しました。

   テーマ: {theme_name_ja}
   収集記事: {total}件 → マッチ: {matched}件

   ソース一覧:
   1. {title} - {source} ({published})
   2. {title} - {source} ({published})
   ...

   このソースで続行しますか？ (y/n)
   ```

### Phase 2: 記事生成

7. **asset-management-workflow スキルへの連携**

   asset-management-workflow スキル（`.claude/skills/asset-management-workflow/SKILL.md`）に処理を委譲します。

   ```python
   Task(
       subagent_type="asset-management-writer",
       description="記事初稿とX投稿の生成",
       prompt=f"""以下のセッションデータに基づいて記事を生成してください。

   ## トピック
   {topic_name}

   ## テーマ
   {theme}

   ## セッションデータ
   ```json
   {session_data}
   ```

   ## 出力先
   - 02_edit/first_draft.md（note記事、2000-4000字）
   - 02_edit/x_post.md（X投稿、280字以内）
   - 02_edit/curated_sources.json（キュレーション済みソース）
   """
   )
   ```

8. **[HF2] 初稿確認**

   --skip-hf が指定されていない場合、初稿を確認：

   ```
   初稿が完成しました。

   - 文字数: {char_count}字
   - X投稿: {x_char_count}字
   - 使用ソース: {used_count}件

   初稿を確認しますか？ (y/n)

   確認する場合:
   - first_draft.md を表示
   - 修正が必要な場合は編集を促す
   - 準備ができたら「続行」と入力
   ```

### Phase 3: コンプライアンスチェック

9. **finance-critic-compliance 呼び出し**

   ```python
   Task(
       subagent_type="finance-critic-compliance",
       description="コンプライアンスチェック",
       prompt=f"""02_edit/first_draft.md のコンプライアンスチェックを実行してください。

   critic.json の compliance セクションを生成してください。"""
   )
   ```

10. **asset-management-reviser 呼び出し（fail/warning 時のみ）**

    ```python
    if compliance_status in ["fail", "warning"]:
        Task(
            subagent_type="asset-management-reviser",
            description="コンプライアンス修正",
            prompt=f"""02_edit/first_draft.md と 02_edit/critic.json を読み込み、
    compliance の critical/high 問題のみ修正してください。

    revised_draft.md を出力してください。"""
        )
    ```

### Phase 4: 結果報告

11. **サマリー出力**

## 完了報告

```markdown
## 資産形成記事生成完了

### 記事情報

| 項目 | 内容 |
|------|------|
| トピック | {topic_name} |
| テーマ | {theme_name_ja} |
| 文字数 | {char_count}字 |
| X投稿 | {x_char_count}字 |
| ソース数 | {source_count}件（使用: {used_count}件） |

### コンプライアンス

| 項目 | 結果 |
|------|------|
| ステータス | {compliance_status} |
| スコア | {compliance_score}/100 |
| 修正箇所 | {revision_count}件 |

### 出力ファイル

| ファイル | パス |
|---------|------|
| 最終記事 | {article_dir}/02_edit/revised_draft.md（または first_draft.md） |
| X投稿 | {article_dir}/02_edit/x_post.md |
| ソース一覧 | {article_dir}/02_edit/curated_sources.json |
| 批評結果 | {article_dir}/02_edit/critic.json |

### セッション情報

- **実行時刻**: {timestamp}
- **セッションファイル**: {session_file}
- **処理時間**: {elapsed}分
```

## 使用例

### 基本的な使用（推奨）

```bash
# テーマを対話で選択
/asset-management "新NISAつみたて投資枠の活用法"

# テーマを指定
/asset-management "インデックスファンドの選び方" --theme fund_selection

# 直近7日分のソースのみ
/asset-management "資産配分の基本" --theme asset_allocation --days 7
```

### オプション付き

```bash
# Web検索スキップ（RSSソースのみ使用）
/asset-management "iDeCoの節税効果" --theme ideco --no-search

# 全自動実行（非推奨）
/asset-management "市場の基礎知識" --theme market_basics --skip-hf

# ソース数を限定
/asset-management "複利効果の実例" --theme simulation --top-n 5
```

## テーマ別推奨設定

| テーマ | 推奨 --days | 理由 |
|--------|------------|------|
| nisa | 14 | 制度解説は更新頻度が低い |
| fund_selection | 14 | ファンド情報は定期更新 |
| asset_allocation | 14 | 基礎知識は広い期間でカバー |
| ideco | 14 | 制度情報は更新頻度が低い |
| market_basics | 7 | 市場情報は最新性が重要 |
| simulation | 30 | シミュレーション記事は汎用性が高い |

## エラーハンドリング

### テーマ設定ファイルが見つからない

```
エラー: テーマ設定ファイルが見つかりません

期待されるパス: data/config/asset-management-themes.json

対処法:
1. ファイルの存在を確認:
   ls data/config/asset-management-themes.json

2. ファイルを復元:
   git checkout data/config/asset-management-themes.json
```

### JP RSSプリセットが見つからない

```
エラー: JP RSSプリセットファイルが見つかりません

期待されるパス: data/config/rss-presets-jp.json

対処法:
1. ファイルの存在を確認:
   ls data/config/rss-presets-jp.json

2. ファイルを復元:
   git checkout data/config/rss-presets-jp.json
```

### ソースが不足している

```
警告: テーマ "{theme}" のソースが不足しています（{count}件）

対処法:
1. 期間を拡大して再実行:
   /asset-management "{topic}" --theme {theme} --days 30

2. Web検索を有効化:
   /asset-management "{topic}" --theme {theme}
   （--no-search を指定しない）
```

### コンプライアンスチェック失敗

```
警告: コンプライアンスチェックで問題が検出されました

ステータス: {status}
スコア: {score}/100

問題点:
1. {issue_1}
2. {issue_2}

自動修正を試みます...
（asset-management-reviser による修正）

修正後も問題が残る場合は手動修正をお願いします:
edit {article_dir}/02_edit/revised_draft.md
```

## 関連リソース

### コマンド

- `/new-finance-article` - 記事フォルダ作成（Phase 1 で内部使用）
- `/finance-edit` - 記事編集ワークフロー
- `/finance-full` - 金融記事の全工程一括実行

### スキル・エージェント

- **ワークフロースキル**: `.claude/skills/asset-management-workflow/SKILL.md`
- **詳細ガイド**: `.claude/skills/asset-management-workflow/guide.md`
- **記事ライター**: `.claude/agents/asset-management-writer.md`
- **コンプライアンス批評**: `.claude/agents/finance-critic-compliance.md`
- **軽量リバイザー**: `.claude/agents/asset-management-reviser.md`

### 設定ファイル

- **テーマ設定**: `data/config/asset-management-themes.json`
- **JP RSSプリセット**: `data/config/rss-presets-jp.json`
- **Python CLI前処理**: `scripts/prepare_asset_management_session.py`

### スニペット

- **免責事項**: `snippets/not-advice.md`（冒頭に挿入）
- **リスク開示**: `snippets/investment-risk.md`（末尾に挿入）
- **NISA免責**: `snippets/nisa-disclaimer.md`（NISAテーマ時に追加）

## 注意事項

1. **対象読者**: 投資初心者向けのコンテンツです。専門用語は初出時に平易化してください。
2. **コンプライアンス**: 特定銘柄の売買推奨、リターン保証等の表現は禁止です。
3. **処理時間**: 全体で5-10分が目安です。
4. **データソース**: JP RSSプリセットに登録済みのフィードのみ対象です。
5. **実行頻度**: テーマあたり週1-2回を推奨します。
