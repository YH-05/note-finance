# 議論メモ: Instagram展開方針

**日付**: 2026-03-21
**参加**: ユーザー + AI

## 背景・コンテキスト

Threads自動化×マルチジャンル収益化戦略（disc-2026-03-21-threads-monetization-strategy）で3アカウント構成が決定済み。ユーザーからThreadsだけでなくInstagramにも同じジャンルで投稿し、アカウントブランドをSNS間で統一させたいという要望があった。

## 調査結果

### Instagram Graph API Content Publishing
- Meta Graph API v19.0+ で公式サポート
- Business/Creatorアカウント + Facebook Page連携必須
- 必要パーミッション: `instagram_basic`, `instagram_content_publish`, `pages_show_list`
- 投稿プロセス: Container作成→Publish の2ステップ
- Carousel（カルーセル）投稿もAPIでサポート
- Long-lived token（60日間有効、リフレッシュ可能）

### Threads vs Instagram の違い

| 項目 | Threads | Instagram |
|------|---------|-----------|
| コンテンツ形式 | テキスト中心 | 画像/リール必須 |
| 文字数 | 500字 | キャプション2,200字 |
| リンク配置 | 投稿内に直接貼れる | ストーリーズ/プロフィールのみ |
| API | Threads Publishing API (250件/24h) | Graph API Content Publishing |
| ASP導線 | コメント欄PRリンク | ストーリーズリンク・プロフィールリンク |
| 発見性 | フォロー外リーチが強い | リール/ハッシュタグ/発見タブ |

### Instagramアフィリエイトの特徴（日本市場）
- フィード投稿にリンクは貼れない（ストーリーズ/プロフィールのみ）
- プロアカウント必須
- A8.net, afb, バリューコマース等が対応済み
- ハッシュタグ戦略（ビッグ/ミドル/スモール組み合わせ）が重要
- PR表記必須

## 議論のサマリー

### Q1: コンテンツ戦略
- 選択肢: プラットフォーム別最適化 / Instagram→Threadsクロスポスト / Threads→Instagram転用
- **決定**: Threads→Instagram転用
- 理由: テキスト生成が得意な自動化システムの強みを活かす。テキスト→画像変換パイプラインを追加する方が効率的

### Q2: Instagram投稿形式
- 選択肢: カルーセル（スライド）/ リール動画 / 両方併用
- **決定**: カルーセル（スライド形式の文字入り画像）
- 理由: 転職ジャンルの定番形式。Playwright+HTML/CSSテンプレートで自動化容易。既存の/generate-table-imageと同じ技術スタック

### Q3: 展開範囲
- 選択肢: 転職のみ / 3アカウント全部 / 転職+美容×恋愛
- **決定**: まず転職アカウントのみでパイロット
- 理由: Threadsの「転職からパイロット」方針と一貫。3ブランド×2プラットフォーム同時は作業量過大

## 決定事項

1. **dec-2026-03-21-instagram-content-strategy**: Threads→Instagram転用方式を採用。テキスト→カルーセル画像変換パイプラインを構築
2. **dec-2026-03-21-instagram-post-format**: カルーセル（スライド形式）を主形式に
3. **dec-2026-03-21-instagram-pilot-scope**: まず転職アカウントのみでパイロット

## アクションアイテム

- [ ] act-015: Instagram Graph API Content Publishing の技術調査 (優先度: 高)
- [ ] act-016: カルーセル画像テンプレートデザイン・転職アカウント用 (優先度: 高)
- [ ] act-017: テキスト→カルーセル変換パイプライン実装 (優先度: 中)
- [ ] act-018: ライターエージェントにInstagramキャプション生成機能追加 (優先度: 中)
- [更新] act-007: アーキテクチャ設計のスコープにInstagram APIポスター追加

## 追加決定: ツールチェーン選定（同日）

### 調査対象
3路線を比較検討: pencil.dev / PostNitro / Playwright+HTML/CSS

### 参考事例（bubekichi氏 X投稿）
> インスタやってる人はpencil結構おすすめかも。
> ・AIっぽくない ・手作り感デザイン
> インスタで伸びる要素を押さえられる
> キーワード選定、台本作成、API投稿まで自動化してるから、作業時間ほぼゼロ。
> 毎投稿1万インプは取れてる
> .penファイルはgit管理できて、投稿のログが積み上がって、コンテキスト成長していく感じも良い。

### 決定: pencil.dev + Playwright（PostNitro不採用）

| 役割 | ツール | 理由 |
|------|--------|------|
| テンプレート設計 | pencil.dev | AIっぽくないデザイン品質、Claude Code MCP連携、無料 |
| コンテンツ生成 | pencil.dev MCP | Claude Codeから自然言語でテキスト差し替え→.penファイル生成 |
| バッチ画像書き出し | Playwright | headlessで高速PNG生成、既存インフラ、無料 |
| 投稿ログ | git | .penファイルをコミット、コンテキスト成長 |
| 投稿 | Instagram Graph API | 公式API経由のCarousel投稿 |

PostNitro不採用理由: 月$12.5〜の有料課金が必要

### 追加アクションアイテム
- [ ] act-019: pencil.dev環境セットアップ（VSCode拡張+MCP接続確認） (優先度: 高)
- [更新] act-016: テンプレートデザインをpencil.devで実施
- [更新] act-017: パイプラインをpencil.dev MCP + Playwrightベースに変更

## 次回の議論トピック

- pencil.devでの具体的なテンプレート作成（.penファイル構造の理解）
- Instagram Businessアカウント + Facebook Page の作成手順
- ストーリーズ活用戦略（ASP導線としてのストーリーズリンク自動投稿）
- .penファイル→Playwrightバッチ書き出しの技術検証

## 参考情報

- Instagram Graph API Content Publishing: https://elfsight.com/blog/instagram-graph-api-complete-developer-guide-for-2026/
- Instagram自動投稿ガイド（2026）: https://dev.to/fermainpariz/how-to-automate-instagram-posts-in-2026-without-getting-banned-3nc0
- Instagramアフィリエイト（バリューコマース）: https://www.valuecommerce.ne.jp/stepup/instagram_affiliate/
- Instagramアフィリエイトやり方（Shopify）: https://www.shopify.com/jp/blog/instagram-affiliate-marketing
- Threads API + Instagram クロスポスト: https://fedica.com/blog/auto-post-instagram-to-threads-automation/
- pencil.dev公式: https://www.pencil.dev/
- pencil.devエクスポート仕様: https://docs.pencil.dev/core-concepts/import-and-export
- pencil.dev + Claude Code MCP実例: https://dev.classmethod.jp/articles/claude-code-pencil-mcp-web-design/
- pencil.dev Skills活用: https://zenn.dev/mae616/articles/02d4425ec419ee
- bubekichi氏のX投稿: https://x.com/bubekichi/status/2034541636848673264
