# equity_research/

個別銘柄のリサーチ情報を管理するディレクトリ。

## フォルダ構造

```
equity_research/
├── README.md              # このファイル
├── _template/             # 新規銘柄追加時のテンプレート
│   └── research_memo/
│       ├── README.md
│       ├── sources/       # 元ソース（PDF：IR資料・有報・アナリストレポート等）
│       ├── notebooklm_qa/ # NotebookLM Q&A結果（phase別Markdown）
│       ├── converted/     # PDF→Markdown変換済みファイル
│       └── initial_report/ # Initial Report ドラフト・修正稿
└── {TICKER}/              # 例: ISAT_IJ, 7203_JP, AAPL_US
    └── research_memo/
        └── （上記と同じ構造）
```

## 新規銘柄の追加手順

```bash
TICKER=7203_JP
cp -r equity_research/_template/research_memo equity_research/$TICKER/research_memo
```

## ティッカー命名規則

`{銘柄コード}_{取引所コード}` 形式

| 例 | 説明 |
|----|------|
| `ISAT_IJ` | Indosat（インドネシア証券取引所） |
| `7203_JP` | トヨタ自動車（東証） |
| `AAPL_US` | Apple（NASDAQ） |
