# 議論メモ: creator-enrichment browser-use CLI フォールバック追加

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-enrichment スキル実行中に Tavily API が usage limit 超過でエラーとなり、WebSearch にフォールバックしたが、WebFetch では note.com 等の JS レンダリングサイトからコンテンツ取得不可だった。browser-use CLI 2.0 が既に site-investigator スキルで使用実績があり、`~/.browser-use-env/` にインストール済みであったため、フォールバック先として追加することを検討・実装した。

## 議論のサマリー

- Tavily API リミット超過は月末に頻繁に発生する実運用上の課題
- WebFetch は静的 HTML のみ対応、note.com（Nuxt.js）/ ameblo.jp 等はコンテンツ取得不可
- browser-use CLI 2.0 の `open` + `extract` コマンドで JS レンダリング後のコンテンツ抽出が可能
- 逐次処理のため速度面の制約あり → 1サイクルあたり最大3 URL に制限

## 決定事項

1. **3段階フォールバック戦略の採用**: Tier 1=Tavily, Tier 2=WebSearch+WebFetch, Tier 3=browser-use CLI
2. **browser-use はフォールバック専用**: Tavily 利用可能時は使用しない。1サイクル最大3 URL、30秒タイムアウト

## 実装内容（完了）

SKILL.md への変更箇所:
- **Phase 0**: `0-5` browser-use CLI 可用性チェック追加、WebSearch ツール取得追加
- **Phase 2**: フォールバック戦略セクション新設、各ステップに Tier 1/2/3 フォールバックチェーン記載、browser-use CLI コマンド例・セッション管理パターン追加
- **エラーハンドリング**: browser-use 関連エラー3パターン追加
- **MUST/NEVER**: フォールバック時の行動ルール追加
- **source_type**: `browser_use` / `websearch` を追加

## アクションアイテム

- [ ] browser-use CLI フォールバックの実動作検証（note.com コンテンツ抽出テスト） (優先度: 高)

## 次回の議論トピック

- Tavily プラン升级の検討（usage limit 回避の根本対策）
- browser-use CLI の extract 精度評価（Tavily Extract との品質比較）
