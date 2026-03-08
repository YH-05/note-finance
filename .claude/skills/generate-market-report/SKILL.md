---
name: generate-market-report
description: "週次マーケットレポートを自動生成するスキル。データ収集→ニュース検索→レポート作成の一連のワークフローを提供。/generate-market-report コマンドで使用。"
allowed-tools: Read, Write, Glob, Grep, Bash, Task, WebSearch
---

# Generate Market Report

週次マーケットレポートを自動生成するスキルです。

## 目的

このスキルは以下を提供します：

- **3種類のレポートモード**: 基本レポート、週次コメント（旧形式）、フル週次レポート（推奨）
- **自動データ収集**: yfinance/FRED 経由の市場データ収集
- **ニュース統合**: GitHub Project / RSS / Tavily からのニュース収集と統合
- **品質検証**: 文字数・フォーマット・データ整合性の自動検証

## いつ使用するか

### プロアクティブ使用

- 毎週水曜日の週次レポート作成時
- 市場データの定期収集と分析が必要な場合

### 明示的な使用

- `/generate-market-report` コマンド
- 「週次レポートを作成して」「マーケットレポートを生成して」などの要求

## モード比較

| モード | 説明 | GitHub Project 連携 | Issue 投稿 | 目標文字数 |
|--------|------|-------------------|-----------|-----------|
| 基本モード | 指定日のレポート生成 | なし | なし | - |
| `--weekly-comment` | 火曜〜火曜の週次コメント（旧形式） | **あり** | **自動** | 3000字以上 |
| `--weekly` | **フル週次レポート（推奨）** | **あり** | **自動** | 5700字以上 |

## 処理フロー

### 基本モード

```
Phase 1: 初期化
├── 引数解析・出力ディレクトリ作成
├── 必要ツール確認（RSS MCP, Tavily, gh）
└── テンプレート確認

Phase 2: データ収集
└── Pythonスクリプト実行（market_report_data.py）

Phase 3: ニュース検索
└── カテゴリ別ニュース検索（指数/MAG7/セクター/決算）

Phase 4: レポート生成
└── テンプレート埋め込み → Markdown出力

Phase 5: 完了処理
└── 結果サマリー表示
```

### --weekly モード（推奨）

```
Phase 1: 初期化
├── 対象期間の計算（--date から7日前 〜 --date）
├── 出力ディレクトリ作成
└── 必要ツール確認

Phase 2: 市場データ収集（★PerformanceAnalyzer4Agent使用）
├── collect_market_performance.py → data/market/
│   ├── {category}_{YYYYMMDD-HHMM}.json（複数期間: 1D, 1W, MTD, YTD...）
│   └── all_performance_{YYYYMMDD-HHMM}.json（統合）
└── データ鮮度チェック（日付ズレ警告）

Phase 3: 仮説生成（★新規）
├── market-hypothesis-generator サブエージェント
├── パターン検出 → 仮説生成 → 検索クエリ計画
└── hypotheses_{YYYYMMDD-HHMM}.json 出力

Phase 4: ニュース調査（★仮説ベース検索）
├── [条件分岐] --news-json / --news-dir 指定あり
│   ├── --news-json: 指定 JSON ファイルをそのまま使用（GitHub Project スキップ）
│   └── --news-dir: ディレクトリ内の全 JSON をマージして使用（GitHub Project スキップ）
├── [条件分岐] --news-json / --news-dir 指定なし（従来フロー）
│   ├── GitHub Project から既存ニュース取得
│   └── 仮説ベースの追加検索（--no-search でスキップ可能）
└── news_with_context.json（仮説との関連付き）

Phase 5: レポート生成（サブエージェント）
├── weekly-report-lead へ委譲（news_json_path / news_json_dir を渡す）
├── weekly-data-aggregation スキル
├── weekly-comment-generation スキル（仮説+検索結果を統合）
├── weekly-template-rendering スキル
└── weekly-report-validation スキル

Phase 6: 品質検証
└── 文字数・フォーマット・データ整合性チェック

Phase 7: Issue 投稿（自動実行）
└── weekly-report-publisher → GitHub Issue 作成（report ラベル）& Project #15 追加

Phase 8: 完了処理
├── 結果サマリー表示
└── Step 8.2: graph-queue 出力（任意）
```

## 入力パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `--date` | 今日 | **レポート終了日（YYYY-MM-DD）。この日付から1週間前が開始日となる** |
| `--output` | articles/market_report_{date} | 出力ディレクトリ |
| `--weekly` | false | フル週次レポート生成（推奨） |
| `--weekly-comment` | false | 週次コメント生成（旧形式） |
| `--project` | 15 | GitHub Project 番号（--weekly時） |
| `--no-search` | false | 追加検索を無効化（--weekly時） |
| `--news-json` | - | 単一の news_scraper JSON ファイルパス（指定時は GitHub Project フローをスキップ） |
| `--news-dir` | - | news_scraper JSON ディレクトリ（期間内全ファイルをマージして使用） |

**注意**: `--weekly` および `--weekly-comment` モードでは、レポート生成後に自動的に GitHub Issue が作成され、`report` ラベルが付与されて Project #15 に「Weekly Report」ステータスで登録されます。

### --news-json / --news-dir の動作

`--news-json` または `--news-dir` を指定すると、GitHub Project からのニュース取得をスキップし、ローカル JSON ファイルをニュースソースとして使用します。

| 条件 | ニュースソース |
|------|--------------|
| `--news-json` / `--news-dir` 省略 | 従来どおり GitHub Project フロー |
| `--news-json <path>` 指定 | 指定した単一 JSON ファイルを使用 |
| `--news-dir <dir>` 指定 | ディレクトリ内の全 JSON ファイルをマージして使用 |

weekly-report-lead 起動時に `news_json_path` / `news_json_dir` パラメータとして渡します。

### 日付と期間の計算

`--date` で指定した日付（YYYY-MM-DD形式）が**終了日**となり、**開始日は終了日の7日前**に自動計算されます。

```
例: --date 2026-01-20
  開始日: 2026-01-13
  終了日: 2026-01-20
  期間: 2026-01-13 〜 2026-01-20（7日間）
```

## 出力ディレクトリ構造

### --weekly モード

```
articles/weekly_report/{YYYY-MM-DD}/
├── data/
│   ├── indices.json          # 指数パフォーマンス
│   ├── mag7.json             # MAG7 パフォーマンス
│   ├── sectors.json          # セクター分析
│   ├── news_from_project.json # GitHub Project からのニュース
│   ├── news_supplemental.json # 追加検索結果
│   ├── aggregated_data.json  # 集約データ
│   └── comments.json         # 生成コメント
├── 02_edit/
│   └── weekly_report.md      # Markdown レポート
└── validation_result.json    # 品質検証結果
```

## 使用例

### 例1: フル週次レポート生成 & Issue投稿

**状況**: 毎週水曜日に週次レポートを作成したい

**コマンド**:
```bash
/generate-market-report
```

**処理**:
1. 対象期間を自動計算（前週火曜〜当週火曜）
2. 市場データを収集
3. GitHub Project #15 からニュースを取得
4. 不足カテゴリを追加検索で補完
5. 3200字以上のレポートを生成
6. 品質検証を実行
7. **GitHub Issue を作成（`report` ラベル付与）し Project #15 に追加**

---

### 例2: GitHub Project のみ使用

**状況**: 追加検索なしでレポートを作成したい

**コマンド**:
```bash
/generate-market-report --weekly --no-search
```

**処理**:
1. GitHub Project からのニュースのみ使用
2. 追加検索をスキップ
3. レポートを生成
4. GitHub Issue を作成し Project #15 に追加

---

### 例3: 特定日付でレポート生成

**状況**: 特定の日付を終了日として1週間分のレポートを作成したい

**コマンド**:
```bash
/generate-market-report --date 2026-01-20
```

**処理**:
1. 2026-01-20 を終了日として設定
2. 開始日を 2026-01-13（7日前）に自動計算
3. 2026-01-13 〜 2026-01-20 の期間でレポートを生成

---

### 例4: NAS ディレクトリを指定してレポート生成

**状況**: NAS に保存した news_scraper の JSON ファイルを使用したい

**コマンド**:
```bash
/generate-market-report --weekly --date 2026-03-01 \
    --news-dir /Volumes/personal_folder/finance-news/
```

**処理**:
1. ディレクトリ内の全 JSON ファイルをマージ
2. GitHub Project フローをスキップ
3. ローカル JSON をニュースソースとして使用
4. レポートを生成して GitHub Issue に投稿

---

### 例5: 単一 JSON ファイルを指定してレポート生成

**状況**: 特定の news_scraper JSON ファイルを直接指定したい

**コマンド**:
```bash
/generate-market-report --weekly --date 2026-03-01 \
    --news-json /Volumes/personal_folder/finance-news/2026-03-01/news_120000.json
```

**処理**:
1. 指定した単一 JSON ファイルを使用
2. GitHub Project フローをスキップ
3. ローカル JSON をニュースソースとして使用
4. レポートを生成して GitHub Issue に投稿

### Step 8.2: graph-queue 出力（任意）

```bash
python scripts/emit_graph_queue.py \
  --command generate-market-report \
  --input "articles/weekly_report/${date}/data/"
echo "graph-queue files generated. Run /save-to-graph to ingest."
```

## 関連リソース

### サブエージェント（--weekly モード用）

| エージェント | 説明 | 使用モード |
|-------------|------|-----------|
| `weekly-report-lead` | リーダーエージェント（ワークフロー制御） | --weekly |
| `wr-news-aggregator` | GitHub Project からニュース集約 | --weekly |
| `wr-data-aggregator` | 入力データの統合・正規化 | --weekly |
| `wr-comment-generator` | セクション別コメント生成 | --weekly |
| `wr-template-renderer` | テンプレートへのデータ埋め込み | --weekly |
| `wr-report-validator` | レポート品質検証 | --weekly |
| `wr-report-publisher` | GitHub Issue 作成 & Project 追加 | --weekly |
| `weekly-comment-indices-fetcher` | 指数ニュース収集 | --weekly-comment |
| `weekly-comment-mag7-fetcher` | MAG7 ニュース収集 | --weekly-comment |
| `weekly-comment-sectors-fetcher` | セクターニュース収集 | --weekly-comment |

### テンプレート

| テンプレート | 用途 |
|-------------|------|
| `template/market_report/weekly_market_report_template.md` | --weekly モード用 |
| `template/market_report/weekly_comment_template.md` | --weekly-comment モード用 |
| `template/market_report/02_edit/first_draft.md` | 基本モード用 |

### Python スクリプト

| スクリプト | 用途 |
|-----------|------|
| `scripts/market_report_data.py` | 基本モード用データ収集 |
| `scripts/weekly_comment_data.py` | 週次モード用データ収集 |
| `scripts/emit_graph_queue.py` | graph-queue 出力スクリプト |
| `/save-to-graph` | graph-queue 取込コマンド |

## エラーハンドリング

### E001: Python スクリプト実行エラー

**原因**: スクリプトが存在しない、依存関係不足、ネットワークエラー

**対処法**:
```bash
# 依存関係を確認
uv sync --all-extras

# スクリプトを直接実行してエラー確認
uv run python scripts/weekly_comment_data.py --output .tmp/test
```

### E010: GitHub Project アクセスエラー

**原因**: Project が存在しない、アクセス権限がない

**対処法**:
```bash
# Project の存在確認
gh project list --owner @me

# 別の Project を指定
/generate-market-report --weekly --project 20
```

### E013: 品質検証失敗

**原因**: 文字数不足、データ整合性エラー

**対処法**:
- コメントを手動で拡充
- 生成されたレポートファイル（02_edit/weekly_report.md）を手動で編集

## 品質基準

### 必須（MUST）

- [ ] 対象期間が正しく計算されている
- [ ] 必須データファイル（indices/mag7/sectors.json）が生成されている
- [ ] --weekly モードで 3200 字以上のレポートが生成される
- [ ] 品質検証結果がファイルに出力される

### 推奨（SHOULD）

- ニュースカテゴリが最低件数を満たしている
- グレード B 以上の品質スコア
- 全セクションにコメントが含まれている

## 完了条件

- [ ] 出力ディレクトリにレポートファイルが生成されている
- [ ] 品質検証が PASS または WARN で完了している
- [ ] **GitHub Issue が作成されている（`report` ラベル付き）**
- [ ] **Issue が Project #15 に追加されている（Status: Weekly Report）**
- [ ] 結果サマリーが表示されている

## 関連コマンド

- `/finance-news-workflow`: ニュース収集
- `/new-finance-article`: 記事フォルダ作成
- `/finance-research`: リサーチ実行
