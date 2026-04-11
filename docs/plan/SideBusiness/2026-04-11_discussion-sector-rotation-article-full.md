# 議論メモ: セクターローテーション記事 — article-full全工程完走

**日付**: 2026-04-11
**参加**: ユーザー + AI

## 背景・コンテキスト

investment_education カテゴリの記事「セクターローテーション入門：Mag7偏重からバランス型への移行タイミング」を `/article-full` で全工程（リサーチ→ドラフト→批評→修正→note.com投稿）を1セッションで実行した。

セッション途中でNeo4j接続問題が発生し、外付けSSD（/Volumes/NeoData）未マウントによるEnterprise DBの停止を診断・解決した。

## 議論のサマリー

### Neo4j Enterprise 接続問題の解決

- research-neo4j が bolt://localhost:7688 で接続不可
- 診断: Docker コンテナは起動しているが、`/Volumes/NeoData` SSD が未マウントで research データベースが "stopping" 状態
- 解決: ユーザーが SSD を接続 → `docker restart neo4j-enterprise` → 全 DB がオンラインに復帰
- **教訓**: Neo4j Enterprise コンテナは /Volumes/NeoData 外付け SSD を必須前提とする。SSD 未接続時は DB 起動不可。

### 記事品質: H1見出し問題の発見と修正

- `finance-reviser` が生成した `revised_draft.md` の本文セクション見出しがすべて `# ` (H1) だった
- note.com パーサーは H1 をタイトルとして扱い、本文見出しとして認識しない → 全セクションが段落として扱われる問題
- `02_draft/revised_draft.md` の本文8セクションを手動で `## ` (H2) に変換して解決
- **根本原因**: `finance-reviser` のプロンプトまたは `first_draft.md` の見出しレベルが H1 だった

### 批評結果（全6エージェント並列）

| 批評項目 | スコア | 主な問題 |
|---------|-------|---------|
| 事実正確性 | 72/100 | XLK YTD 符号誤り（+1.20% → 実測 -0.81%）、日付不整合 |
| コンプライアンス | 78/100 | 「積極的に推奨」表現（要修正） |
| 構成 | 88/100 | 概念定義の位置 |
| データ正確性 | 72/100 | ソースURL欠落（GDP/MS/TSLA/S&P493） |
| 読みやすさ | 82/100 | 「オールドスクール」等 |
| ライター規約 | 83/100 | H1重複、免責事項の---装飾 |
| **総合** | **79/100** | |

### 投稿結果

- note.com 下書きURL: https://editor.note.com/notes/n8092910d0bd6/edit/
- ブロック数: 227（heading:9, paragraph:198, list_item:19, separator:1）
- 投稿アカウント: 株投資ラボ (kabu-lab)

## 決定事項

1. **note.com 投稿前の H1→H2 変換**: 本文見出しに `# ` が使われている場合、投稿前に `## ` に変換する必要がある。finance-reviser/first_draft の見出しレベルを修正すること。
2. **Neo4j Enterprise = SSD 必須**: `docker restart neo4j-enterprise` 前に `/Volumes/NeoData` SSD の接続を確認する運用ルールを確立する。

## アクションアイテム

- [ ] note.comのセクターローテーション記事（https://editor.note.com/notes/n8092910d0bd6/edit/）でカバー画像・ハッシュタグを設定して公開 (優先度: 高)
- [ ] finance-reviser プロンプトまたは first_draft 生成ルールで、本文見出しを H2 で生成するよう修正 (優先度: 中)

## 次回の議論トピック

- セクターローテーション記事の公開後パフォーマンス確認
- TSMC Q1 決算記事、dividend-ETF記事、fed-zero-cuts記事 等の未投稿記事の処理

## 参考情報

- 記事ディレクトリ: `articles/investment_education/2026-04-11_sector-rotation-mag7-shift/`
- セッション: research(KG+Tavily) → draft(9,735字) → critique(6並列) → revise → publish
- note.com パーサー仕様: H1はタイトル扱い、本文見出しはH2/H3のみ有効
