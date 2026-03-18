---
name: notebooklm-automation
description: |
  NotebookLM CLIツール（nlm）およびPlaywrightを使ったNotebookLM自動化のナレッジベース。
  チャット質問の自動送信、回答収集、ノートブック操作の実証済みパターンを提供する。
  NotebookLMへの質問投入、回答収集、バッチ処理、レポート機能の活用時にプロアクティブに使用。
  Use PROACTIVELY when automating NotebookLM interactions, sending batch questions,
  collecting Q&A responses, or any NotebookLM notebook operations.
---

# NotebookLM 自動化スキル

NotebookLMのチャット機能を自動化し、大量の質問を効率的に処理するためのナレッジベース。

## ツール選択ガイド

### nlm CLI — 推奨ツール

`nlm` は NotebookLM のブラウザ自動化 CLI ツール。MCP サーバー経由の操作を完全に置き換える。

```bash
# エントリポイント
nlm [--session-file PATH] [--headless/--no-headless] [--json] COMMAND
```

| 操作 | CLI コマンド | 説明 |
|------|-------------|------|
| ノートブック一覧 | `nlm notebook list` | 全ノートブック一覧 |
| ノートブック作成 | `nlm notebook create TITLE` | 新規作成 |
| ノートブック要約 | `nlm notebook summary ID` | サマリー取得 |
| ソース追加（URL） | `nlm source add-url ID --url URL` | URL ソース追加 |
| ソース追加（ファイル） | `nlm source add-file ID --file PATH` | ファイルアップロード |
| ソース一覧 | `nlm source list ID` | ソース一覧 |
| 単一チャット | `nlm chat ask ID "質問"` | **推奨: 単一質問** |
| バッチチャット | `nlm chat batch ID -f questions.txt` | **推奨: バッチ処理** |
| チャット履歴 | `nlm chat history ID` | 履歴取得 |
| メモ作成 | `nlm note create ID --content "..."` | メモ作成 |
| Audio 生成 | `nlm audio generate ID` | ポッドキャスト生成 |
| Studio コンテンツ | `nlm studio generate ID --type report` | レポート等生成 |
| リサーチワークフロー | `nlm workflow research ID -q questions.txt` | バッチ + Studio |
| セッション確認 | `nlm session status` | セッション状態確認 |

### JSON 出力モード

全コマンドで `--json` フラグが使用可能:

```bash
nlm --json notebook list
nlm --json chat ask abc-123 "質問テキスト"
```

### ノートブックIDの取得方法

```bash
# JSON で ID 一覧を取得
nlm --json notebook list | jq '.[].notebook_id'
```

Playwright で直接取得する場合:
1. https://notebooklm.google.com/ にナビゲート
2. ノートブックカードをクリック
3. `window.location.href` でURLからIDを抽出

## チャット自動化パターン

### 核心: askQuestion関数

以下のパターンが `nlm chat` に内蔵済み。詳細は `references/playwright-patterns.md` を参照。

**重要ポイント:**
1. **入力:** `keyboard.type()` を使う（`fill()` はAngularイベントが発火しない）
2. **送信:** `Enter` キーを押す（送信ボタンは `disabled` 属性で `click()` が失敗する）
3. **回答検出:** コピーボタン `button[aria-label="モデルの回答をクリップボードにコピー"]` の数を監視
4. **回答取得:** コピーボタンをクリック → `navigator.clipboard.readText()` でテキスト取得
5. **バッチ処理:** 3問ごとにページリロード（DOM detachment防止）

## バッチ処理戦略

### CLI バッチコマンド

```bash
# 基本: 質問ファイルからバッチ処理
nlm chat batch <notebook_id> -f questions.txt --batch-size 3

# 結果をディレクトリに保存
nlm chat batch <notebook_id> -f questions.txt -o output/ --batch-size 3

# JSON 出力
nlm --json chat batch <notebook_id> -f questions.txt
```

### 推奨バッチサイズ

| 条件 | バッチサイズ | 理由 |
|------|------------|------|
| 安定環境 | 3問 | DOM detachment回避の実証済み上限 |
| 不安定環境 | 2問 | クラッシュ時の損失最小化 |
| テスト時 | 1問 | パターン検証用 |

### リサーチワークフロー

バッチチャット + Studio コンテンツ生成を一括実行:

```bash
nlm workflow research <notebook_id> \
  -q questions.txt \
  -o output/ \
  --batch-size 3 \
  --content-type report
```

### 結果の保存

質問が多い場合（>10問）は、Phase/カテゴリごとにMarkdownファイルに保存:

```
output/
├── batch_results_20260318_120000.json   # 全結果（JSON）
├── batch_results_20260318_120000.md     # Q&A（Markdown）
└── research_20260318_120000.json        # ワークフロー結果
```

## ソーステキスト取得パターン

`nlm source details` は要約（`content_summary`）を返す。
全文テキストが必要な場合は Playwright で直接取得:

```javascript
async function getSourceText(page, sourceButtonRef) {
  await page.locator(`[ref="${sourceButtonRef}"]`).click();
  await page.waitForTimeout(3000);
  const text = await page.evaluate(() => {
    const container = document.querySelector('.scroll-container');
    return container ? container.textContent.trim() : null;
  });
  return text;
}
```

## 既知の問題と回避策

| 問題 | 症状 | 回避策 |
|------|------|--------|
| Angular change detection | 送信ボタンが有効にならない | `keyboard.type()` + `Enter`（CLI で自動処理） |
| DOM detachment | `Element is not attached to the DOM` | 3問ごとにリロード（`--batch-size 3`） |
| ブラウザクラッシュ | Chrome プロセス終了 | `pkill Chrome` → リトライ |
| ページロード遅延 | ソース0件表示 | `waitForSelector` + 追加待機（CLI で自動処理） |

## 質問設計のコツ

NotebookLMの回答品質を上げるために:

- 「具体的な数字を含めて回答してください」を付加
- 1質問1トピックに絞る
- 「どのソースに基づいていますか？」でソース明示を促す
- セルサイドレポート間比較は「各レポートの見解を比較して」と指示

## 参照

- 詳細なPlaywrightコードパターン: `references/playwright-patterns.md`
- CLI ソースコード: `src/notebooklm/cli/`
- サービス層: `src/notebooklm/services/`
