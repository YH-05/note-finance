# 資産形成コンテンツ軽量ワークフロー実装計画

## Context

日本在住の投資初心者向けに資産形成系の記事（note.com + X投稿）を発信したい。既存の `/finance-full`（20-40分）は市場データ取得・SEC開示等の重いリサーチフェーズがあり、教育コンテンツには過剰。運用会社レポートやニュースを収集→キュレーション→初心者向けに噛み砕いた記事を生成する**軽量な専用ワークフロー**（5-10分）を新設する。

**対象トピック**: NISA制度、ファンド選び、資産配分、iDeCo、市場基礎知識、資産形成シミュレーション

## ワークフロー全体像

```
/asset-management "新NISAつみたて投資枠の活用法" --theme nisa
  │
  ├── Phase 1: ソース収集（2-3分）
  │   ├── Python CLI: prepare_asset_management_session.py
  │   │   ├── JP RSS フィード取得（運用会社・金融庁・メディア）
  │   │   ├── 日付フィルタ（デフォルト14日）
  │   │   ├── テーマキーワードマッチング
  │   │   └── 出力: .tmp/asset-management-{timestamp}.json
  │   └── 補足 Web検索（Tavily、オプション）
  │
  ├── Phase 2: 記事生成（2-4分）
  │   └── asset-management-writer エージェント
  │       ├── ソースキュレーション（関連度スコアリング）
  │       ├── note.com記事生成（2000-4000字）
  │       ├── X投稿生成（280字以内）
  │       └── snippets自動挿入（not-advice, investment-risk）
  │
  ├── Phase 3: コンプライアンスチェック（1-2分）
  │   ├── finance-critic-compliance（既存エージェント再利用）
  │   └── asset-management-reviser（compliance修正のみ）
  │
  └── Phase 4: 結果報告（<30秒）
      └── 生成ファイル一覧 + 統計
```

## 設計判断

1. **コード共有**: `prepare_news_session.py` の共通関数を `scripts/session_utils.py` に抽出し、両スクリプトから import
2. **出力先**: 既存の `articles/` ディレクトリに統合（`articles/asset_management_001_nisa-guide/` 形式）
3. **コンプライアンス**: `finance-critic-compliance` エージェントをそのまま再利用（変更不要）

## 新規作成ファイル一覧（13ファイル）

### 設定ファイル（2）

| パス | 説明 |
|------|------|
| `data/config/asset-management-themes.json` | テーマ定義（6テーマ + コンテンツルール） |
| `data/config/rss-presets-jp.json` | 日本語RSSフィード定義 |

#### テーマ構造（`asset-management-themes.json`）

```json
{
  "version": "1.0",
  "themes": {
    "nisa": {
      "name_ja": "NISA制度",
      "keywords_ja": ["NISA", "つみたて", "非課税", "積立投資"],
      "target_sources": ["fsa", "morningstar_jp", "emaxis"]
    },
    "fund_selection": {
      "name_ja": "ファンド選び",
      "keywords_ja": ["インデックス", "ファンド", "信託報酬", "eMAXIS", "オルカン"],
      "target_sources": ["emaxis", "morningstar_jp"]
    },
    "asset_allocation": {
      "name_ja": "資産配分",
      "keywords_ja": ["資産配分", "ポートフォリオ", "分散投資", "リバランス"],
      "target_sources": ["daiwa", "morningstar_jp"]
    },
    "ideco": {
      "name_ja": "iDeCo・企業型DC",
      "keywords_ja": ["iDeCo", "確定拠出年金", "DC", "節税"],
      "target_sources": ["fsa", "morningstar_jp"]
    },
    "market_basics": {
      "name_ja": "市場の基礎知識",
      "keywords_ja": ["株式市場", "経済指標", "為替", "債券", "金利"],
      "target_sources": ["jpx", "boj", "daiwa"]
    },
    "simulation": {
      "name_ja": "資産形成シミュレーション",
      "keywords_ja": ["複利", "積立", "シミュレーション", "老後資金"],
      "target_sources": ["fsa", "daiwa"]
    }
  },
  "content_rules": {
    "target_audience": "beginner",
    "required_snippets": ["not-advice", "investment-risk"],
    "note_char_range": [2000, 4000],
    "x_char_limit": 280
  }
}
```

#### RSSフィード候補（`rss-presets-jp.json`）

| フィードID | ソース | URL | 確認状況 |
|-----------|--------|-----|---------|
| `jp-emaxis` | eMAXIS レポート | `https://emaxis.jp/special/rss/index.html` | RSS配信あり |
| `jp-fsa` | 金融庁 広報 | `https://www.fsa.go.jp/kouhou/rss.html` | RSS配信あり |
| `jp-boj` | 日本銀行 | `https://www.boj.or.jp/rss.htm` | RSS配信あり |
| `jp-daiwa` | 大和総研 | `https://www.dir.co.jp/rss.html` | RSS配信あり |
| `jp-morningstar` | モーニングスタージャパン | `https://www.morningstar.co.jp/news/blog/rss.html` | RSS配信あり |
| `jp-jpx` | 日本取引所グループ | `https://www.jpx.co.jp/rss/` | RSS配信あり |

> 実装前に各URLの実フィードURLを `curl` で検証する（ランディングページの場合あり）

### テンプレート（3）

| パス | 説明 |
|------|------|
| `template/asset_management/article-meta.json` | メタデータテンプレート |
| `template/asset_management/02_edit/first_draft.md` | note記事テンプレート |
| `template/asset_management/02_edit/x_post.md` | X投稿テンプレート |

#### note記事テンプレート構造

```markdown
> {snippets/not-advice.md}

# はじめに
[100-200字: この記事で分かること]

# {テーマ}を分かりやすく解説
## 基本的な仕組み
[300-600字]

## 具体的なポイント
[400-800字: 3つ程度のポイント]

## よくある質問
[200-400字: Q&A 2-3問]

# まとめ
## 今回のポイント
[箇条書き3-5点]

---
## 参考情報
{ソースURLリスト}

> {snippets/investment-risk.md}
```

### スクリプト（2）

| パス | 説明 |
|------|------|
| `scripts/session_utils.py` | 共通モジュール（`prepare_news_session.py` から抽出） |
| `scripts/prepare_asset_management_session.py` | Python CLI前処理 |

#### 共通モジュール抽出（`scripts/session_utils.py`）

`prepare_news_session.py` から以下の汎用関数・クラスを抽出:
- `filter_by_date()` — 日付フィルタリング
- `select_top_n()` — 上位N件選択
- `write_session_file()` — セッションJSON書き出し
- `_get_logger()` — ロガー初期化
- Pydanticモデル: `ArticleData`, `BlockedArticle`, `SessionStats`

`prepare_news_session.py` は抽出後 `from scripts.session_utils import ...` に変更。

#### 新規スクリプト（`prepare_asset_management_session.py`）

`session_utils.py` の共通関数を利用。主な違い:
- テーマ設定ファイル: `asset-management-themes.json` を参照
- RSSフィード: `rss-presets-jp.json` を参照（フィードIDでマッチ）
- デフォルト期間: 14日（運用会社レポートは更新頻度が低いため）
- GitHub Issue連携: 不要（重複チェックはローカルのみ）
- キーワードマッチング: `keywords_ja` による日本語テーママッチ追加
- 出力: `.tmp/asset-management-{timestamp}.json`

### エージェント（2）

| パス | 説明 |
|------|------|
| `.claude/agents/asset-management-writer.md` | 記事ライター（ソースキュレーション + note記事 + X投稿） |
| `.claude/agents/asset-management-reviser.md` | 軽量リバイザー（compliance修正のみ） |

#### asset-management-writer の設計

**入力**: セッションJSON（ソースリスト）+ トピック + テーマ
**出力**: `first_draft.md`, `x_post.md`, `curated_sources.json`

主な指示:
- 専門用語は初出時に必ず平易な説明を付与
- 信頼度別表現ルール（`finance-article-writer.md` から継承）
- 禁止表現: 「買うべき」「おすすめ」「間違いない」等
- ソースへのリンクを参考情報セクションに列挙

#### asset-management-reviser の設計

`finance-reviser.md` の軽量版。compliance の critical/high のみ修正。構造・可読性・データ正確性の修正はスキップ。

### スキル + コマンド（4）

| パス | 説明 |
|------|------|
| `.claude/skills/asset-management-workflow/SKILL.md` | オーケストレータースキル |
| `.claude/skills/asset-management-workflow/guide.md` | 詳細ガイド |
| `.claude/commands/asset-management.md` | `/asset-management` コマンド |
| `snippets/nisa-disclaimer.md` | NISA制度変更リスクの注記 |

#### コマンドパラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| トピック名 | (対話入力) | 記事テーマ |
| `--theme` | (対話選択) | nisa / fund_selection / asset_allocation / ideco / market_basics / simulation |
| `--days` | 14 | RSS遡り日数 |
| `--no-search` | false | Web検索スキップ |
| `--skip-hf` | false | ヒューマンフィードバックスキップ |

## 既存ファイルの変更（4ファイル）

| パス | 変更内容 |
|------|---------|
| `scripts/prepare_news_session.py` | 共通関数を `session_utils.py` に抽出後、import に変更 |
| `CLAUDE.md` | Slash Commands テーブルに `/asset-management` 追加 |
| `.claude/commands/new-finance-article.md` | カテゴリ選択肢に `asset_management` を追加 |
| `.claude/commands/finance-suggest-topics.md` | カテゴリ分布に `asset_management` を追加 |

> `finance-critic-compliance.md` は変更不要（そのまま再利用）

## 実装フェーズ

### Phase 1: 基盤整備

1. RSSフィードURL検証（`curl` で各URLの実フィードを確認）
2. `data/config/rss-presets-jp.json` 作成
3. `data/config/asset-management-themes.json` 作成
4. `template/asset_management/` ディレクトリ + テンプレート作成
5. `snippets/nisa-disclaimer.md` 作成

### Phase 2: 共通モジュール抽出 + 新スクリプト

1. `scripts/session_utils.py` 作成（`prepare_news_session.py` から汎用関数抽出）
2. `scripts/prepare_news_session.py` を `session_utils` から import するよう修正
3. 既存テスト通過確認（`make check-all`）
4. `scripts/prepare_asset_management_session.py` 作成（`session_utils` + キーワードマッチング）
5. テスト作成・実行
6. `make check-all`

### Phase 3: エージェント + スキル + コマンド

1. `.claude/agents/asset-management-writer.md` 作成
2. `.claude/agents/asset-management-reviser.md` 作成
3. `.claude/skills/asset-management-workflow/SKILL.md` 作成
4. `.claude/skills/asset-management-workflow/guide.md` 作成
5. `.claude/commands/asset-management.md` 作成

### Phase 4: 統合 + ドキュメント

1. 既存ファイル更新（CLAUDE.md, new-finance-article, finance-suggest-topics）
2. E2Eテスト: `/asset-management "新NISAで始める積立投資" --theme nisa`
3. 実行時間計測（目標: 5-10分）

## 検証方法

### 自動テスト

- `tests/scripts/test_prepare_asset_management_session.py`
  - `test_正常系_日付フィルタが正しく動作`
  - `test_正常系_キーワードマッチが動作`
  - `test_異常系_空フィードで空結果`
  - `test_エッジケース_全記事が期間外`

### 手動検証チェックリスト

- [ ] `/asset-management` が5-10分で完了
- [ ] note記事が2000-4000字の範囲
- [ ] X投稿が280字以内
- [ ] `snippets/not-advice.md` が記事冒頭に含まれる
- [ ] `snippets/investment-risk.md` が記事末尾に含まれる
- [ ] compliance critic が pass
- [ ] 禁止表現が含まれない
- [ ] 参考情報セクションにソースURLが列挙されている
- [ ] `make check-all` パス
