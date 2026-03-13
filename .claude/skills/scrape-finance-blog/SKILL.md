---
name: scrape-finance-blog
description: 資産形成・財務ブログをスクレイピングし、テーマ別に記事を収集・分析するスキル。4フェーズ構成（モード判定→スクレイピング→テーマ別分析→結果報告）。robots.txt準拠チェック付き。
allowed-tools: Read, Bash, Grep, Glob, WebFetch
---

# scrape-finance-blog スキル

資産形成・財務ブログ（Wealth Finance Blog）から記事をスクレイピングし、
テーマ別キーワードマッチングを行い、記事リストを出力するスキル。
`scrape_wealth_blogs.py` をオーケストレートし、4フェーズで実行する。

## アーキテクチャ

```
/scrape-finance-blog (このスキル = オーケストレーター)
  |
  +-- Phase 1: モード判定・設定確認
  |     +-- プリセットファイルの存在確認
  |     +-- 対象サイト・テーマの確認
  |     +-- --dry-run / --validate-only モード判定
  |
  +-- Phase 2: スクレイピング実行
  |     +-- robots.txt 準拠チェック（--check-robots 時）
  |     +-- HTTP HEAD チェック（サイト到達確認）
  |     +-- RSSフィード取得 または サイトマップ経由バックフィル
  |     +-- レート制限遵守（WEALTH_DOMAIN_RATE_LIMITS 参照）
  |
  +-- Phase 3: テーマ別分析
  |     +-- キーワードマッチング（asset-management-themes.json 参照）
  |     +-- 日付フィルタリング（--days 引数）
  |     +-- Top-N 選出（--top-n 引数）
  |
  +-- Phase 4: 結果報告
        +-- セッションJSON出力（.tmp/ ディレクトリ）
        +-- 統計サマリー表示
        +-- 後続ワークフロー（/asset-management）への引き渡し
```

## 使用方法

```bash
# 標準実行（全サイトからRSS収集 + テーマ分析）
/scrape-finance-blog

# 特定プリセットファイルを使用
/scrape-finance-blog --presets jp

# 特定テーマのみ
/scrape-finance-blog --themes fire_wealth_building,personal_finance

# ドライラン（実際にはスクレイピングしない）
/scrape-finance-blog --dry-run

# robots.txt準拠チェックを含む
/scrape-finance-blog --check-robots

# 検証のみ（スクレイピングなし）
/scrape-finance-blog --validate-only

# 日付範囲とTop-N指定
/scrape-finance-blog --days 30 --top-n 5
```

## パラメータ一覧

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --presets | `wealth` | プリセットキー: `wealth` / `jp` / カスタムファイルパス |
| --themes | `all` | カンマ区切りテーマキー、または `all` |
| --days | `14` | 記事の取得期間（日数） |
| --top-n | `10` | テーマ別の最大記事数 |
| --dry-run | `false` | スクレイピングを実行せず、対象URLのみ表示 |
| --check-robots | `false` | robots.txt準拠チェックを実行 |
| --validate-only | `false` | プリセットのJSON構造・HTTP到達確認のみ実行 |
| --output | 自動生成 | セッションJSONの出力パス（.tmp/ 内） |

## プリセットキーとファイルのマッピング

| キー | ファイル | 説明 |
|------|---------|------|
| `wealth` | `data/config/rss-presets-wealth.json` | 英語圏の資産形成ブログ（デフォルト） |
| `jp` | `data/config/rss-presets-jp.json` | 日本語金融フィード |
| カスタムパス | 指定ファイル | `data/config/` 配下の任意JSONファイル |

## Phase 1: モード判定・設定確認

### ステップ 1.1: プリセットファイルの確認

```bash
# プリセットキーからファイルを解決
# wealth → data/config/rss-presets-wealth.json
# jp    → data/config/rss-presets-jp.json
```

プリセットファイルが存在しない場合はエラーを出力して処理中断。

### ステップ 1.2: テーマ設定の確認

```bash
# テーマ設定ファイルの確認
ls data/config/asset-management-themes.json
```

テーマファイルが存在しない場合は警告を出力し、キーワードマッチングなしで継続。

### ステップ 1.3: 実行モードの判定

| モード | 条件 | 動作 |
|--------|------|------|
| validate-only | `--validate-only` | JSON構造・HTTP到達確認のみ、スクレイピングなし |
| dry-run | `--dry-run` | 対象URL一覧表示、スクレイピングなし |
| standard | 上記以外 | 通常のスクレイピング・分析を実行 |

## Phase 2: スクレイピング実行

### ステップ 2.1: robots.txt準拠チェック（オプション）

`--check-robots` が指定された場合:

```bash
uv run python scripts/validate_rss_presets.py data/config/rss-presets-wealth.json --check-robots
```

- `BLOCKED` のフィードはスクレイピング対象から除外
- `ERROR` のフィードは警告を出力して継続

### ステップ 2.2: メインスクリプトの実行

```bash
# 基本実行
uv run python scripts/scrape_wealth_blogs.py --presets wealth --days 14

# テーマ指定
uv run python scripts/scrape_wealth_blogs.py --presets wealth --themes fire_wealth_building --days 30
```

### ステップ 2.3: エラーハンドリング

| エラー | 対処 |
|--------|------|
| ネットワーク到達不可 | 警告を出力してスキップ |
| robots.txt ブロック | スキップ（--check-robots 時のみ） |
| HTTPタイムアウト | 最大3回リトライ後スキップ |
| ペイウォール検出 | 警告を出力してスキップ |

## Phase 3: テーマ別分析

### ステップ 3.1: キーワードマッチング

`data/config/asset-management-themes.json` のキーワードを使用してタイトル・サマリーを照合。
マッチング: 大文字小文字を区別しない部分一致。

### ステップ 3.2: 日付フィルタリング

`published` フィールドが `--days` 日以内の記事のみを対象とする。

### ステップ 3.3: Top-N選出

各テーマで `--top-n` 件まで（公開日時の降順）。

## Phase 4: 結果報告

### ステップ 4.1: セッションJSON出力

```
.tmp/wealth-scrape-{YYYYMMDD}-{HHMMSS}.json
```

セッションJSON形式は `prepare_asset_management_session.py` の出力と互換。

### ステップ 4.2: 統計サマリー

```
===================================================
Scrape Finance Blog 完了
===================================================
プリセット: wealth
対象サイト: 14
取得記事数: 87
日付フィルタ後: 62
キーワードマッチ後: 23

テーマ別内訳:
  personal_finance: 8 記事
  fire_wealth_building: 6 記事
  data_driven_investing: 5 記事
  dividend_income: 4 記事
===================================================
出力: .tmp/wealth-scrape-20260313-120000.json
```

### ステップ 4.3: 後続ワークフローへの引き渡し

出力されたセッションJSONを `/asset-management` スキルに渡すことで、
note記事・Xポスト生成のワークフローを継続できる:

```
/asset-management --session .tmp/wealth-scrape-20260313-120000.json
```

## 関連リソース

| リソース | パス |
|---------|------|
| メインスクリプト | `scripts/scrape_wealth_blogs.py` |
| 検証スクリプト | `scripts/validate_rss_presets.py` |
| セッション準備スクリプト | `scripts/prepare_asset_management_session.py` |
| プリセット（Wealth） | `data/config/rss-presets-wealth.json` |
| プリセット（JP） | `data/config/rss-presets-jp.json` |
| テーマ設定 | `data/config/asset-management-themes.json` |
| スクレイピング設定 | `src/rss/config/wealth_scraping_config.py` |
| robots.txtチェッカー | `src/rss/utils/robots_checker.py` |
| 後続スキル | `.claude/skills/asset-management-workflow/SKILL.md` |

## 前提条件

1. **依存パッケージがインストール済みであること**
   ```bash
   uv sync --all-extras
   ```

2. **プリセットJSONが存在すること**
   ```bash
   ls data/config/rss-presets-wealth.json
   ls data/config/rss-presets-jp.json
   ```

3. **テーマ設定が存在すること**
   ```bash
   ls data/config/asset-management-themes.json
   ```

## エラーハンドリング

| エラーコード | 説明 | 対処 |
|------------|------|------|
| E001: プリセットファイル未検出 | `data/config/rss-presets-*.json` が存在しない | `--presets` 引数でファイルパスを明示指定 |
| E002: テーマ設定未検出 | `data/config/asset-management-themes.json` が存在しない | テーマ設定なしで全記事出力 |
| E003: スクレイピング全失敗 | 全フィードへの接続が失敗 | ネットワーク設定を確認 |
| E004: 出力ディレクトリ未存在 | `.tmp/` が存在しない | `mkdir -p .tmp/` で作成 |

## 変更履歴

### 2026-03-13: 初版作成（Issue #91）

- 4フェーズ構成の定義
- `--presets` パラメータによるプリセット切り替えサポート
- `--check-robots` による robots.txt 準拠チェック連携
- `validate_rss_presets.py` との統合
