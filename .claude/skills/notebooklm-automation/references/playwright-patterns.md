# Playwright コードパターン — NotebookLM自動化

## 完全なaskQuestion関数（実証済み）

```javascript
async function askQ(page, question, maxWaitMs = 180000) {
  // 1. 現在のコピーボタン数を記録
  let beforeCount = 0;
  try {
    const bb = await page.$$('button[aria-label="モデルの回答をクリップボードにコピー"]');
    beforeCount = bb.length;
  } catch(e) {}

  // 2. チャット入力欄を取得・フォーカス
  const chatInput = await page.$('textarea[placeholder="入力を開始します..."]');
  if (!chatInput) throw new Error('Chat input not found');
  await chatInput.focus();
  await page.waitForTimeout(300);

  // 3. 既存テキストをクリア（Cmd+A → Backspace）
  await page.keyboard.down('Meta');
  await page.keyboard.press('a');
  await page.keyboard.up('Meta');
  await page.keyboard.press('Backspace');
  await page.waitForTimeout(300);

  // 4. 質問を入力（keyboard.typeでAngularイベント発火）
  //    delay: 3 は安定性と速度のバランス
  await page.keyboard.type(question, { delay: 3 });
  await page.waitForTimeout(500);

  // 5. Enterキーで送信（送信ボタンclickは使わない）
  await page.keyboard.press('Enter');

  // 6. 回答完了を待機（コピーボタン数の増加で検出）
  const startTime = Date.now();
  while (Date.now() - startTime < maxWaitMs) {
    await page.waitForTimeout(4000); // 4秒間隔でチェック
    try {
      const currentButtons = await page.$$('button[aria-label="モデルの回答をクリップボードにコピー"]');
      if (currentButtons.length > beforeCount) {
        // 7. 回答完了 → 2秒待機してから要素を再クエリ
        await page.waitForTimeout(2000);
        const freshButtons = await page.$$('button[aria-label="モデルの回答をクリップボードにコピー"]');

        // 8. 最後のコピーボタンをクリック
        await freshButtons[freshButtons.length - 1].click({ timeout: 5000 });
        await page.waitForTimeout(500);

        // 9. クリップボードからテキスト取得
        const text = await page.evaluate(() => navigator.clipboard.readText());
        return { success: true, answer: text };
      }
    } catch(e) {
      // DOM変更エラーは無視して再試行
      continue;
    }
  }
  return { success: false, error: 'timeout' };
}
```

## バッチ処理テンプレート（3問バッチ）

```javascript
async (page) => {
  // ページロード待機
  await page.waitForSelector(
    'textarea[placeholder="入力を開始します..."]',
    { timeout: 30000 }
  );
  await page.waitForTimeout(3000);

  // askQ関数をここに定義（上記参照）

  const questions = [
    '質問1。具体的な数字を含めて回答してください。',
    '質問2。具体的な数字を含めて回答してください。',
    '質問3。具体的な数字を含めて回答してください。'
  ];

  const results = [];
  for (let i = 0; i < questions.length; i++) {
    try {
      const result = await askQ(page, questions[i]);
      results.push({ qNum: i + 1, ...result });
    } catch(e) {
      results.push({ qNum: i + 1, success: false, error: e.message });
    }
  }
  return results;
}
```

## ノートブックID取得パターン

```javascript
async (page) => {
  // ノートブックのURLからIDを取得
  const url = await page.evaluate(() => window.location.href);
  // URL形式: https://notebooklm.google.com/notebook/{uuid}
  const match = url.match(/notebook\/([a-f0-9-]+)/);
  return match ? match[1] : null;
}
```

## ページロード確認パターン

```javascript
async (page) => {
  // 方法1: チャット入力欄の存在確認
  const chatInput = await page.$('textarea[placeholder="入力を開始します..."]');
  if (chatInput) {
    const disabled = await chatInput.getAttribute('disabled');
    return { loaded: true, chatEnabled: disabled === null };
  }

  // 方法2: ソース数の確認
  const sourceCount = await page.$eval(
    '[class*="source-count"]',
    el => el.textContent
  ).catch(() => 'unknown');

  return { loaded: false, sourceCount };
}
```

## エラーリカバリーパターン

### DOM Detachment からの復帰

```javascript
// コピーボタンクリック時のエラーハンドリング
try {
  const buttons = await page.$$('button[aria-label="モデルの回答をクリップボードにコピー"]');
  await buttons[buttons.length - 1].click({ timeout: 5000 });
} catch(e) {
  if (e.message.includes('not attached to the DOM')) {
    // ページリロードしてリトライ
    await page.goto(notebookUrl);
    await page.waitForSelector('textarea[placeholder="入力を開始します..."]', { timeout: 30000 });
    await page.waitForTimeout(3000);
    // 質問を再送信
  }
}
```

### ブラウザクラッシュからの復帰

```bash
# Chromeプロセスを強制終了
pkill -f "Google Chrome"
# または
pkill -f chrome

# Playwright MCPが新しいブラウザを起動するのを待つ
# → browser_navigate で再アクセス
```

## ソーステキスト取得パターン（実証済み）

MCP `get_source_details` は要約のみ。Playwrightなら全文取得可能。

### 単一ソースのテキスト取得

```javascript
async (page) => {
  // 1. ソースリストからソースをクリック（詳細パネルを開く）
  //    ソースボタンのrefを指定するか、テキストで検索
  const sourceBtn = await page.$('button:has-text("ソース名の一部")');
  await sourceBtn.click();
  await page.waitForTimeout(3000); // パネル読み込み待機

  // 2. .scroll-container から全文テキストを取得
  const text = await page.evaluate(() => {
    const container = document.querySelector('.scroll-container');
    return container ? container.textContent.trim() : null;
  });

  return { length: text?.length, text };
}
```

### 全ソース一括取得

```javascript
async (page) => {
  const results = [];

  // ソースリスト内の全ボタンを取得
  // 各ソースはボタン要素でクリック可能
  const sourceItems = await page.$$('generic[cursor=pointer] > button');

  for (let i = 0; i < sourceItems.length; i++) {
    // 毎回DOMから再取得（detachment対策）
    const items = await page.$$('generic[cursor=pointer] > button');
    if (i >= items.length) break;

    const title = await items[i].textContent();
    await items[i].click();
    await page.waitForTimeout(3000);

    const text = await page.evaluate(() => {
      const c = document.querySelector('.scroll-container');
      return c ? c.textContent.trim() : null;
    });

    results.push({
      index: i,
      title: title.trim(),
      textLength: text?.length || 0,
      text
    });
  }

  return results;
}
```

### 注意事項

- `.scroll-container` はソース詳細パネル内のスクロール可能領域
- PDFから抽出されたプレーンテキストが格納（表や画像の構造は失われる）
- テキスト量はソースにより異なる（セルサイドレポートで約10,000文字）
- 一度に1ソースのみ表示可能。別ソースをクリックすると切り替わる
- 多数ソースを一括取得する場合はDOM detachmentに注意（5-10ソースごとにリロード推奨）

---

## セレクタ一覧

| 要素 | セレクタ |
|------|---------|
| チャット入力欄 | `textarea[placeholder="入力を開始します..."]` |
| 送信ボタン | `button[aria-label="送信"]` |
| コピーボタン（回答） | `button[aria-label="モデルの回答をクリップボードにコピー"]` |
| メモ保存ボタン | `button[aria-label="メッセージをメモに保存"]` |
| ソース検索 | `textarea[placeholder="ウェブで新しいソースを検索"]` |
| ノートブックタイトル | `textbox` (notebook title) |
| ソース全文テキスト | `.scroll-container` （ソース詳細パネル内） |
| ソースガイド（要約） | `.source-guide, [class*="source-guide"]` |

**注意:** これらのセレクタはNotebookLMのUI更新で変わる可能性がある。
aria-labelベースのセレクタが最も安定。

## パフォーマンス実績

| 指標 | 値 |
|------|-----|
| 1質問あたり回答時間 | 20-60秒 |
| バッチサイズ（安定） | 3問 |
| 71問の総処理時間 | 約110分 |
| ブラウザクラッシュ頻度 | 約25問に1回 |
| 成功率（リトライ含む） | 100% |
