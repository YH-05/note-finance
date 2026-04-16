---
description: 発行済み決算プレビュー記事に対応するレビュー記事を自動生成します。候補選択→リサーチ→ドラフト→批評→投稿を一括実行。
argument-hint: [@preview_dir] [--skip-publish] [--mode quick|full] [--skip-hf]
---

株投資ラボの earnings カテゴリで、**既に note.com に投稿済みの決算プレビュー記事**に対応するレビュー記事（発表後の振り返り）を生成するコマンドです。

`article-earnings-review` スキルを必ず使用してください。プレビュー記事との対比構造で差別化された記事を作成します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `@preview_dir` | ○※ | - | プレビュー記事ディレクトリ（例: `@articles/earnings/2026-04-06_blk-earnings-preview/`） |
| `--skip-publish` | - | false | 投稿をスキップ |
| `--mode` | - | full | 批評モード（quick / full） |
| `--skip-hf` | - | false | ヒューマンフィードバックをスキップ（非推奨） |

※ `@preview_dir` が未指定の場合、未レビューのプレビュー候補を列挙して選択させます。

## 処理フロー

```
Phase 0: 候補特定（preview_dir 未指定時）
├─ list_unreviewed_previews.py 実行
└─ ユーザーに番号選択させる

Phase 1: レビュー記事フォルダ初期化
├─ プレビュー meta.yaml / revised_draft.md を Read
├─ focus_points 抽出（プレビュー §2 から）
├─ レビューディレクトリ作成
└─ meta.yaml 生成（type: earnings_review, preview_ref 含む）

Phase 2-5: 既存コマンド委譲
├─ /article-research
├─ /article-draft
├─ /article-critique --mode {mode}
└─ /article-publish（--skip-publish でスキップ）
```

## 実行手順

### Phase 0: 候補特定（preview_dir 未指定時のみ）

1. 以下のスクリプトを実行して未レビュー候補を列挙:

   ```bash
   uv run --with pyyaml python .claude/skills/article-earnings-review/scripts/list_unreviewed_previews.py --format table
   ```

2. 候補が 0 件の場合は以下を表示して終了:

   ```
   未レビューのプレビュー記事が見つかりませんでした。
   - 決算発表日が未到来、または
   - プレビュー自体が note 未投稿、または
   - 既にレビュー記事を作成済み

   直接プレビューを指定する場合:
     /article-earnings-review @articles/earnings/{preview_dir}/
   ```

3. 候補が複数ある場合、番号を入力させる:

   ```
   レビュー対象にするプレビュー記事の番号を入力してください (1-N):
   ```

### Phase 1: レビュー記事フォルダ初期化

1. **プレビュー記事の読み込み**:
   - `{preview_dir}/meta.yaml` を Read
   - `{preview_dir}/02_draft/revised_draft.md` を Read（focus_points 抽出のため）
   - `ticker`, `fiscal_quarter`, `fiscal_year`, `earnings_date`, `announcement_time`, `note_url` / `draft_url` を取得

2. **focus_points の抽出**:
   - `revised_draft.md` の「## 2. 今回の決算ポイント」セクションから着目KPI・注目ドライバーを2-5個抽出
   - 箇条書きで自然言語の短文（各20-40字）

3. **レビューディレクトリ作成**:
   - 命名: `articles/earnings/{今日のYYYY-MM-DD}_{ticker-lower}-q{N}-{year}-earnings-review/`
   - サブディレクトリ: `01_research/`, `02_draft/`, `03_published/`, `images/`

4. **meta.yaml 生成**: `article-earnings-review` スキルの「meta.yaml テンプレート」に従う
   - `type: earnings_review`
   - `preview_ref.path`: プレビューの相対パス
   - `preview_ref.note_url`: プレビューの note URL
   - `preview_ref.focus_points`: 抽出した箇条書き

5. **[HF1] 承認**:
   --skip-hf が指定されていない場合:

   ```
   レビュー記事フォルダを作成しました。

   - 対象: {ticker} Q{N} {year}
   - プレビュー記事: {preview_dir}
   - プレビューURL: {note_url}
   - レビューフォルダ: {review_dir}
   - 抽出した focus_points:
     1. {focus_point_1}
     2. {focus_point_2}
     ...

   このままリサーチに進みますか？ (y/n)
   ```

### Phase 2: リサーチ実行

`/article-research @{review_dir}` を実行。

実行時、investment-research エージェントに以下を伝達:

- 発表日（`earnings_date`）以降の情報を優先的に収集すること
- `preview_ref.focus_points` をクエリシードに利用すること
- SEC EDGAR 8-K（発表当日版）、カンファレンスコール要旨、アナリストレーティング変更を必須で取得
- プレビュー記事の内容と重複しないトピックを意識すること

### Phase 3: ドラフト作成

`/article-draft @{review_dir}` を実行。

`finance-article-writer` エージェントへの追加指示:

1. `meta.yaml.preview_ref.path` のプレビュー記事の `revised_draft.md` を**事前に Read** すること
2. `.claude/skills/finance-article-writer/references/earnings.md` の末尾にある **「決算レビュー版（earnings_review）」セクション** を参照すること
3. §0（プレビュー記事のおさらい）に `preview_ref.note_url` へのマークダウンリンクを必ず埋め込むこと
4. §2 で `preview_ref.focus_points` の全項目について「プレビュー時の問い → 実績 → 差分」の3点セットで言及すること
5. §3 ではプレビュー `revised_draft.md` に書かれていない新情報のみを扱うこと

### Phase 4: 批評・修正

`/article-critique @{review_dir} --mode {mode}` を実行。

通常の批評フローに加え、レビュー版固有のチェック:

- [ ] §0 にプレビュー note リンクがあるか
- [ ] `preview_ref.focus_points` の全項目が §2 に登場するか
- [ ] §3 の内容がプレビューと重複していないか
- [ ] タイトルサフィックスが「決算レビュー」か

Step 4.5 のサムネイル生成は `type == earnings_review` を検出して Pencil nodeId `har1R`（グリーンバッジ）を使用する（既存の article-earnings-thumbnail スキルの既定挙動）。

### Phase 5: 投稿

`--skip-publish` が指定されていない場合、`/article-publish @{review_dir}` を実行。

## 完了報告

```markdown
## 決算レビュー記事作成完了

### 記事情報
- **対象**: {ticker} Q{N} {year}
- **プレビュー記事**: {preview_dir}
  - note URL: {preview_note_url}
- **レビュー記事**: {review_dir}
  - note URL: {review_note_url または "未投稿"}

### 対比構造の充足
- プレビュー focus_points: {N} 項目 → §2 で全て言及済み
- §3 で扱った新情報: {M} 項目
- §0 プレビューリンク: 埋め込み済み

### 最終スコア
| 項目 | スコア |
|------|--------|
| 総合 | {overall}/100 |
| コンプライアンス | {compliance}/100 |
| 事実正確性 | {fact}/100 |

### 次のステップ
1. note.com で下書きを確認: {review_note_url}
2. サムネイル確認
3. 公開ボタンで公開
```

## 使用例

```bash
# 候補から選択して作成
/article-earnings-review

# プレビューを直接指定
/article-earnings-review @articles/earnings/2026-04-06_blk-earnings-preview/

# 批評・修正までで投稿なし
/article-earnings-review @articles/earnings/2026-04-06_blk-earnings-preview/ --skip-publish

# クイックモード
/article-earnings-review @articles/earnings/2026-04-06_blk-earnings-preview/ --mode quick
```

## エラーハンドリング

### プレビュー記事が未投稿の場合

```
エラー: プレビュー記事が note に未投稿です

指定: {preview_dir}
meta.yaml.workflow.publish: {status}

プレビューを先に投稿してから再実行してください:
  /article-publish @{preview_dir}
```

### 決算発表日が未到来の場合

```
警告: 決算発表日が未到来です

earnings_date: {date}（今日: {today}）

通常、発表後に本コマンドを実行します。強制実行する場合は --force を指定してください。
```

### 同ティッカー・同四半期のレビュー記事が既存の場合

```
エラー: 既にレビュー記事が存在します

既存: {existing_review_dir}

別のティッカー・四半期を指定するか、既存レビュー記事を編集してください:
  /article-revise @{existing_review_dir}
```

## 関連コマンド

- **スキル本体**: `.claude/skills/article-earnings-review/SKILL.md`
- **候補列挙スクリプト**: `.claude/skills/article-earnings-review/scripts/list_unreviewed_previews.py`
- **執筆ガイド**: `.claude/skills/finance-article-writer/references/earnings.md`（「決算レビュー版」セクション）
- **構成コマンド**: `/article-research`, `/article-draft`, `/article-critique`, `/article-publish`
- **サムネイル**: `/article-earnings-thumbnail`（type で自動分岐）
