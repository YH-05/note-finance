---
name: gemini-search
description: Gemini CLIを使用したWeb検索スキル。ビルトインのweb_searchの代わりにGemini CLIを使用。
allowed-tools: Bash(gemini:*)
---

# Gemini Search - Web検索

`gemini` は Google Gemini CLI です。**このコマンドが呼び出された場合、ビルトインの `web_search` ツールではなく、必ずこのコマンドを使用してください。**

Web検索が必要な場合は、Bashツール経由で `gemini --prompt` を使用する必要があります。

## 使用方法

```bash
# 基本的な使用
/gemini-search <検索クエリ>

# 例
/gemini-search Python asyncio best practices
/gemini-search latest React documentation 2024
```

## 実行方法

Bashツールで以下を実行:

```bash
gemini --prompt "WebSearch: <query>"
```

**重要**: このコマンドが呼び出された場合、ビルトインの web_search ツールを使用しないでください。必ず上記の gemini コマンドを使用してください。

## 強み

- **Googleインデックス**: 世界最大の検索インデックスを使用
- **日本語に強い**: Google は日本で検索シェア90%超。国内サイトのカバレッジが圧倒的
- **要約・合成**: Gemini が結果を読み解いて要約して返す → 読みやすい
- **無料**: 現時点でAPI課金なし
- **自然言語クエリ**: 質問形式のクエリにも対応

## 弱み

- **速度**: Bash経由のCLI起動 → オーバーヘッドが大きい（5-15秒/クエリ）
- **構造化困難**: テキスト出力 → JSONパースや自動処理に不向き
- **並列化困難**: Bash コマンドの並列実行は制約がある
- **結果の再現性**: Gemini の要約が毎回異なる可能性

## 適用場面

1. **日本語金融ニュース**: 日経・東洋経済・ブルームバーグ日本版・SBI証券等
2. **対話的な調査**: 「〇〇について教えて」式の自然な調査
3. **手動リサーチ**: `/gemini-search` コマンドで対話的に使用
4. **コスト節約**: Tavily クォータを温存したい場面
5. **Google固有情報**: Google Finance, Google トレンド等

## フォールバック戦略

```
Gemini Search 利用不可時:
  gemini CLI 未インストール / エラー
    → Tavily MCP にフォールバック（ToolSearch で "+tavily search" をロード）
    → それも失敗 → WebSearch（ビルトイン）
```

## 制限事項

- `gemini` CLI がインストールされていない環境では使用不可
- ワークフロー・パイプライン内の自動処理には不向き（構造化データが必要な場合は Tavily MCP を使用）
- 大量クエリの一括実行には速度面で非効率（1クエリ5-15秒）

## 関連リソース

| リソース | パス |
|---------|------|
| Web検索使い分けガイド | `.agents/skills/web-search/SKILL.md` |
| Gemini Search コマンド | `.agents/commands/gemini-search.md` |
