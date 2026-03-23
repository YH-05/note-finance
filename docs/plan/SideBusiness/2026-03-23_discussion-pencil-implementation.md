# 議論メモ: career_sister カルーセルテンプレート Pencil MCP 実装

**日付**: 2026-03-23
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-23-pencil-implementation
**前提Discussion**: disc-2026-03-23-pencil-template-design（設計方針）

## 背景・コンテキスト

前半セッションで確定した設計方針（ウォームプロ、7枚構成、型別色違い、丸ゴシック、上下分割表紙）に基づき、Pencil MCPを使って実際にcareer_sister用カルーセルテンプレートを実装した。

## 実装サマリー

### 作成した7枚のスライド

| 枚 | 名称 | 内容 | ノードID |
|----|------|------|---------|
| 1 | Cover - 表紙 | 上下分割型（テラコッタ上部 + フックテキスト） | `2NQJt` |
| 2 | Body1 - 問題提起 | 「面接で一番聞かれるのは志望動機じゃない」 | `uuFte` |
| 3 | Body2 - ポイント1 | 転職理由のネガティブ→ポジティブ変換 | `jtSb1` |
| 4 | Body3 - ポイント2 | 志望動機の3軸組み立て | `9lRQA` |
| 5 | Body4 - ポイント3 | 逆質問で差をつける | `WInd9` |
| 6 | Body5 - まとめ | サマリーボックス + 締めの一言 | `zfqFu` |
| 7 | CTA - フォロー | テラコッタ背景 + フォローボタン + タグライン | `M5Jq4` |

### デザイン仕様（実装済み）

| 要素 | 値 |
|------|-----|
| サイズ | 1080x1080px（Instagram標準） |
| 背景色 | `#FFF8F0`（クリーム） |
| テキスト色 | `#2D2D2D`（ダークグレー） |
| アクセントカラー | `#D4A574`（テラコッタ / 型1用） |
| フォント | Nunito（丸ゴシック代替） |
| 見出し | Nunito 700, 38-52px |
| 本文 | Nunito 400, 26-28px |

### PNG書き出し結果

```
data/creator/accounts/career_sister/templates/exports/
├── slide1_cover.png      (51KB, 2160x2160px)
├── slide2_problem.png    (73KB)
├── slide3_point1.png     (73KB)
├── slide4_point2.png     (81KB)
├── slide5_point3.png     (75KB)
├── slide6_summary.png    (75KB)
└── slide7_cta.png        (55KB)
```

## 発見事項: Pencil MCP の制約

### saveコマンドが存在しない

Pencil MCPにはsave/save-asに相当するツールがない。以下を試行:

| 試行 | 結果 |
|------|------|
| `open_document(filePath)` | アプリ内でファイルパスを関連付けるが、ディスクに保存しない |
| `batch_design(filePath=...)` | 既存ファイルへの操作用。新規ファイルに対しては「ノードが見つからない」エラー |
| AppleScript `keystroke "s"` | 「osascript is not allowed to send keystrokes」で拒否 |
| `export_nodes` | PNG/JPEG/WEBP/PDFのみ。.pen形式での保存は不可 |

**結論**: .penファイルのディスク保存にはPencilアプリ上でCmd+Sが必須。

### フォント制約

- `Hiragino Maru Gothic ProN`（macOS標準の丸ゴシック）は使用不可
- `Nunito`（Google Fonts系の丸みのあるサンセリフ）で代替成功

## 決定事項

1. **dec-2026-03-23-pencil-mcp-limitations**: Pencil MCPのsave制約を認識。export_nodesでPNG書き出しは可能。.pen保存はアプリ側操作が必要
2. **dec-2026-03-23-pencil-png-export-verified**: PNG書き出しパイプライン確認。scale:2で2160x2160px、Instagram品質十分

## アクションアイテム

- [x] act-2026-03-23-pencil-002: PNG書き出し検証 → 完了
- [ ] act-2026-03-23-pencil-001: .penファイルのディスク保存（Pencilアプリで Cmd+S） (優先度: 高)
- [ ] act-2026-03-23-pencil-003: テキスト差し替えワークフロー設計 (優先度: 中)
- [ ] 残り3色バリエーション作成（コーラル/ダスティローズ/ティール） (優先度: 中)

## 次回の議論トピック

- Pencilアプリで.penファイルを保存し、テキスト差し替えテスト
- 残り3色バリエーション（型2-4）の作成
- テキスト差し替え→PNG書き出し→Instagram API投稿の自動化ワークフロー
- career_sister用のcronスケジュール設計（投稿頻度・時間帯）

## 参考情報

- 設計方針議論: `2026-03-23_discussion-pencil-template-design.md`
- career_sisterペルソナ: `data/creator/accounts/career_sister/persona.md`
- 初回投稿5本: `data/creator/accounts/career_sister/initial_posts.md`
- Pencil MCP公式: https://www.pencil.dev/
