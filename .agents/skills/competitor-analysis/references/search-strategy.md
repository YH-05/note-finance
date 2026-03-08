# 競合調査用検索戦略

## 検索フェーズ

参照: `.claude/resources/search-templates/competitor-content.md`（クエリテンプレート）

### Phase 1: note.com カテゴリスキャン

| 検索 | クエリ例 | 目的 |
|------|---------|------|
| 1 | `site:note.com 米国株 分析 {PERIOD}` | 米国株カテゴリの最新記事 |
| 2 | `site:note.com 投資 初心者 {PERIOD}` | 初心者向けコンテンツ |
| 3 | `site:note.com マーケットレポート {PERIOD}` | 定期レポート系 |
| 4 | `site:note.com {KEYWORD_JA} 投資` | カテゴリ指定時のキーワード検索 |

### Phase 2: トレンド交差照合

現在のトレンドキーワードで note.com を検索:
| 検索 | クエリ例 | 目的 |
|------|---------|------|
| 5 | `site:note.com {TRENDING_KEYWORD} {PERIOD}` | トレンドトピックのカバー状況 |
| 6 | `site:note.com 新NISA {PERIOD}` | NISA関連の競合状況 |

### Phase 3: エンゲージメント信号

| 検索 | クエリ例 | 目的 |
|------|---------|------|
| 7 | `note.com 金融 人気 記事 {PERIOD}` | 人気記事の傾向 |
| 8 | `note 投資 話題 {PERIOD}` | SNSでの話題性 |

### Phase 4: 他プラットフォーム比較（depth=full のみ）

| 検索 | クエリ例 | 目的 |
|------|---------|------|
| 9 | `site:zenn.dev 投資 分析 {PERIOD}` | Zenn の金融記事 |
| 10 | `site:toyokeizai.net {KEYWORD_JA} {PERIOD}` | プロメディアの記事 |
| 11-15 | 追加キーワード検索 | 深掘り |

## 検索実行ルール

1. `{PERIOD}` は `--days` パラメータに基づいて設定
2. 日本語クエリをデフォルトで使用（国内プラットフォーム中心）
3. 結果が少ない場合は期間を広げる（30日→90日）
4. 各検索結果からタイトル、著者、公開日、エンゲージメント指標を抽出
