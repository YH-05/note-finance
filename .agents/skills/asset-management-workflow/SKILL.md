---
name: asset-management-workflow
description: 資産形成コンテンツの軽量ワークフロー。JP RSSソース収集→note記事(2000-4000字)+X投稿生成→コンプライアンスチェック→結果報告。5-10分以内完了。
allowed-tools: Read, Bash, Task
---

# 資産形成ワークフロー

JP RSSフィードから資産形成関連ニュースを収集し、初心者向けnote記事とX投稿を自動生成するワークフロースキル。

## 処理時間目標

| 指標 | 目標 | 根拠 |
|------|------|------|
| 全体合計 | 5-10分 | Project #68 成功基準 |
| Phase 1（ソース収集） | 2-3分 | Python CLI前処理 + JP RSS取得 |
| Phase 2（記事生成） | 2-4分 | asset-management-writer エージェント |
| Phase 3（コンプライアンスチェック） | 1-2分 | finance-critic-compliance + asset-management-reviser |
| Phase 4（結果報告） | 30秒以内 | 集約・表示のみ |

## アーキテクチャ

```
/asset-management "トピック名" --theme nisa (このスキル = オーケストレーター)
  |
  +-- Phase 1: ソース収集（2-3分）
  |     +-- prepare_asset_management_session.py
  |           +-- JP RSSプリセット読み込み（rss-presets-jp.json）
  |           +-- テーマ別キーワードマッチング
  |           +-- 公開日時フィルタリング
  |           +-- 上位N件選択（--top-n、デフォルト10件/テーマ）
  |           +-- セッションJSON出力（.tmp/asset-mgmt-*.json）
  |
  +-- Phase 2: 記事生成（2-4分）
  |     +-- asset-management-writer エージェント
  |           +-- ソースキュレーション（関連度スコアリング）
  |           +-- note記事の初稿（2000-4000字）
  |           +-- X投稿（280字以内）
  |           +-- curated_sources.json 出力
  |
  +-- Phase 3: コンプライアンスチェック（1-2分）
  |     +-- finance-critic-compliance エージェント（既存再利用）
  |     |     +-- 禁止表現スキャン
  |     |     +-- 免責事項確認
  |     |     +-- 投資助言的表現チェック
  |     |     +-- critic.json 出力
  |     +-- asset-management-reviser エージェント
  |           +-- compliance の critical/high のみ修正
  |           +-- revised_draft.md 出力
  |
  +-- Phase 4: 結果報告（<30秒）
        +-- 記事統計サマリー
        +-- コンプライアンススコア表示
        +-- 出力ファイル一覧
```

### finance-news-workflow との比較

| 項目 | finance-news-workflow | asset-management-workflow |
|------|----------------------|--------------------------|
| 目的 | ニュースIssue一括投稿 | 初心者向け記事生成 |
| データソース | EN RSSフィード（34件） | JP RSSフィード（rss-presets-jp.json） |
| テーマ数 | 11テーマ | 6テーマ |
| 出力 | GitHub Issue（closed） | note記事 + X投稿 |
| 処理時間 | 5分以内 | 5-10分 |
| コンプライアンス | なし | 必須（compliance critic） |
| 対象読者 | 自分用ニュースDB | 投資初心者 |

## 使用方法

```bash
# 標準実行（テーマ指定必須）
/asset-management "新NISAつみたて投資枠の活用法" --theme nisa

# オプション付き
/asset-management "インデックスファンドの選び方" --theme fund_selection --days 7

# Web検索スキップ（RSSソースのみ使用）
/asset-management "資産配分の基本" --theme asset_allocation --no-search

# ヒューマンフィードバックスキップ（全自動実行）
/asset-management "iDeCoの節税効果" --theme ideco --skip-hf
```

## パラメータ一覧

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| トピック名 | (対話入力) | 記事テーマ・タイトル案 |
| --theme | (対話選択) | nisa / fund_selection / asset_allocation / ideco / market_basics / simulation |
| --days | 14 | 過去何日分のRSSを対象とするか |
| --top-n | 10 | 各テーマの最大記事数（公開日時の新しい順） |
| --no-search | false | Web検索をスキップし、RSSソースのみ使用 |
| --skip-hf | false | ヒューマンフィードバック（確認プロンプト）をスキップ |

## Phase 1: ソース収集

### ステップ1.1: 環境確認

```bash
# テーマ設定ファイル確認
test -f data/config/asset-management-themes.json

# JP RSSプリセット確認
test -f data/config/rss-presets-jp.json
```

### ステップ1.2: Python CLI実行

```bash
# セッションファイル作成
uv run python scripts/prepare_asset_management_session.py \
    --days ${days} \
    --themes ${theme} \
    --top-n ${top_n}
```

**出力**: `.tmp/asset-mgmt-{YYYYMMDD}-{HHMMSS}.json`

**セッションファイル構造**:

```json
{
  "session_id": "asset-mgmt-20260306-120000",
  "timestamp": "2026-03-06T12:00:00+00:00",
  "themes": {
    "nisa": {
      "name_ja": "NISA制度",
      "articles": [
        {
          "url": "https://...",
          "title": "...",
          "summary": "...",
          "feed_source": "...",
          "published": "2026-03-01T09:00:00+09:00"
        }
      ],
      "keywords_used": ["NISA", "つみたて", "非課税", "積立投資"]
    }
  },
  "stats": {
    "total": 50,
    "filtered": 30,
    "matched": 12
  }
}
```

## Phase 2: 記事生成

### ステップ2.1: asset-management-writer 呼び出し

```python
Task(
    subagent_type="asset-management-writer",
    description="記事初稿とX投稿の生成",
    prompt=f"""以下のセッションデータに基づいて記事を生成してください。

## トピック
{topic_name}

## テーマ
{theme}

## セッションデータ
```json
{session_data}
```

## 出力先
- 02_edit/first_draft.md（note記事、2000-4000字）
- 02_edit/x_post.md（X投稿、280字以内）
- 02_edit/curated_sources.json（キュレーション済みソース）
"""
)
```

### 出力ファイル

| ファイル | 説明 | 制約 |
|---------|------|------|
| `02_edit/first_draft.md` | note記事の初稿 | 2000-4000字 |
| `02_edit/x_post.md` | X投稿 | 280字以内 |
| `02_edit/curated_sources.json` | キュレーション済みソース | 関連度スコア50以上のみ使用 |

## Phase 3: コンプライアンスチェック

### ステップ3.1: finance-critic-compliance 呼び出し

```python
Task(
    subagent_type="finance-critic-compliance",
    description="コンプライアンスチェック",
    prompt=f"""02_edit/first_draft.md のコンプライアンスチェックを実行してください。

critic.json の compliance セクションを生成してください。"""
)
```

### ステップ3.2: asset-management-reviser 呼び出し（compliance fail/warning 時のみ）

```python
if compliance_status in ["fail", "warning"]:
    Task(
        subagent_type="asset-management-reviser",
        description="コンプライアンス修正",
        prompt=f"""02_edit/first_draft.md と 02_edit/critic.json を読み込み、
compliance の critical/high 問題のみ修正してください。

revised_draft.md を出力してください。"""
    )
```

### 判定基準

| ステータス | 条件 | アクション |
|-----------|------|-----------|
| pass | compliance 問題なし | Phase 4 へ（修正不要） |
| warning | high 問題あり | reviser で修正後 Phase 4 へ |
| fail | critical 問題あり | reviser で修正後 Phase 4 へ |

## Phase 4: 結果報告

### サマリー出力形式

```markdown
## 資産形成記事生成完了

### 記事情報

| 項目 | 内容 |
|------|------|
| トピック | {topic_name} |
| テーマ | {theme_name_ja} |
| 文字数 | {char_count}字 |
| X投稿 | {x_char_count}字 |
| ソース数 | {source_count}件（使用: {used_count}件） |

### コンプライアンス

| 項目 | 結果 |
|------|------|
| ステータス | {compliance_status} |
| スコア | {compliance_score}/100 |
| 修正箇所 | {revision_count}件 |

### 出力ファイル

| ファイル | パス |
|---------|------|
| 最終記事 | {article_dir}/02_edit/revised_draft.md（または first_draft.md） |
| X投稿 | {article_dir}/02_edit/x_post.md |
| ソース一覧 | {article_dir}/02_edit/curated_sources.json |
| 批評結果 | {article_dir}/02_edit/critic.json |

### セッション情報

- **実行時刻**: {timestamp}
- **セッションファイル**: {session_file}
- **処理時間**: {elapsed}分
```

## テーマ一覧

| テーマキー | 日本語名 | キーワード例 | 対象ソース |
|-----------|---------|-------------|-----------|
| nisa | NISA制度 | NISA, つみたて, 非課税, 積立投資 | fsa, morningstar_jp, emaxis |
| fund_selection | ファンド選び | インデックス, ファンド, 信託報酬, eMAXIS, オルカン | emaxis, morningstar_jp |
| asset_allocation | 資産配分 | 資産配分, ポートフォリオ, 分散投資, リバランス | daiwa, morningstar_jp |
| ideco | iDeCo・企業型DC | iDeCo, 確定拠出年金, DC, 節税 | fsa, morningstar_jp |
| market_basics | 市場の基礎知識 | 株式市場, 経済指標, 為替, 債券, 金利 | jpx, boj, daiwa |
| simulation | 資産形成シミュレーション | 複利, 積立, シミュレーション, 老後資金 | fsa, daiwa |

## コンテンツルール

| 項目 | 値 |
|------|-----|
| 対象読者 | 投資初心者（beginner） |
| note記事文字数 | 2000-4000字 |
| X投稿文字数 | 280字以内 |
| 必須スニペット | `snippets/not-advice.md`（冒頭）、`snippets/investment-risk.md`（末尾） |

## 関連リソース

| リソース | パス |
|---------|------|
| Python CLI前処理 | `scripts/prepare_asset_management_session.py` |
| テーマ設定 | `data/config/asset-management-themes.json` |
| JP RSSプリセット | `data/config/rss-presets-jp.json` |
| 記事ライター | `.claude/agents/asset-management-writer.md` |
| コンプライアンス批評 | `.claude/agents/finance-critic-compliance.md` |
| 軽量リバイザー | `.claude/agents/asset-management-reviser.md` |
| 記事テンプレート | `template/asset_management/` |
| 免責事項スニペット | `snippets/not-advice.md` |
| リスク開示スニペット | `snippets/investment-risk.md` |
| NISA免責スニペット | `snippets/nisa-disclaimer.md` |
| 詳細ガイド | `.claude/skills/asset-management-workflow/guide.md` |

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| E001: テーマ設定ファイルエラー | `data/config/asset-management-themes.json` の存在・JSON形式を確認 |
| E002: JP RSSプリセットエラー | `data/config/rss-presets-jp.json` の存在・JSON形式を確認 |
| E003: Python CLI エラー | `prepare_asset_management_session.py` のログを確認 |
| E004: ソース不足 | `--days` を増やす、または `--no-search false` でWeb検索を有効化 |
| E005: 記事生成失敗 | セッションJSONの articles 件数を確認。0件ならテーマ/キーワードを見直し |
| E006: コンプライアンス fail | reviser で自動修正。修正後も fail なら手動対応 |

## 制約事項

- **RSSフィード**: JP RSSプリセットに登録済みのフィードのみ対象
- **キーワードマッチング**: 初版は単純部分文字列マッチ（形態素解析は将来対応）
- **実行頻度**: テーマあたり週1-2回を推奨
- **処理時間**: 全体5-10分（目標）
