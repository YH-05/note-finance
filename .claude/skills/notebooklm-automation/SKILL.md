---
name: notebooklm-automation
description: |
  NotebookLM MCPサーバーおよびPlaywrightを使ったNotebookLM自動化のナレッジベース。
  チャット質問の自動送信、回答収集、ノートブック操作の実証済みパターンを提供する。
  NotebookLMへの質問投入、回答収集、バッチ処理、レポート機能の活用時にプロアクティブに使用。
  Use PROACTIVELY when automating NotebookLM interactions, sending batch questions,
  collecting Q&A responses, or any NotebookLM notebook operations.
---

# NotebookLM 自動化スキル

NotebookLMのチャット機能を自動化し、大量の質問を効率的に処理するためのナレッジベース。

## ツール選択ガイド

### MCP vs Playwright — いつ何を使うか

| 操作 | MCP (`notebooklm_*`) | Playwright 直接操作 |
|------|----------------------|---------------------|
| ノートブック一覧取得 | タイムアウトしやすい | Playwright + スクリーンショットで確認 |
| ノートブック作成 | 使用可 | 不要 |
| ソース追加 | 使用可 | 不要 |
| 単一チャット質問 | **30秒タイムアウトで失敗しやすい** | **推奨** |
| バッチチャット | **ほぼ確実に失敗** | **推奨** |
| ノートブックID取得 | MCP list → 0件になることがある | **URLから直接取得** |
| ソーステキスト取得 | `get_source_details` → **要約のみ** | **全文テキスト取得可能** |

**原則:** ソースが多い（>20個）ノートブックではMCPのchat系ツールは使わない。
Playwrightで直接UIを操作するほうが確実。

### ノートブックIDの取得方法

MCP `list_notebooks` が空を返す場合（ロード遅延が原因）:

1. Playwrightでhttps://notebooklm.google.com/ にナビゲート
2. スクリーンショットで対象ノートブックを目視確認
3. ノートブックカードをクリックして開く
4. `window.location.href` でURLからIDを抽出

```javascript
// URLからノートブックIDを取得
const url = await page.evaluate(() => window.location.href);
// https://notebooklm.google.com/notebook/{notebook_id}
```

## ソーステキスト取得パターン

MCP `get_source_details` は要約（`content_summary`）しか返さない。
Playwrightなら元ソースの**全文テキスト**が取得可能。

### 手順

1. ソースリストでソース名のボタンをクリック（詳細パネルを開く）
2. `.scroll-container` の `textContent` で全文取得

```javascript
async function getSourceText(page, sourceButtonRef) {
  // 1. ソースをクリックして詳細パネルを開く
  await page.locator(`[ref="${sourceButtonRef}"]`).click();
  await page.waitForTimeout(3000); // パネル読み込み待機

  // 2. 全文テキストを取得
  const text = await page.evaluate(() => {
    const container = document.querySelector('.scroll-container');
    return container ? container.textContent.trim() : null;
  });

  return text; // PDFの全文テキスト
}
```

### 全ソース一括取得

```javascript
async function getAllSourceTexts(page) {
  // ソースボタンの一覧を取得
  const sourceButtons = await page.$$('.source-list button[class*="source"]');
  const results = [];

  for (let i = 0; i < sourceButtons.length; i++) {
    const title = await sourceButtons[i].textContent();
    await sourceButtons[i].click();
    await page.waitForTimeout(3000);

    const text = await page.evaluate(() => {
      const c = document.querySelector('.scroll-container');
      return c ? c.textContent.trim() : null;
    });

    results.push({ index: i, title: title.trim(), textLength: text?.length || 0, text });

    // ソースリストに戻る（戻るボタンまたは別のソースをクリック）
  }

  return results;
}
```

### 注意事項

| 項目 | 詳細 |
|------|------|
| セレクタ | `.scroll-container` （ソース詳細パネル内） |
| 取得内容 | PDFから抽出されたプレーンテキスト（表・画像は失われる） |
| テキスト量 | ソースにより異なる（セルサイドレポートで約10,000文字） |
| 制限 | 一度に1ソースのみ表示可能。切替には再クリックが必要 |

---

## チャット自動化パターン

### 核心: askQuestion関数

以下のパターンが実証済み。詳細は `references/playwright-patterns.md` を参照。

**重要ポイント:**
1. **入力:** `keyboard.type()` を使う（`fill()` はAngularイベントが発火しない）
2. **送信:** `Enter` キーを押す（送信ボタンは `disabled` 属性で `click()` が失敗する）
3. **回答検出:** コピーボタン `button[aria-label="モデルの回答をクリップボードにコピー"]` の数を監視
4. **回答取得:** コピーボタンをクリック → `navigator.clipboard.readText()` でテキスト取得
5. **バッチ処理:** 3問ごとにページリロード（DOM detachment防止）

### 処理フロー

```
[ページロード] → [waitForSelector: textarea] → [3問ループ]
  ↓
  [focus → Cmd+A → Backspace → type質問 → Enter]
  ↓
  [コピーボタン数を監視（4秒間隔、最大180秒）]
  ↓
  [新しいコピーボタン検出 → 2秒待機 → 再クエリ → click → clipboard読取]
  ↓
  [次の質問 or ページリロード]
```

### 失敗回避チェックリスト

- [ ] `fill()` を使っていないか → `keyboard.type()` に変更
- [ ] 送信ボタンを `click()` していないか → `Enter` キーに変更
- [ ] 古い要素参照を使っていないか → クリック前に `$$()` で再クエリ
- [ ] 3問以上連続処理していないか → 3問ごとにリロード
- [ ] ページロード待機しているか → `waitForSelector` + `waitForTimeout(3000)`
- [ ] try/catch でDOM変更エラーを捕捉しているか

## バッチ処理戦略

### 推奨バッチサイズ

| 条件 | バッチサイズ | 理由 |
|------|------------|------|
| 安定環境 | 3問 | DOM detachment回避の実証済み上限 |
| 不安定環境 | 2問 | クラッシュ時の損失最小化 |
| テスト時 | 1問 | パターン検証用 |

### ページリロード手順

```javascript
// バッチ間のリロード
await page.goto(`https://notebooklm.google.com/notebook/${notebookId}`);
await page.waitForSelector('textarea[placeholder="入力を開始します..."]', { timeout: 30000 });
await page.waitForTimeout(3000); // ソース読み込み待機
```

### 結果の保存

質問が多い場合（>10問）は、Phase/カテゴリごとにMarkdownファイルに保存:

```
notebooklm_qa/
├── phase1_all.md   # セクションごとにQ&Aを整理
├── phase2_all.md
└── ...
```

各ファイルのフォーマット:
```markdown
# Phase N: テーマ名 — NotebookLM Q&A

## セクション名

### Q1: 質問の要約
回答テキスト（Markdown形式）
```

## 既知の問題と回避策

| 問題 | 症状 | 回避策 |
|------|------|--------|
| MCP 30秒タイムアウト | `batch_chat` 全問失敗 | Playwright直接操作に切替 |
| Angular change detection | 送信ボタンが有効にならない | `keyboard.type()` + `Enter` |
| DOM detachment | `Element is not attached to the DOM` | 3問ごとにリロード + 要素再クエリ |
| ブラウザクラッシュ | Chrome プロセス終了 | `pkill Chrome` → リロード → リトライ |
| ページロード遅延 | ソース0件表示 | `waitForSelector` + 追加待機 |
| コピーボタンの重複カウント | 1回答に2つのコピーボタン | カウント差分 > 0 で検出（2つ単位で増える） |

## 質問設計のコツ

NotebookLMの回答品質を上げるために:

- 「具体的な数字を含めて回答してください」を付加
- 1質問1トピックに絞る
- 「どのソースに基づいていますか？」でソース明示を促す
- セルサイドレポート間比較は「各レポートの見解を比較して」と指示

## 参照

- 詳細なPlaywrightコードパターン: `references/playwright-patterns.md`
