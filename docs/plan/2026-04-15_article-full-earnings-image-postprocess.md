# 改善プラン: article-full (earnings) の画像生成ポストプロセス自動化

**日付**: 2026-04-15
**対象**: `/article-full` earnings カテゴリ実行時の画像生成保証
**関連**: `.claude/commands/article-critique.md`, `.claude/rules/article-quality-standards.md`

## 背景

`/article-full --category earnings` を実行した際、3種類の画像生成スキルの発動保証に差がある：

| 画像種別 | 現状の発動保証 | 発動箇所 |
|---------|---------------|---------|
| サムネイル (`article-earnings-thumbnail`) | ✅ 保証あり | `article-critique.md` Step 4.5 で明示的な自動呼び出し |
| 表画像化 (`generate-table-image`) | ⚠️ 保証なし | ルール／チェックリストのみ、LLM判断依存 |
| チャート画像化 (`generate-chart-image`) | ⚠️ 保証なし | 同上 |

ライター／リバイザーエージェントが `.claude/rules/article-quality-standards.md` を参照して「自律的に判断」する設計のため、マークダウン表がそのまま残る・チャート化すべきデータがテキストのまま、という取りこぼしが発生しうる。

## 目標

**revised_draft.md 生成後に、表・チャートの画像化がステップとして強制発動される状態**を作る。

earnings カテゴリでは特に数値表・株価/業績チャートが多いため、最優先で対応。

## 方針: 3段階の改善

### Phase 1（即効・最小変更）: article-critique.md に画像化ステップを追加

`article-critique.md` の Step 4.5（サムネイル生成）の**直前に Step 4.4（表・チャート画像化）を新設**する。

```
Step 4: リバイザー実行 → revised_draft.md 生成
Step 4.4: 画像ポストプロセス（全カテゴリ共通）  ← 新設
  ├── revised_draft.md をスキャン
  ├── マークダウン表を検出 → 検出数を表示
  └── 検出あり → エージェントに画像化を指示（LLM裁量で残す道も許容）
Step 4.5: 決算サムネイル生成（earnings のみ）
Step 5: ステータス更新
```

**実装コスト**: 低（`article-critique.md` の文言追加のみ）
**効果**: 中（明示ステップ化で「忘れる」確率が大幅減、ただし実行はエージェント判断）

### Phase 2（確実化）: ポストプロセススキルを新設

`article-image-postprocess` スキルを新規作成し、Step 4.4 で呼び出す。

**スキル仕様**:
- 入力: `{article_dir}/02_draft/revised_draft.md`
- 処理:
  1. markdown AST パースでテーブルを抽出（`re` または `mistune`）
  2. 各テーブルに対してユーザー/LLMが画像化要否を判定
  3. 画像化するテーブルを JSON 化 → `scripts/generate_table_image.py` 実行
  4. revised_draft.md のテーブルを `![](images/table_*.png)` に自動置換
  5. チャート化すべき数値列（時系列データ等）は LLM で検出 → `scripts/generate_chart_image.py` で生成
- 出力: 更新された revised_draft.md + `images/table_*.png`, `images/chart_*.png`

**実装コスト**: 中（新規スキル + 検出ロジック + markdown 置換）
**効果**: 高（earnings 以外のカテゴリでも再利用可能）

### Phase 3（完全自動化・任意）: CI的な検証ステップ

`article-publish` 実行前に残存マークダウン表を検出したら **投稿を中止** する gate を追加。

**実装コスト**: 低（`article-publish.md` にチェックステップ追加）
**効果**: 高（最終防衛線として機能）

## 推奨実装順序

1. **Phase 1 を即実装**（`article-critique.md` 更新のみ、15分）
2. Phase 3 を次に追加（publish の gate、10分）
3. Phase 2 は earnings 記事数件で Phase 1/3 の取りこぼしパターンを観察してから設計

## Phase 1 の具体的な変更案

`.claude/commands/article-critique.md` の Step 4.5 の直前に追加:

```markdown
### Step 4.4: 表・チャート画像化ポストプロセス（全カテゴリ共通）

revised_draft.md を生成した後、以下を**必ず実行する**:

1. revised_draft.md 内のマークダウン表を検出（`| ... |` 行を grep）
2. 検出された表それぞれについて:
   - `/generate-table-image` で PNG 化
   - `articles/{category}/{slug}/images/table_*.png` に保存
   - revised_draft.md の該当表を `![表タイトル](images/table_*.png)` に置換
3. 時系列データ・比較データがテキスト記述のまま残っている箇所を LLM で検出
4. 検出された箇所について `/generate-chart-image` で PNG 化し埋め込み
5. 変更後の revised_draft.md を保存

検出漏れ・画像化失敗は警告のみ表示し、Step 4.5 に進む。
```

## 検証方法

Phase 1 実装後、以下の earnings 記事で検証:

- 今週作成済みの `articles/earnings/2026-04-11_tsmc-q1-2026-earnings-review/`
- 新規作成する NFLX Q1 2026 earnings preview

**成功基準**:
- revised_draft.md に `| --- |` 形式のマークダウン表が0個
- `images/table_*.png` が最低1枚生成される
- サムネイル・表・チャートの3種全てが `images/` に揃う

## リスク・留意点

1. **短すぎる表の過剰画像化**: 2列×3行程度の小さな表まで画像化すると note の可読性が落ちる。**閾値（例: 3列以上 or 5行以上）** を設けるべき
2. **Markdown 置換ミス**: テーブル検出の正規表現が壊れると本文を破壊する恐れ → 必ず diff 表示 + バックアップ（`revised_draft.md.bak`）
3. **チャート化判定の曖昧さ**: LLM に任せると画像化しすぎる/しなさすぎるブレが出る。Phase 2 で閾値と例を明文化

## アクションアイテム

- [ ] Phase 1: `article-critique.md` に Step 4.4 を追加（優先度: 高）
- [ ] Phase 3: `article-publish.md` に残存表検出 gate を追加（優先度: 高）
- [ ] Phase 1 実装後、NFLX Q1 2026 プレビュー記事で動作検証（優先度: 中）
- [ ] Phase 2: `article-image-postprocess` スキル設計ドキュメント起票（優先度: 中）
- [ ] 表画像化の閾値ルール（3列以上 or 5行以上）を `article-quality-standards.md` に追記（優先度: 中）

## 次回の議論トピック

- Phase 2 スキルの markdown 置換方式（正規表現 vs mistune AST）
- チャート化判定を LLM に任せる場合のプロンプト設計
- 他カテゴリ（stock_analysis, macro_economy）への展開タイミング
