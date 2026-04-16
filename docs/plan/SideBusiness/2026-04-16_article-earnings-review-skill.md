# 議論メモ: 決算レビュー記事の自動生成スキル開発

**日付**: 2026-04-16
**参加**: ユーザー + AI
**プロジェクト**: 株投資ラボ収益化

## 背景・コンテキスト

株投資ラボ（note.com アカウント）では earnings カテゴリでプレビュー記事（発表3-5日前）を量産する仕組み（`/article-full --category earnings`）が整っている。プレビュー記事は 4/6 (BLK) / 4/11 (JPM) / 4/15 (GE, NFLX, TSLA, UNH) / 4/22 (IBM) 等を発行済み。

現時点で発行済みのプレビュー記事に対し、決算発表後のレビュー記事（事後振り返り）の手動作成は行われているが、プレビュー時点の焦点との対比を含む体系的なワークフローは未整備。既存のレビュー記事は 2026-04-11 の TSMC と 2026-04-14 の BLK のみ。

## 議論のサマリー

### 論点1: 実装方式（新規コマンド vs 既存コマンド拡張）

初期提案として `/article-earnings-review` 新規コマンド + 補助スクリプトで候補列挙を分離する構成を検討した。ユーザーから「`/article-full` にフラグ引数を追加する方式はどうか」との対案があり、折衷案として「候補列挙は `/article-status` 等の補助コマンド、実行本体は `/article-full --review-of` フラグ」を提示した。

最終的にユーザーが「新しいスキルコマンド作成方式で進める」と判断し、独立コマンド方式を採用。

### 論点2: プレビュー→レビューの紐付け方法

プレビュー記事と対応するレビュー記事を機械的に紐付けるために、レビュー記事の `meta.yaml` に `preview_ref` フィールドを追加:

- `preview_ref.path`: プレビュー記事ディレクトリの相対パス
- `preview_ref.note_url`: プレビューの note.com URL（冒頭リンク埋め込み用）
- `preview_ref.focus_points`: プレビュー時点の注目ポイントのリスト（2-5個）

### 論点3: 執筆ルールの配置場所

プレビュー用の `.claude/skills/finance-article-writer/references/earnings.md` と別ファイル化するか、同ファイル内に追記するかを検討。earnings カテゴリ内の派生仕様であるため、同ファイル末尾に「決算レビュー版（earnings_review）」セクションを追記する方針とした（finance-article-writer スキルの参照先を分岐させる必要がなくなる）。

### 論点4: meta.yaml フィールド揺れへの対応

既存プレビュー記事の meta.yaml には複数の表記揺れが存在:

- `symbol` (単一文字列) vs `symbols[]` (リスト)
- `fiscal_quarter: "Q1"` + `fiscal_year: 2026` vs `fiscal_quarter: "Q1 2026"` vs `fiscal_quarter_ending: "Mar/2026"`
- `note_url` vs `draft_url`
- ディレクトリ命名3種（`-q1-2026-earnings-preview` / `-earnings-preview` / `-earnings-review-2026q1`）

候補列挙スクリプト側で吸収する方針とし、meta.yaml と ディレクトリ名の両方からフォールバック推定する関数を実装した。

## 決定事項

1. **独立コマンド方式の採用**: `/article-full` に `--review-of` フラグを追加するのではなく、`/article-earnings-review` を新規スラッシュコマンドとして作成する
2. **プレビュー紐付けは `meta.yaml.preview_ref`**: レビュー記事の meta.yaml に `preview_ref.path` / `preview_ref.note_url` / `preview_ref.focus_points` を必須フィールドとして追加
3. **執筆ルールは earnings.md に追記**: 新規ファイルを作らず、`.claude/skills/finance-article-writer/references/earnings.md` の末尾に「決算レビュー版」セクションを追記
4. **レビュー記事のセクション構成を6セクション+§0で固定**: §0 プレビューおさらい / §1 ハイライト / §2 focus_points 答え合わせ / §3 未言及新情報 / §4 株価反応 / §5 次四半期 / §6 まとめ
5. **フィールド揺れ吸収は Python スクリプト側で実装**: meta.yaml と ディレクトリ命名の両方からフォールバック推定する関数を持つ

## アクションアイテム

- [x] `.claude/skills/article-earnings-review/scripts/list_unreviewed_previews.py` 作成（優先度: 高）
- [x] `.claude/skills/article-earnings-review/SKILL.md` 作成（優先度: 高）
- [x] `.claude/commands/article-earnings-review.md` 作成（優先度: 高）
- [x] `.claude/skills/finance-article-writer/references/earnings.md` に「決算レビュー版」セクション追記（優先度: 高）
- [ ] 実運用テスト: BLK（レビュー済み）と TSMC（レビュー済み）が正しく除外されること、新規プレビューが検出されることを確認（優先度: 中）
- [ ] JPMorgan Q1 2026 プレビューの `earnings_date` 欠落を修正（meta.yaml 補完）（優先度: 中）
- [ ] `article-earnings-thumbnail` スキルの `earnings_review` 用 Pencil nodeId `har1R`（グリーンバッジ）の実在とスタイル確認（優先度: 中）
- [ ] 初回レビュー記事作成時のドッグフーディング: 4/14 BLK Q1 2026 決算を対象に `/article-earnings-review` を実行し、対比構造の品質を評価（優先度: 低、次回発表サイクル時）

## 次回の議論トピック

- レビュー記事の実行結果を踏まえた改善点（focus_points 抽出精度、§3 の新情報ソースの質）
- 決算レビュー記事の note.com での PV・有料購読 CVR（プレビュー単独 vs レビュー単独 vs セット）
- プレビュー記事の誘導リンクを更新する仕組み（レビュー作成後、プレビュー記事内に「レビュー版はこちら」リンクを追記）

## 参考情報

### 成果物

| ファイル | 役割 |
|---------|------|
| `.claude/commands/article-earnings-review.md` | `/article-earnings-review` スラッシュコマンド |
| `.claude/skills/article-earnings-review/SKILL.md` | スキル本体 |
| `.claude/skills/article-earnings-review/scripts/list_unreviewed_previews.py` | 未レビュー候補列挙スクリプト |
| `.claude/skills/finance-article-writer/references/earnings.md` | 末尾に「決算レビュー版」セクション追記 |

### 動作確認結果（2026-04-16）

スクリプト `list_unreviewed_previews.py` を `--today 2026-04-16` で実行:

- BLK（`2026-04-06_blk-earnings-preview`）: 既にレビュー記事（`2026-04-14_blk-earnings-review-2026q1`）が存在 → 正しく除外
- JPMorgan（`2026-04-11_jpmorgan-q1-2026-earnings-preview`）: `earnings_date` 欠落 → 警告ログでスキップ
- TSLA/NFLX/GE/UNH/IBM: いずれも発表日未到来 → 除外
- 結果: 該当候補なし（想定通り）
