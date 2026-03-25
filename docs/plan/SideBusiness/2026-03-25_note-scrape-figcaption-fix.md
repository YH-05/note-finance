# 議論メモ: note-scrape figcaption対応修正

**日付**: 2026-03-25
**参加**: ユーザー + AI

## 背景・コンテキスト

note.com/fukuoka1116 のスクレイピングで全18記事の `body_length=0` となり、
RawStore に1件も保存されない問題が発生。

## 調査結果

- セレクタ `.note-common-styles__textnote-body` は正しく存在
- しかし子要素に `<p>` がなく、`<figure><figcaption>` 内に `<br>` 区切りでテキストが格納されていた
- 既存の `extract_body_text()` は `<p>` 要素のみを検索 → 0件で空文字返却
- `skip_empty=True`（RawStore デフォルト）により全記事スキップ

## 修正内容

`src/data_pipeline/collectors/note_com_browser.py` の `extract_body_text()` に3段階フォールバックを実装:

1. **Strategy 1**: `<p>` 要素（従来の標準レイアウト）
2. **Strategy 2**: `<figcaption>` 要素（画像キャプション型レイアウト） ← 今回のケース
3. **Strategy 3**: `textContent` 直接取得（最終フォールバック）

figcaption パターンでは `innerHTML` の `<br>` を改行に変換してテキスト抽出。

## 実行結果

| 項目 | 修正前 | 修正後 |
|------|--------|--------|
| body_length | 全記事 0 | 1000〜2400字 |
| RawStore 保存 | 0件 | 18件 |

### creator-neo4j 投入結果

- Stories: 18件（全記事エッセイ/体験談型）
- Entities: 5, Concepts: 89（13カテゴリ）
- Neo4j: 121ノード, 142リレーション

### RSSモニター

- `fukuoka1116` を genre=career で追加済み

## 決定事項

1. extract_body_text に3段階フォールバック戦略を採用（p → figcaption → textContent）

## アクションアイテム

- [ ] extract_body_text 修正のコミット・PR作成（優先度: 中）
- [ ] 他クリエイターでの回帰テスト確認（優先度: 低）

## 対象ファイル

- `src/data_pipeline/collectors/note_com_browser.py` — extract_body_text() 修正
