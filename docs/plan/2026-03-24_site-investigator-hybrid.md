# site-investigator ハイブリッド化計画

## Context

site-investigator スキルは現在 **Playwright MCP** で全 5 Phase を実行しているが、
毎回のスナップショットがコンテキストに蓄積され、トークン消費が大きい（~114K tokens/タスク）。

**Playwright CLI** を調査フェーズで使うことで：
- トークン消費を約 1/4 に削減（~27K tokens）
- セッション安定性が 15-20 回 → 50+ 回に向上
- スナップショットをファイル保存 → 必要部分のみ Read

実装が見えてきたら Playwright MCP に切り替えてセレクタ検証を行うハイブリッド方式にする。

## 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `.claude/commands/site-investigator.md` | 実行手順にハイブリッド方式の説明追加 |
| `.claude/skills/site-investigator/SKILL.md` | Phase 1-5 を CLI コマンドに書き換え、検証フェーズ追加 |
| `.claude/skills/site-investigator/references/investigation-checklist.md` | JS コードブロックを CLI `eval` 形式に更新 |

**変更不要**: `scripts/generate_site_report.py`（JSON スキーマ変更なし）、`.mcp.json`

## CLI コマンドマッピング

| MCP ツール | CLI コマンド | 備考 |
|-----------|-------------|------|
| `browser_navigate` | `open <url>` / `goto <url>` | `open` は初回、`goto` は同一セッション内 |
| `browser_snapshot` | `snapshot --filename <path>` | ファイル保存（コンテキスト外） |
| `browser_take_screenshot` | `screenshot --filename <path>` | ファイル保存 |
| `browser_click` | `click <ref>` | ref はスナップショットから取得 |
| `browser_evaluate` | `eval '() => { ... }'` | 複雑な結果は `JSON.stringify()` 必須 |
| `browser_network_requests` | `network` | stdout に一覧出力 |
| `browser_handle_dialog` | `dialog-accept` / `dialog-dismiss` | |
| `browser_close` | `close` | セッション終了 |

## 実装ステップ

### Step 1: コマンドファイル更新

`.claude/commands/site-investigator.md` の実行手順を更新。
allowed-tools は現状維持（CLI は Bash 経由、MCP は検証フェーズ用に残す）。

```markdown
## 実行手順

1. SKILL.md を読み込み、5 Phase の調査プロトコルに従って実行
   - Phase 1-5: Playwright CLI (`npx -y @playwright/cli@latest`) を Bash 経由で使用
   - 検証フェーズ（オプション）: Playwright MCP でセレクタの詳細テスト
2. 調査結果を `.tmp/site-investigation-{domain}-{timestamp}.json` に保存
3. レポート生成スクリプトを実行
4. レポートを報告
```

### Step 2: SKILL.md 書き換え（メイン作業）

#### 2a. 前提条件・CLI 使用パターンのセクション追加

- `npx -y @playwright/cli@latest` で自動インストール（package.json 不要）
- 基本コマンド一覧、スナップショットの効率的な読み方を記載
- ファイル保存先: `.tmp/site-reports/{domain}/snapshots/phase{n}-{page}.md`

#### 2b. Phase 1-5 を CLI コマンドに書き換え

各 Phase の `browser_*` 呼び出しを CLI コマンドに置換。構造・目的は同じ。

Phase 1 例:
```bash
# 1. ブラウザ起動 + アクセス
npx -y @playwright/cli@latest open {url}

# 2. スクリーンショット
npx -y @playwright/cli@latest screenshot --filename .tmp/site-reports/{domain}/screenshots/phase1.png

# 3. スナップショットをファイルに保存
npx -y @playwright/cli@latest snapshot --filename .tmp/site-reports/{domain}/snapshots/phase1-home.md

# 4. Read で冒頭100行を読み、ページ種別・言語・CMS を判定

# 5. Cookie バナーがあれば click <ref>
```

#### 2c. 検証フェーズ（新規セクション）追加

Phase 5 完了後、ユーザーがセレクタ検証を求めた場合:
1. CLI セッションを `close`
2. Playwright MCP で同じページに `browser_navigate`
3. `browser_evaluate` でセレクタの querySelectorAll テスト
4. `browser_click` でページネーション動作確認

### Step 3: チェックリスト更新

`references/investigation-checklist.md` の JavaScript ブロックを CLI `eval` 形式に更新。
JS コード自体は同じ、呼び出し方法だけ変更。

```bash
# Before (MCP)
# browser_evaluate で実行

# After (CLI)
npx -y @playwright/cli@latest eval '() => {
  return JSON.stringify({
    wordpress: !!document.querySelector("meta[name=\"generator\"][content*=\"WordPress\"]"),
    ...
  });
}'
```

## 注意点

| リスク | 対策 |
|-------|------|
| `eval` のシェルエスケープ問題 | 外側はシングルクォート、内側はダブルクォート。複雑な JS は `.tmp/` にファイル保存して読み込み |
| CLI 初回の `npx` ダウンロード遅延 | 最初の `open` コマンドで自動インストール、以降は高速 |
| CLI が利用不可の場合 | MCP ツールが allowed-tools に残っているため完全フォールバック可能 |
| スナップショットファイルの上書き | ドメイン + タイムスタンプでディレクトリ分離済み |

## 検証方法

1. 適当なサイト（例: `https://techcrunch.com`）で `/site-investigator` を実行
2. `.tmp/site-reports/` にスナップショット・スクリーンショットが保存されることを確認
3. レポート（`report.md`, `report.json`）が正常に生成されることを確認
4. 検証フェーズで MCP に切り替えてセレクタテストが動くことを確認
