# Indie Idea Scout パターンの note-finance 応用計画

## Context

Zenn記事「Claude Code Indie Idea Scout スキル」の3つの設計パターンを本プロジェクトに応用する:

1. **references/ による判断基準の外部化**: SKILL.md/エージェントから評価基準を分離し、独立改善可能に
2. **検索クエリの型化**: カテゴリ別クエリテンプレートで WebSearch の精度を底上げ
3. **スコアリング評価軸の外部化**: ルーブリックを外部ファイルに定義

**対象**: 案2（既存スキルへの横展開）を除く5案を実装。

## 実装順序

| 順序 | 案 | 種別 | 新規ファイル | 変更ファイル | 依存 |
|------|-----|------|------------|------------|------|
| 1 | 案4: 検索クエリテンプレート集 | 共通基盤 | 8 | 2 | なし |
| 2 | 案5: 批評エージェント基準外部化 | リファクタ | 6 | 7 | なし |
| 3 | 案1: トピック発掘スキル強化 | 改善 | 4 | 2 | 案4 |
| 4 | 案3: 競合コンテンツ分析 | 新規スキル | 4 | 0 | 案4 |
| 5 | 案6: 投資テーマリサーチ | 新規スキル | 5 | 0 | 案4 |
| **計** | | | **27** | **11** | |

### ユーザー決定事項

- **案1**: 既存の `/finance-suggest-topics` コマンドを拡張（内部で topic-discovery スキルを呼び出す）
- **案3・案6**: コマンド化しない。スキルのみで提供し、必要時にスキル名で呼び出す

---

## 案4: 検索クエリテンプレート集（共通基盤）

他の案が参照する共通リソース。`.claude/resources/search-templates/` を新設。

### 新規ファイル (8)

| ファイル | 内容 |
|---------|------|
| `.claude/resources/search-templates/README.md` | 使い方ガイド。プレースホルダ構文(`{TICKER}`, `{YYYY}`, `{KEYWORD_JA}`)、言語戦略（EN=グローバル, JA=国内）、サイト指定、フォールバック戦略 |
| `index-market.md` | 株価指数・市場全体。Bull/Bear条件別クエリ、Growth vs Value、日経/TOPIX |
| `individual-stocks.md` | 個別銘柄。決算、カタリスト、バリュエーション、日本語クエリ |
| `macro-economy.md` | マクロ経済。FOMC、CPI、雇用統計、日銀、為替 |
| `sectors.md` | セクター別。テクノロジー、エネルギー、ヘルスケア、セクターローテーション |
| `ai-tech.md` | AI・テクノロジー。GPU/半導体、クラウド/SaaS、日本AI銘柄 |
| `japan-market.md` | 日本市場特化。東証決算、円安影響、新NISA、個人投資家動向 |
| `competitor-content.md` | 競合コンテンツ調査。`site:note.com`クエリ、プラットフォーム比較 |

### 変更ファイル (2) — 参照行を1行追加のみ

- `.claude/agents/market-hypothesis-generator.md` — `参照: .claude/resources/search-templates/` を追記
- `.claude/agents/weekly-comment-indices-fetcher.md` — `参照: .claude/resources/search-templates/index-market.md` を追記

---

## 案5: 批評エージェント評価基準の外部化

5つの批評エージェントのインライン評価基準を `.claude/resources/critique-criteria/` に抽出。

### 現状の問題

- 禁止表現リストが `finance-critic-compliance.md` と `finance-article-writer.md` で重複定義
- スコアリング方式が5パターン（統一基準なし）
- 基準変更時に各エージェントを個別修正が必要

### 新規ファイル (6)

| ファイル | 抽出元エージェント | 主な内容 |
|---------|------------------|---------|
| `.claude/resources/critique-criteria/compliance-standards.md` | finance-critic-compliance | 禁止表現リスト、注意表現、必須免責事項3種、ステータス判定ロジック |
| `fact-verification.md` | finance-critic-fact | 検証対象、重要度判定（high/medium/low）、検証方法 |
| `data-accuracy.md` | finance-critic-data | 許容誤差テーブル（株価±0.01、変動率±0.1%等）、データタイプ別検証方法 |
| `structure-evaluation.md` | finance-critic-structure | 評価項目5カテゴリ、カテゴリ別構成要件、スコアリング重み付け |
| `readability-standards.md` | finance-critic-readability | ターゲット読者別基準、note.com読者特性、モバイル最適化 |
| `scoring-methodology.md` | 新規（統一化） | 統一スコアリング方式、重要度定義、グレードバンド（A-F） |

### 変更ファイル (7) — インライン基準を参照に置換

各エージェントの変更パターン: 評価基準セクションを `参照: .claude/resources/critique-criteria/{file}.md` に置換。処理フロー・出力スキーマ・ロール定義はそのまま維持。

| ファイル | 変更内容 |
|---------|---------|
| `.claude/agents/finance-critic-compliance.md` | 禁止表現・免責事項・スコアリング → 参照に置換 |
| `.claude/agents/finance-critic-fact.md` | 重要度定義・スコアリング → 参照に置換 |
| `.claude/agents/finance-critic-data.md` | 許容誤差テーブル・スコアリング → 参照に置換 |
| `.claude/agents/finance-critic-structure.md` | 評価項目・カテゴリ要件・重み付け → 参照に置換 |
| `.claude/agents/finance-critic-readability.md` | 読者基準・note.com特性・重み付け → 参照に置換 |
| `.claude/agents/finance-article-writer.md` | 禁止表現（重複部分） → compliance-standards.md 参照に置換 |
| `.claude/agents/finance-reviser.md` | 禁止表現修正テーブル → compliance-standards.md 参照を追加 |

---

## 案1: 記事トピック発掘スキル強化

現在の `finance-topic-suggester`（LLM知識のみ）に WebSearch ベースのトレンドリサーチを追加。

### 新しいフロー

```
Phase 1: トレンドリサーチ（WebSearch 8-12回、search-templates/ 使用）
Phase 2: ギャップ分析（既存 articles/ vs トレンド）
Phase 3: トピック生成・5軸評価（references/ 参照）
Phase 4: 構造化レポート出力（JSON）
```

### 新規ファイル (4)

| ファイル | 内容 |
|---------|------|
| `.claude/skills/topic-discovery/SKILL.md` | オーケストレータースキル。4フェーズ処理フロー、パラメータ（`--category`, `--count`, `--no-search`）。`--no-search` で現行動作（LLMのみ）を維持 |
| `references/scoring-rubric.md` | 5軸評価ルーブリック（timeliness, information_availability, reader_interest, feasibility, uniqueness）。各軸の High/Medium/Low バンド定義 |
| `references/reader-profile.md` | note.com 読者特性。デモグラフィック、セグメント（初心者/中級/上級）、コンテンツ嗜好、季節イベント |
| `references/search-strategy.md` | トレンドリサーチの検索戦略。クエリ配分（市場3、セクター2、AI2、日本2、コンテンツギャップ1-3）、`.claude/resources/search-templates/` 参照 |

### 変更ファイル (2)

| ファイル | 変更内容 |
|---------|---------|
| `.claude/commands/finance-suggest-topics.md` | Phase 2 で `topic-discovery` スキルを呼び出すよう変更 |
| `.claude/agents/finance-topic-suggester.md` | インライン評価基準を `references/scoring-rubric.md` 参照に置換。トピックソース定義を削除し、検索結果を入力として受け取る形に簡素化 |

---

## 案3: 競合コンテンツ分析スキル（新規）

note.com 金融カテゴリの競合状況を分析し、コンテンツ機会を発見。

### フロー

```
Phase 1: 競合記事収集（WebSearch 10-15回、competitor-content.md テンプレート使用）
Phase 2: コンテンツギャップ分析（収集記事 vs 自分の articles/）
Phase 3: 差別化スコアリング（gap-analysis-framework.md 参照）
Phase 4: 機会レポート出力（.tmp/competitor-analysis/{timestamp}.md）
```

### 新規ファイル (4)

| ファイル | 内容 |
|---------|------|
| `.claude/skills/competitor-analysis/SKILL.md` | オーケストレータースキル。パラメータ: `--category`, `--depth`(quick/full), `--days` |
| `references/competitor-sources.md` | 注目クリエイター/メディア一覧。note.com 金融カテゴリ、Zenn/Qiita、プロメディア。四半期ごと更新推奨 |
| `references/gap-analysis-framework.md` | ギャップ種別（トピック/深さ/鮮度/読者レベル/フォーマット）、機会スコアリング（5軸×1-5点）、優先度マトリクス |
| `references/search-strategy.md` | 競合調査用検索戦略。note.comカテゴリスキャン、トレンド交差照合、エンゲージメント信号、`.claude/resources/search-templates/competitor-content.md` 参照 |

### 変更ファイル: なし

---

## 案6: 投資テーマ深掘りリサーチスキル（新規）

特定の投資テーマについてマルチソースで深掘りリサーチし、記事素材を集める。

### フロー

```
Phase 1: マルチソース検索（WebSearch + RSS MCP + Reddit MCP + SEC Edgar MCP）
Phase 2: ファクト整理（時系列、数値データ、専門家見解）
Phase 3: 論点抽出（ブル/ベア/ニュートラル）
Phase 4: リサーチノート出力
```

### 新規ファイル (5)

| ファイル | 内容 |
|---------|------|
| `.claude/skills/investment-research/SKILL.md` | オーケストレータースキル。パラメータ: `--theme`(必須), `--depth`(quick/standard/deep), `--language`(en/ja/both)。MCP は ToolSearch でロード、利用不可時はフォールバック |
| `references/search-strategy.md` | テーマ種別ごとのソース優先順位。個別銘柄: SEC>WebSearch>RSS>Reddit、マクロ: WebSearch>RSS>Reddit。深さ別クエリ予算（quick:5-8, standard:12-18, deep:20-30） |
| `references/source-reliability.md` | ソース信頼度4段階。Tier1: SEC/中銀/政府統計、Tier2: Bloomberg/Reuters/日経、Tier3: 業界誌/プレスリリース、Tier4: Reddit/SNS。事実主張はTier1-2必須 |
| `references/research-depth-criteria.md` | 深掘り判断基準。3+信頼ソースで確認=quick十分、ブル/ベアが証拠付き=standard十分、コア主張にTier1×2=deep要件。収穫逓減シグナル定義 |
| `references/output-format.md` | リサーチノートテンプレート。エグゼクティブサマリー→背景→ファクト整理→論点分析（ブル/ベア/ニュートラル）→データソース一覧→記事化可能性 |

### 変更ファイル: なし

---

## ディレクトリ構造（完成形）

```
.claude/
├── resources/                          # 【案4・5で新設】
│   ├── search-templates/               # 【案4】検索クエリテンプレート集
│   │   ├── README.md
│   │   ├── index-market.md
│   │   ├── individual-stocks.md
│   │   ├── macro-economy.md
│   │   ├── sectors.md
│   │   ├── ai-tech.md
│   │   ├── japan-market.md
│   │   └── competitor-content.md
│   └── critique-criteria/              # 【案5】批評評価基準
│       ├── compliance-standards.md
│       ├── fact-verification.md
│       ├── data-accuracy.md
│       ├── structure-evaluation.md
│       ├── readability-standards.md
│       └── scoring-methodology.md
├── skills/
│   ├── topic-discovery/                # 【案1】トピック発掘
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── scoring-rubric.md
│   │       ├── reader-profile.md
│   │       └── search-strategy.md
│   ├── competitor-analysis/            # 【案3】競合分析
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── competitor-sources.md
│   │       ├── gap-analysis-framework.md
│   │       └── search-strategy.md
│   └── investment-research/            # 【案6】投資テーマリサーチ
│       ├── SKILL.md
│       └── references/
│           ├── search-strategy.md
│           ├── source-reliability.md
│           ├── research-depth-criteria.md
│           └── output-format.md
└── agents/                             # 【案5で変更】
    ├── finance-critic-*.md             # 評価基準 → 参照に置換
    ├── finance-article-writer.md       # 禁止表現 → 参照に置換
    └── finance-reviser.md              # 修正テーブル → 参照追加
```

## 設計原則

1. **references/ は判断基準、SKILL.md/agent は処理フロー**: 何を評価するかと処理手順を分離
2. **Single Source of Truth**: 禁止表現等の重複定義を1ファイルに統合（compliance-standards.md → 3箇所から参照）
3. **漸進的改善**: references/ を更新するだけで全消費者の品質が向上
4. **Graceful Degradation**: `--no-search` モード、MCP不在時フォールバック
5. **既存動作の維持**: エージェントの入出力スキーマは変更しない

## 検証方法

### 案4: 検索クエリテンプレート集
- テンプレートファイルが正しいMarkdown構文で記述されているか確認
- README.md のプレースホルダ構文が各テンプレートで一貫しているか確認

### 案5: 批評エージェント基準外部化
- `/finance-edit` で記事を批評し、外部化前と同等の評価結果が得られるか確認
- `compliance-standards.md` の禁止表現が `finance-critic-compliance`, `finance-article-writer`, `finance-reviser` 全てから正しく参照されるか確認

### 案1: トピック発掘スキル強化
- `/finance-suggest-topics` を実行し、WebSearch ベースのトレンド情報が提案に反映されるか確認
- `--no-search` オプションで従来動作（LLMのみ）が維持されるか確認

### 案3: 競合コンテンツ分析
- スキル `competitor-analysis` を呼び出し、note.com の競合記事が収集されるか確認
- ギャップ分析レポートが `.tmp/competitor-analysis/` に出力されるか確認

### 案6: 投資テーマリサーチ
- スキル `investment-research` を特定テーマ（例: "NVIDIA AI需要"）で呼び出す
- マルチソース（WebSearch + RSS）からのファクト収集とリサーチノート出力を確認
- `--depth quick` と `--depth deep` で検索量が異なることを確認
