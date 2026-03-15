---
description: 資産形成コンテンツ（note記事+X投稿）を自動生成します。JP RSSソース収集→記事生成→コンプライアンスチェック→結果報告。
---

# 資産形成コンテンツ生成ワークフロー

投資初心者向けの資産形成コンテンツ（note記事 2000-4000字 + X投稿 280字以内）を自動生成するワークフローです。

## パラメータ（ユーザーに確認）

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| トピック名 | ○ | - | 記事のテーマ（例: 新NISAつみたて投資枠の活用法） |
| --theme | - | 対話で選択 | テーマキー（nisa / fund_selection / asset_allocation / ideco / market_basics / simulation） |
| --days | - | 14 | 過去何日分のRSSを対象とするか |
| --top-n | - | 10 | 各テーマの最大記事数 |
| --no-search | - | false | Web検索をスキップし、RSSソースのみ使用 |
| --skip-hf | - | false | ヒューマンフィードバックをスキップ |

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
├── asset-management-workflow スキル
│   ├── ソースキュレーション（関連度スコアリング）
│   ├── note記事の初稿（2000-4000字）
│   ├── X投稿（280字以内）
│   └── curated_sources.json 出力
└── [HF2] 初稿確認 ✓

Phase 3: コンプライアンスチェック（1-2分）
├── コンプライアンス批評
│   ├── 禁止表現スキャン
│   ├── 免責事項確認
│   └── 投資助言的表現チェック
├── 修正（fail/warning 時のみ）
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

3. **テーマの選択**

   --theme が指定されていない場合はユーザーに選択させます。

4. **環境確認**

   ```bash
   test -f data/config/asset-management-themes.json
   test -f data/config/rss-presets-jp.json
   ```

5. **Python CLI実行**

   // turbo

   ```bash
   uv run python scripts/prepare_asset_management_session.py \
       --days ${days} \
       --themes ${theme} \
       --top-n ${top_n}
   ```

   出力: `.tmp/asset-mgmt-{YYYYMMDD}-{HHMMSS}.json`

6. **[HF1] ソース確認**

   --skip-hf が指定されていない場合、収集結果をユーザーに確認。

### Phase 2: 記事生成

7. **asset-management-workflow スキルへの連携**

   `.agents/skills/asset-management-workflow/SKILL.md` の指示に従い処理を実行。

   出力:
   - `02_draft/first_draft.md`（note記事、2000-4000字）
   - `02_draft/x_post.md`（X投稿、280字以内）
   - `02_draft/curated_sources.json`（キュレーション済みソース）

8. **[HF2] 初稿確認**

   --skip-hf が指定されていない場合、初稿をユーザーに確認。

### Phase 3: コンプライアンスチェック

9. **コンプライアンス批評**

   first_draft.md のコンプライアンスチェックを実行。critic.json の compliance セクションを生成。

10. **修正（fail/warning 時のみ）**

    compliance の critical/high 問題のみ修正し、revised_draft.md を出力。

### Phase 4: 結果報告

11. **サマリー出力**

## エラーハンドリング

- **テーマ設定ファイルが見つからない**: `data/config/asset-management-themes.json` の存在を確認
- **JP RSSプリセットが見つからない**: `data/config/rss-presets-jp.json` の存在を確認
- **ソースが不足**: 期間を拡大（`--days 30`）して再実行
- **コンプライアンスチェック失敗**: 自動修正後も問題が残る場合は手動修正

## 関連リソース

| リソース | パス |
|---------|------|
| asset-management-workflow スキル | `.agents/skills/asset-management-workflow/SKILL.md` |
| テーマ設定 | `data/config/asset-management-themes.json` |
| JP RSSプリセット | `data/config/rss-presets-jp.json` |
| Python CLI前処理 | `scripts/prepare_asset_management_session.py` |
| 免責事項 | `snippets/not-advice.md` |
| リスク開示 | `snippets/investment-risk.md` |
| NISA免責 | `snippets/nisa-disclaimer.md` |
