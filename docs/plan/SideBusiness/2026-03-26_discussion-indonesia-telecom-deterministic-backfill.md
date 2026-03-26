# 議論メモ: インドネシア telecom 向け research-neo4j 決定論的バックフィル実行

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

同日の `2026-03-26_discussion-indonesia-telecom-gap-analysis.md` で、インドネシア telecom レポート着手前に research-neo4j の不足領域を診断した。

主要な不足は以下だった。

- `Source.domain` / `FROM_DOMAIN` の欠損
- `Fact.source_url` / `as_of_date` の欠損
- `Claim -> Entity` の未接続
- `Insight` の `ABOUT` 不足

これらのうち、既存グラフだけから一意に導けるものに限定して、決定論的バックフィルをコードベースに実装し、本番 DB に反映した。

## 議論のサマリー

### 実装

- `scripts/backfill_deterministic_research_gaps.py` を新規追加
- `tests/scripts/test_backfill_deterministic_research_gaps.py` を追加
- `data/lifecycle-state/research/deterministic-backfill-guide.md` を追加

CLI は以下の4 stage を持つ。

1. `domains`
2. `facts`
3. `claims`
4. `insights`

`--dry-run` と `--stage` に対応し、曖昧ケースは補完しない方針を明示した。

### 検証

- `uv run pytest tests/scripts/test_backfill_deterministic_research_gaps.py -v`
- `uv run ruff check scripts/backfill_deterministic_research_gaps.py tests/scripts/test_backfill_deterministic_research_gaps.py`

上記は通過済み。

### 実行結果

dry-run の後、本番実行を行った。

更新件数:

- `domains`: 1,277
- `facts`: 181
- `claims`: 2,065
- `insights`: 0

合計更新件数は `3,523`。

`insights` は候補 3 件すべてが曖昧であり、設計どおりスキップした。

実行後の再 dry-run では、

- `facts`: 残件 0
- `claims`: 残件 0

まで改善している。

### 残件

- `Insight` の曖昧ケース 3 件
- `domains` で `source_id = null` の候補 1 件

後者は `Source` ノード側の異常データ、またはクエリ対象の例外ケースであり、スクリプト側で `source_id` 空を除外すれば解消可能と判断した。

## 決定事項

1. インドネシア telecom レポート前補強の第一段として、既存グラフから一意に導ける欠損は決定論的バックフィルで先に埋める
2. `Insight` のように一意に導けないケースは推測補完せず、別フェーズの確認・追加調査で扱う

## アクションアイテム

- [ ] `backfill_deterministic_research_gaps.py` に `source_id` 空の domain 候補を除外するガードを追加する (優先度: 高)
- [ ] `Insight` の曖昧 3 件について、`DERIVED_FROM` 先を確認し手動で `ABOUT` を確定できるか判定する (優先度: 中)
- [ ] 補強済み research-neo4j を前提に、インドネシア telecom レポートの章立てを設計する (優先度: 中)

## 次回の議論トピック

- TowerCo / Komdigi / spectrum 論点の追加補強をどこまで先にやるか
- レポート本文を entity 比較型にするか、テーマ別論点型にするか
- synthetic URL 差し替えの残タスクをどの単位で消化するか

## 参考情報

- 直前の議論メモ: `docs/plan/SideBusiness/2026-03-26_discussion-indonesia-telecom-gap-analysis.md`
- 実装ファイル: `scripts/backfill_deterministic_research_gaps.py`
- 実行ガイド: `data/lifecycle-state/research/deterministic-backfill-guide.md`
