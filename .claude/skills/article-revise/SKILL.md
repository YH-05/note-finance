---
name: article-revise
description: revised_draft.md にユーザーのフィードバックを反映して記事を更新するスキル。記事の修正依頼、トーン変更、構成変更、内容追加・削除など、既存記事への変更指示があれば必ずこのスキルを使うこと。「ここを直して」「もっとカジュアルに」「結論を強くして」「データを追加して」「この部分を削って」「記事を修正」「revised_draft を更新」「フィードバックを反映」と言われたら必ずこのスキルを使うこと。/article-critique の自動批評とは異なり、人間の具体的な指示に基づいて記事を改善する。
---

# article-revise スキル

既存の revised_draft.md（または first_draft.md）にユーザーのフィードバックを反映し、更新版を生成する。

## いつ使うか

- ユーザーが記事の内容・構成・トーンについて具体的な修正指示を出したとき
- `/article-critique` の自動批評では拾えない、ユーザー固有の視点を反映したいとき
- 投稿前の最終調整（表現の微調整、セクション追加・削除など）

`/article-critique` が「自動批評→機械的修正」なのに対し、`/article-revise` は「人間のフィードバック→対話的修正」を担う。

## 使い方

```
/article-revise @articles/stock_analysis/2026-03-28_xxx/ "もっと具体例を増やして、結論を強くして"
/article-revise @articles/macro_economy/2026-03-25_fed/ "導入部分が長すぎる。データの出典URLを追加して"
/article-revise @articles/asset_management/2026-03-20_nisa/ --diff "表現をもっとカジュアルに"
```

## 処理フロー

```
Step 1: パス解決・コンテキスト読み込み
├── 共通パス解決ロジック（.claude/commands/_shared/path-resolution.md）
├── meta.yaml 読み込み（category, topic, tags 等）
├── 02_draft/revised_draft.md（優先）または first_draft.md を読み込み
└── 02_draft/critic.json（存在すれば参考情報として読む）

Step 2: バックアップ作成
└── 現在の revised_draft.md → 02_draft/revisions/{slug}_rev{N}.md（YAMLフロントマター付き）

Step 3: フィードバック反映
├── ユーザーのフィードバックを解釈
├── カテゴリ別執筆ルールに従って修正（finance-article-writer スキル参照）
├── 記事品質ルール遵守（.claude/rules/article-quality-standards.md）
└── 02_draft/revised_draft.md を上書き生成

Step 4: 変更サマリー表示
├── 修正箇所のハイレベル要約
├── --diff 指定時: セクション単位の詳細 before/after
└── meta.yaml の updated_at を更新
```

## Step 1: パス解決・コンテキスト読み込み

共通パス解決ロジック（`.claude/commands/_shared/path-resolution.md`）に従う。

1. 記事ディレクトリを特定
2. `meta.yaml` を読み込み、category・topic・tags を取得
3. ドラフトの読み込み優先順位:
   - `02_draft/revised_draft.md`（存在すればこちら）
   - `02_draft/first_draft.md`（revised がなければフォールバック）
4. `02_draft/critic.json` があれば参考情報として読む（既知の問題点の把握に使う）
5. `01_research/sources.json` があれば参考情報として読む（ソースURL補完に使う）

## Step 2: バックアップ作成

上書き前に必ずバックアップを取る。ユーザーが元に戻せるようにするため。

`revisions/` はあくまでバックアップ履歴であり、投稿対象ではない。`/article-publish` が投稿するのは常に `02_draft/revised_draft.md`（最新版）のみ。

### ファイル命名規則

```
02_draft/revisions/{slug}_rev{N}.md
```

- `{slug}`: meta.yaml の `article_id` から取得（例: `2026-03-28_indonesia-telecom-sector`）
- `{N}`: リビジョン番号。`revisions/` 内の既存ファイルから最大番号を検出し、+1 する。初回は `_rev1`

例: `02_draft/revisions/2026-03-28_indonesia-telecom-sector_rev1.md`

### YAML フロントマター

各リビジョンファイルの先頭に、修正日時と変更内容のサマリーを YAML フロントマターとして記録する:

```markdown
---
revision: 1
created_at: "2026-03-29T10:05:00+09:00"
feedback: "ディスクレーマーを本文の最後に移動させて"
changes:
  - "冒頭のディスクレーマー（引用ブロック）を削除"
  - "末尾のディスクレーマーに一本化"
---

（ここに修正前の revised_draft.md の全文）
```

`revisions/` ディレクトリがなければ作成する。

## Step 3: フィードバック反映

ユーザーのフィードバックに従って記事を修正する。修正時のガイドライン:

### 基本方針

- **フィードバックに忠実に**: ユーザーが求めた変更を正確に反映する。勝手に追加の「改善」をしない
- **既存の良い部分を保持**: フィードバックで触れられていない箇所は原則として維持する
- **記事のトーン一貫性**: 部分修正でもトーンが不自然にならないよう調整する

### 品質ルール（常に遵守）

以下は `.claude/rules/article-quality-standards.md` で定義されたルール。フィードバック反映時も必ず守る:

1. **マークダウン表の画像化**: 修正で表を追加した場合は `/generate-table-image` で画像化
2. **ソースURL埋め込み**: 数値データ・統計の引用にはソースURLをリンクとして埋め込む
3. **チャートの画像化**: データ可視化が必要なら `/generate-chart-image` で画像化

### コンプライアンス（常に遵守）

修正後も以下を満たすこと:
- 末尾が「参考データソース → 挨拶文 → 免責事項」の順で構成されている
- 挨拶文（`snippets/closing-greeting.md` の全文: `いつも読んでいただきありがとうございます！…励みになります！！`）が免責事項の直前に装飾なし段落で存在する
- 免責事項（`snippets/disclaimer.md` の全文）が末尾に1箇所のみ存在する
- タイトルが具体的で読者メリットが明確（抽象タイトル・煽り記号は不可。common-rules.md § 3 参照）
- 本文・タイトルにダッシュ記号（`ーー` `——` `—` `--`）が含まれていない
- 禁止表現（「買うべき」「絶対に」等）が含まれていない

詳細: `finance-article-writer` スキルの `references/common-rules.md`

### カテゴリ別ルール参照

meta.yaml の `category` に応じて、`finance-article-writer` スキルのカテゴリ別リファレンスを確認する:

| category | 参照ファイル |
|----------|------------|
| stock_analysis | `.claude/skills/finance-article-writer/references/stock-analysis.md` |
| macro_economy | `.claude/skills/finance-article-writer/references/macro-economy.md` |
| investment_education | `.claude/skills/finance-article-writer/references/investment-education.md` |
| quant_analysis | `.claude/skills/finance-article-writer/references/quant-analysis.md` |
| market_report | `.claude/skills/finance-article-writer/references/market-report.md` |
| asset_management | `.claude/skills/finance-article-writer/references/asset-management.md` |

## Step 3.5: 決算サムネイル自動生成（earnings カテゴリのみ）

`meta.yaml` の `category` が `earnings` の場合、revised_draft.md の書き出し直後に **article-earnings-thumbnail スキルを自動で呼び出す**。

- 呼び出し: `/article-earnings-thumbnail @{article_dir}`
- スキル定義: `.claude/skills/article-earnings-thumbnail/SKILL.md`
- 出力: `{article_dir}/images/thumbnail.png`

サムネイル生成に失敗しても（ロゴ取得失敗など）記事修正自体は成功扱いとする。警告のみ表示。

`category != earnings` の場合はスキップ。

## Step 4: 変更サマリー表示

修正完了後、以下を表示する:

```markdown
## 修正完了

### フィードバック
> {ユーザーのフィードバック原文}

### 修正内容
- {変更点1}
- {変更点2}
- {変更点3}

### バックアップ
`02_draft/revisions/{slug}_rev{N}.md`

### 次のステップ
- 内容確認後、追加修正があれば再度 `/article-revise` を実行
- 公開準備ができたら `/article-publish @{article_dir}`
```

`--diff` オプションが指定された場合は、セクション単位で before/after を表示:

```markdown
### 詳細変更（--diff）

#### セクション: はじめに
**Before**: 最近の市場動向を見ると...（略）
**After**: 2026年3月の米国株市場は大きな転換点を迎えています...（略）

#### セクション: まとめ
**Before**: 以上のことから...（略）
**After**: 3つの指標が示すように...（略）
```

## meta.yaml 更新

```yaml
updated_at: "YYYY-MM-DD"  # 更新日を記録
```

`workflow` ステータスは変更しない（revision 状態を維持）。

## エラーハンドリング

### ドラフトが存在しない

```
エラー: 記事ドラフトが見つかりません

02_draft/revised_draft.md も first_draft.md も存在しません。

対処法:
- /article-draft @{article_dir} を先に実行してください
```

### meta.yaml が存在しない

```
エラー: meta.yaml が見つかりません

指定されたディレクトリは記事ディレクトリではない可能性があります。
パスを確認してください。
```

## 関連コマンド・スキル

| 名前 | 役割 | 違い |
|------|------|------|
| `/article-critique` | 自動批評→機械的修正 | AI批評エージェントが問題を検出して修正 |
| `/article-revise` | 人間フィードバック→対話的修正 | ユーザーの具体的な指示に基づいて修正 |
| `/article-publish` | note.com に下書き投稿 | 修正完了後に実行 |
| `finance-reviser` | 批評結果を反映する修正エージェント | /article-critique 内部で使用 |
