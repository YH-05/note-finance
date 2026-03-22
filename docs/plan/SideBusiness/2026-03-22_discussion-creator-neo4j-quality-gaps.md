# 議論メモ: creator-neo4j 品質ギャップ分析

**日付**: 2026-03-22
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-22-creator-neo4j-quality-gaps
**前提議論**: disc-2026-03-21-creator-neo4j-knowledge-building

## 背景・コンテキスト

前日セッションで474件のナレッジを投入し品質スコア86/100を達成。本セッションでは残りの改善ポイントを特定・分析した。

## 品質ギャップ分析結果

### 1. ジャンルバランス（最大の課題）

| ジャンル | 件数 | シェア | 目標 | ギャップ |
|---------|------|--------|------|---------|
| career | 312 | 66% | 40% | 過剰 |
| beauty-romance | 77 | 16% | 30% | -65件不足 |
| spiritual | 85 | 18% | 30% | -55件不足 |

### 2. Story の絶対数不足

| ジャンル | Story | 目標 | ギャップ |
|---------|-------|------|---------|
| career | 22 | 30 | -8 |
| beauty-romance | 10 | 20 | -10 |
| spiritual | 6 | 15 | -9 |

### 3. Source URL 品質が低い

- 全Sourceの66%がルートURLまたは短縮URL（25文字未満）
- 具体的な記事URLは34%のみ
- ファクトチェック時に元記事にたどり着けない

### 4. Topic singleton 率が高い

- career: 459/569 (81%)
- beauty-romance: 115/152 (76%)
- spiritual: 132/175 (75%)
- 1コンテンツにしか紐づかないTopicが79%。ナレッジ検索精度が低い

### 5. Service / Post / Account ノードが空

スキーマ上あるが0件。ASP案件（Service）やアカウント定義（Account）が未投入。

### 6. クロスジャンル Topic が少ない

3ジャンル共通Topicは Instagram, Threads, カルーセル の3つのみ。

## 優先度付き改善アクション

| # | アクション | 優先度 |
|---|-----------|--------|
| 1 | Source URL の具体化（ルートURL→記事URLに修正） | 高 |
| 2 | beauty-romance Story +10件 / spiritual Story +9件 追加収集 | 高 |
| 3 | Service ノード投入（ASP案件の具体データ） | 高 |
| 4 | Account ノード投入（3アカウントの定義） | 中 |
| 5 | Topic 正規化（類似統合 + 階層化） | 中 |
| 6 | beauty-romance / spiritual の Fact/Tip 各+30件 | 中 |

## インフラ注意

- creator-neo4j のデータは `/tmp/creator-neo4j-data` に一時退避中
- Docker Desktop のNASマウント問題が未解消
- NAS復旧後に `/Volumes/NeoData/neo4j-creator/data` に戻す必要あり
