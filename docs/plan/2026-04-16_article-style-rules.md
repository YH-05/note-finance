# 議論メモ: 株投資ラボ記事の文体ルール3点

**日付**: 2026-04-16
**参加**: ユーザー + AI
**関連Project**: 株投資ラボ収益化
**関連Discussion ID**: `disc-2026-04-16-article-style-rules`

## 背景・コンテキスト

note.com「株投資ラボ」アカウントで運用している金融記事（全6カテゴリ: macro / stock / asset / education / report / earnings）について、ユーザーから文体ルールの統一要望が発生した。既存記事のトーン・タイトル付け・末尾構成に揺らぎがあり、読者とのエンゲージメント強化とスキ・フォロー率向上を狙う。

## 議論のサマリー

ユーザーから以下3点の具体的指示が明示され、それを記事執筆ワークフロー全体に反映する方針で合意。

1. **ダッシュ記号禁止**: `ーー` `——` `—` `--` を全面禁止し、日本語として自然な読点・かっこ・全角コロン・縦棒に置換する
2. **タイトルの明瞭化**: 一発で内容が理解でき、読者メリット（分かる・学べる・比較・解決）を含む形に統一する
3. **末尾挨拶文テンプレート化**: 免責事項の直前に固定の挨拶文を必ず挿入する

## 決定事項

### D1: ダッシュ記号の全カテゴリ禁止

- 対象記号: `ーー`（長音2連続）、`——`（em dash 2連続）、`—`（em dash 単体）、`--`（ハイフン2連続）
- 代替: 読点「、」・かっこ書き「（〜）」・全角コロン「: 」・全角縦棒「｜」
- 理由: ダッシュは日本語記事では威圧的・翻訳調に見え、個人投資家・初心者〜中級者層に合わない
- `finance-critic-compliance` エージェントと `finance-reviser` で検出・修正

### D2: タイトル生成ルールの明文化

- 全角30-38字以内（note.com タイムラインで折り返さないサイズ）
- 具体的対象（企業名・制度名・指標名）＋読者メリット（「分かる」「比較」「シミュレーション」等）
- 推奨パターン: 「〇〇が分かる」型、「〇〇を比較」型、数字＋結論型、疑問解決型、速報解説型
- 禁止: 抽象タイトル（「市場動向について」）、煽り記号連打、投資助言的断定
- earnings カテゴリのみ固定フォーマット `【🇺🇸米株決算】{企業名}（{ティッカー}）Q{数字} {年} 決算プレビュー/レビュー` を厳守（既存仕様維持）

### D3: 記事末尾テンプレートの統一

末尾構成を全カテゴリ共通で以下の順に固定:

```
（本文）
↓
## 参考データソース
↓
---
↓
いつも読んでいただきありがとうございます！これからも株式投資・資産形成で役立つ記事をお届けします⭐️スキやフォローしていただけると励みになります！！
↓
---
↓
免責事項: 本記事は一般的な情報提供を目的としており…
```

- 挨拶文を `snippets/closing-greeting.md` に新規切り出し
- 装飾禁止（`>` 引用、`**` 太字、`##` 見出しなし）
- `scripts/note_publisher/markdown_parser.py` の `_remove_references_section` に挨拶文プレフィックスを境界として追加し、note.com 投稿時も保護

## 実装内容（16ファイル）

### 新規作成（1）

- `snippets/closing-greeting.md` — 挨拶文固定テキスト

### 共通ルール（1）

- `.claude/skills/finance-article-writer/references/common-rules.md`
  - § 3 「タイトル生成ルール」新設
  - § 4 「記事末尾テンプレート（挨拶文＋免責事項）」新設
  - § 6.5 「記号の禁止」新設（ダッシュ禁止）
  - § 9 共通チェックリストにタイトル・文体・コンプライアンス項目を追加

### カテゴリ別ルール（6）

全カテゴリのセクション構成テンプレート末尾を「参考データソース → 挨拶文 → 免責事項」に統一し、タイトル例を追加:

- `references/stock-analysis.md`
- `references/macro-economy.md`
- `references/investment-education.md`
- `references/asset-management.md`
- `references/market-report.md`
- `references/earnings.md`（固定フォーマットの例外注記を追加）

### 批評基準（2）

- `.claude/resources/critique-criteria/compliance-standards.md`
  - 禁止記号リスト追加
  - 必須テンプレート（挨拶文＋免責事項）を定義
  - チェック項目に「記事末尾テンプレート」セクション追加
- `.claude/resources/critique-criteria/writer-rules-evaluation.md`
  - § 0 「タイトル品質チェック (WR-TL)」新設（具体性・読者メリット・字数・禁止記号・煽り記号）

### 批評・修正エージェント（3）

- `.claude/agents/finance-critic-compliance.md`
  - スキーマに `greeting` / `prohibited_symbol` カテゴリ追加
  - `required_disclaimers.closing_greeting` と `order_correct` フィールド追加
  - 処理フローに禁止記号スキャン・挨拶文検出・順序確認を明示
- `.claude/agents/finance-reviser.md`
  - 記事末尾テンプレート追加・禁止記号除去・タイトル調整のルールを追加
  - 品質チェックリストに挨拶文・禁止記号・タイトルを追加
- `.claude/agents/asset-management-reviser.md`
  - 挨拶文の確認・追加ルール、禁止記号除去ルールを追加

### スキル（2）

- `.claude/skills/article-publish/SKILL.md` — 投稿前品質チェックリストにタイトル・文体・末尾テンプレート項目を追加
- `.claude/skills/article-revise/SKILL.md` — 修正時のコンプライアンス遵守項目に末尾構成・タイトル・禁止記号を追加

### スクリプト（1）

- `scripts/note_publisher/markdown_parser.py`
  - `_CLOSING_GREETING_PREFIX` 定数追加（`いつも読んでいただきありがとうございます`）
  - `_remove_references_section` に挨拶文段落の終了境界判定を追加

## アクションアイテム

- [ ] 既存記事への遡及適用（ユーザー判断。運用中記事で旧末尾構成のものは次回 `article-revise` で随時更新） (優先度: 低)
- [ ] 動作検証: 次回の記事投稿時（任意の1記事）で新ルールに従ったドラフト生成・批評・投稿が期待通り動作することを確認 (優先度: 中)
- [ ] markdown_parser テスト追加: 挨拶文境界判定の unit test を `tests/scripts/note_publisher/test_markdown_parser.py` に追加（既存の TestReferencesSection と同じ構造で） (優先度: 中)

## 次回の議論トピック

- 既存記事（articles/ 配下の過去記事）に新末尾テンプレートを一括適用するかどうか（バッチスクリプトで実施するか、新規記事からのみ適用するか）
- タイトルルール適用の効果測定（note.com の記事ビュー・スキ率・フォロー率の比較）

## 参考情報

- feedback メモリに記録済み: `feedback_article_quality.md`（ルール4-6追記）
- Project: `株投資ラボ収益化`
- Neo4j Discussion ID: `disc-2026-04-16-article-style-rules`（note-neo4j 保存は `/Volumes/NeoData` マウント復旧後に要再試行）
