---
description: AI投資バリューチェーン（77社・10カテゴリ）のブログ/リリースを収集し、投資視点で要約してGitHub Project #44に投稿します。
---

# AI投資バリューチェーン収集

AI企業ブログ/リリースを自動収集し、投資視点で要約してGitHub Project #44に投稿するワークフローです。

## パラメータ（ユーザーに確認）

| パラメータ | デフォルト | 説明                                         |
| ---------- | ---------- | -------------------------------------------- |
| days       | 7          | 過去何日分の記事を対象とするか               |
| categories | all        | 対象カテゴリ（ai_llm,gpu_chips,... / all）   |
| top_n      | 10         | 各カテゴリの最大記事数（公開日時の新しい順） |

## カテゴリ一覧

| カテゴリキー            | 日本語名                   | 対象企業数 |
| ----------------------- | -------------------------- | ---------- |
| ai_llm                  | AI/LLM開発                 | 11社       |
| gpu_chips               | GPU・演算チップ            | 10社       |
| semiconductor_equipment | 半導体製造装置             | 6社        |
| data_center             | データセンター・クラウド   | 7社        |
| networking              | ネットワーキング           | 2社        |
| power_energy            | 電力・エネルギー           | 7社        |
| nuclear_fusion          | 原子力・核融合             | 8社        |
| physical_ai             | フィジカルAI・ロボティクス | 9社        |
| saas                    | SaaS・AI活用ソフトウェア   | 10社       |
| ai_infra                | AI基盤・MLOps              | 7社        |

## 処理フロー

### 1. パラメータ確認

ユーザーにパラメータを確認する。指定がなければデフォルト値を使用。

### 2. `ai-research-workflow` スキルの読み込み

// turbo
`.agents/skills/ai-research-workflow/SKILL.md` を読み込み、スキルの指示に従う。

### 3. Phase 1: Python CLI前処理（3分以内）

```
├── 企業定義マスタ読み込み（77社・10カテゴリ）
├── ティアベース取得ルーティング:
│   ├── Tier 1: FeedReader → RSS対応企業（8社）
│   ├── Tier 2: RobustScraper → 汎用スクレイピング（64社）
│   └── Tier 3: CompanyScraperRegistry → 企業別アダプタ（5社）
├── 日付フィルタリング → 重複チェック → Top-N選択
└── カテゴリ別JSONファイル出力
```

// turbo

```bash
python scripts/prepare_ai_research_session.py --days {days} --categories {categories} --top-n {top_n}
```

### 4. Phase 2: 投資視点要約（6分以内）

投資視点4セクション要約生成（概要/技術的意義/市場影響/投資示唆）を実行。
市場影響度判定（low/medium/high）+ 関連銘柄タグ付けを行う。
Issue作成 + close → Project #44追加。

### 5. Phase 3: 結果集約 + 統計レポート（1分以内）

カテゴリ別統計、ティア別成功率、スクレイピング統計サマリーを出力する。

## 関連リソース

| リソース                    | パス                                           |
| --------------------------- | ---------------------------------------------- |
| ai-research-workflow スキル | `.agents/skills/ai-research-workflow/SKILL.md` |
| Python CLI前処理            | `scripts/prepare_ai_research_session.py`       |
| 企業定義マスタ              | `data/config/ai-research-companies.json`       |
| GitHub Project #44          | https://github.com/users/YH-05/projects/44     |
