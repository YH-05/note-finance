---
allowed-tools: mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_click, mcp__playwright__browser_evaluate, mcp__playwright__browser_network_requests, mcp__playwright__browser_handle_dialog, mcp__playwright__browser_close, Bash, Read, Write, Glob, Grep
---

# /site-investigator

対象 URL のサイト構造を調査し、スクレイピングに必要な情報をレポートする。
ハイブリッド方式: 調査は Playwright CLI（トークン効率優先）、検証は Playwright MCP。

## 引数

$ARGUMENTS — 調査対象の URL（例: `https://example.com/blog`）

## 実行手順

1. `.claude/skills/site-investigator/SKILL.md` を読み込み、5 Phase の調査プロトコルに従って実行する
   - **Phase 1-5（調査）**: Playwright CLI (`npx -y @playwright/cli@latest`) を Bash 経由で使用
   - **検証フェーズ（オプション）**: ユーザーの要求に応じて Playwright MCP ツールに切り替え、セレクタの詳細テストを実施
2. 調査結果を `.tmp/site-investigation-{domain}-{timestamp}.json` に保存する
3. レポート生成スクリプトを実行する:
   ```bash
   uv run python .claude/skills/site-investigator/scripts/generate_site_report.py \
     --input .tmp/site-investigation-{domain}-{timestamp}.json \
     --output-dir .tmp/site-reports/{domain}/
   ```
4. 生成されたレポート（`.tmp/site-reports/{domain}/report.md`）を読み込んで結果を報告する

## 注意事項

- robots.txt の Disallow ルールを尊重すること
- 調査全体で 10-20 リクエスト程度に抑えること
- 個人情報やログイン情報をレポートに含めないこと
- Playwright CLI が利用不可の場合は Playwright MCP にフォールバックすること
