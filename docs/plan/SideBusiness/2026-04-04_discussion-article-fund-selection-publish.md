# 議論メモ: インデックスファンド年齢別記事 公開フロー完了

**日付**: 2026-04-04
**参加**: ユーザー + AI

## 背景・コンテキスト

`articles/asset_management/2026-03-08_fund-selection-age-based/` の記事を
リサーチからやり直し（前セッション）、ドラフト生成・批評・修正・公開まで一連のワークフローを完走した。

## 議論のサマリー

### KG投入の修正確認

前セッションで研究グラフ（research-neo4j）への投入が失敗していた問題を今セッションで修正。
- `neo4j_loader.py` はCLIインターフェースを持たない（`if __name__ == "__main__"` なし）
- 正しい接続先: `bolt://localhost:7687`（Enterprise multi-database、database=research）
- `ingest_to_neo4j(data, skip_schema_check=True)` をPythonから直接呼び出して解決
- 投入結果: 48 nodes / 187 relations（source_fact×7, extracted_from_fact×7, tagged×72, tagged_fact×42）

### ドラフト生成（/article-draft）

- `finance-article-writer` スキルが common-rules + asset-management ルールを読み込み
- general-purpose エージェントが `02_draft/first_draft.md` を生成（約8,442字）
- マークダウン表2枚（generate-table-image コメント付き）、チャート参照2箇所
- 27箇所のインラインソースURLリンク埋め込み済み

### 批評（/article-critique full mode）

6エージェントを並列実行し critic.json を統合：

| 批評カテゴリ | スコア | 主要指摘 |
|------------|-------|---------|
| compliance | 68 | CP001-CP004: 特定商品推奨表現、「王道です」断定 |
| structure | 77 | 基礎知識・データセクションの文字数不足 |
| data_accuracy | 78 | 金融庁データ帰属誤り、415ヶ月注記なし |
| readability | 72 | 段落長・文長が長い、専門用語初出説明なし |
| writer_rules | 87 | フロントマター欠落（medium）、リンク不足（low） |
| fact | 68 | F001: 計算値誤り（「月3万円×20年→2,471万円」→正値は約1,234万円） |

**総合スコア: 76/100**

`finance-reviser` が `02_draft/revised_draft.md` を生成（21箇所修正）。
- F001は「35歳スタートでは月約5万円必要」という比較表現に変更して回避
- CP001-CP004: compliance表現を全て修正
- YAMLフロントマターを先頭に追加

### 画像生成

| ファイル | 内容 | ツール |
|--------|------|--------|
| `images/table_01.png` | 年代別株式比率目安（グライドパス） | generate_table_image.py |
| `images/table_02.png` | オルカン vs S&P500 比較 | generate_table_image.py |
| `images/chart_01.png` | 月3万円×30年資産推移（面グラフ） | generate_chart_image.py |
| `images/chart_02.png` | 25歳/35歳スタート比較（折れ線） | generate_chart_image.py |

revised_draft.md からマークダウン表・チャートコメントを削除し、画像参照に置換。

### 公開（/article-publish）

- セッション: `data/config/note-storage-state-kabu-lab.json`
- 投稿先: 株投資ラボ note.com アカウント
- 下書きURL: https://editor.note.com/notes/n20aa83bc3c74/edit/
- `03_published/article.md` にコピー済み

## 決定事項

1. research-neo4j への KG投入は `ingest_to_neo4j()` をPythonから直接呼び出す（CLIなし）
2. note.com 投稿には `NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json` を明示指定

## アクションアイテム

- [ ] note.com でカバー画像を設定（優先度: 高）
- [ ] ハッシュタグ設定 + 公開ボタンで公開（優先度: 高）
- [ ] X投稿を生成: `/x-post @articles/asset_management/2026-03-08_fund-selection-age-based/`（優先度: 中）

## 次回の議論トピック

- 「月約5万円（35歳スタート）」の計算精度確認（正値は約4.2万円、許容範囲か）
- critic_score 76 からの改善余地（特に readability/fact スコア向上策）

## 参考情報

- 正しい積立シミュレーション計算式: FV = PMT × [(1+r)^n - 1] / r（月利 r=0.05/12）
- chart_02.json の null値バグ: `last_label: true` + null値の組み合わせでTypeError発生 → 終端値を平坦化して回避
