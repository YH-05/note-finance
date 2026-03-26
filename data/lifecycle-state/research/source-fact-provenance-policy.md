# Source / Fact Provenance Policy

**Instance**: `research-neo4j`  
**Status**: active  
**Updated**: 2026-03-26

---

## 目的

`research-neo4j` では、Fact/Claim の件数を増やすことよりも、レポート本文や比較表で使える出典品質を優先する。

特に以下を防ぐ。

- `gemini-search-aggregated://...` や `file://...` を脚注代わりに使ってしまうこと
- 一次ソース不在の Fact を、確定事実として比較表や投資判断に使うこと
- Source が存在するだけで「引用可能」と誤認すること

この文書は、**一次ソースが見つからない場合の Source / Fact の扱い**を定義する。

---

## 基本方針

1. 一次ソースが見つからない場合でも、Source/Fact を即時削除はしない
2. ただし、**引用可否**と**レポート利用可否**を分けて扱う
3. 一次ソースがない Fact は「保留」または「暫定」に格下げし、重要判断には使わない
4. 一意に検証できない内容から新規 Insight を作らない
5. 比較表・投資判断・章立ての中核には、一次ソースまたは十分に信頼できる二次ソースのみを使う

---

## Source の分類

### A. Primary / Official

以下を一次ソースとして扱う。

- 企業 IR
- 企業公式 press release
- annual report / quarterly results / presentation / transcript
- 規制当局・省庁・取引所・統計当局
- 企業・当局が直接公開する filing / disclosure

運用上の扱い:

- `citation-ready`
- 比較表、本文脚注、時点確定、Insight 根拠に使用可

### B. Secondary / Reputable

以下を信頼できる二次ソースとして扱う。

- Reuters, Bloomberg などの大手報道
- sell-side report
- 業界調査会社
- 企業・規制文脈を明示的に要約した信頼できる記事

運用上の扱い:

- 一次ソースの代替ではない
- 暫定的な補助根拠として保持可
- レポート本文の補助説明には使えるが、最重要主張の唯一根拠にはしない

### C. Synthetic / Internal / Unverifiable

以下はそのままでは引用元として扱わない。

- `gemini-search-aggregated://...`
- `file://...`
- 一時メモやローカル集約ファイル
- URL があっても出典先を追跡できないもの
- publisher / published_at / 原文コンテキストが確認できないもの

運用上の扱い:

- リサーチの足がかりとして保持することは可
- 脚注・比較表・重要主張には使わない
- 一次または十分な二次ソースへ置換できるまで「未検証」とみなす

---

## 一次ソースなし時の Source ルール

### 1. 残してよい Source

次の条件を満たす場合、Source は保持してよい。

- 内容の探索起点として有用
- どの Entity / Topic に紐づくかが明確
- 後で置換候補を探す価値がある

典型例:

- `gemini-search-aggregated://src-idn-mkt-repair`
- analyst report の要約メモ
- 一時的に投入した PDF ローカルパス

### 2. 残すが、引用源としては扱わない Source

次の Source はグラフ上に存在しても、**引用可**とはみなさない。

- synthetic URL
- ローカルファイル URL
- domain / publisher / published_at が欠けたままの Source

これらは:

- Source ノードとして保持可
- `Fact.source_url` の最終形とはみなさない
- レポート脚注には出さない

### 3. 置換を優先する Source

次の条件に当てはまる Source は、P0 で置換対象とする。

- 主要企業・規制当局に紐づく
- 比較表・投資判断・章立てに使いたい内容を支えている
- Fact/Claim/Insight の根拠として頻繁に参照されている

---

## 一次ソースなし時の Fact ルール

### 1. Fact を確定事実として扱ってよい条件

以下のいずれかを満たすこと。

- 一次ソースに直接紐づく
- 信頼できる二次ソースに紐づき、内容が明示的かつ検証可能

さらに望ましい条件:

- `source_url` が実 URL
- `as_of_date` がある
- 主語となる Entity が明確

### 2. Fact を暫定保持する条件

一次ソースはないが、内容自体は有用で、後で検証できる可能性が高い場合は保持してよい。

典型例:

- 「市場シェア比較」「ARPU 比較」「tower sharing 動向」など、後で公式資料に置換できそうなもの
- sell-side や大手報道の要約から抽出されたもの

ただし扱いは制限する。

- 比較表の主要列に使わない
- 本文の断定表現に使わない
- 新規 Insight の唯一根拠に使わない

### 3. Fact をレポート利用不可とする条件

以下に当てはまるものは、Fact として残しても**レポート本文では使わない**。

- 出典が synthetic / unverifiable のみ
- 時点が不明
- どの企業・規制主体の話か曖昧
- 数値や主張の原文を再確認できない

### 4. 重要用途への利用制限

一次ソースなし Fact は、以下の用途に使わない。

- valuation 比較の根拠
- KPI 比較表の確定値
- 規制変更の確定記述
- bullish / bearish thesis の中核根拠
- Insight の結論部分

---

## レポートでの使用ルール

### 使用可

- 一次ソース付き Fact
- 一次ソース付き Claim
- 十分に信頼できる二次ソースで補足された背景説明

### 条件付き使用

- 一次ソースが未取得だが、複数の信頼できる二次ソースで整合する内容
- 背景説明・仮説候補・調査メモとしての利用

### 使用不可

- synthetic URL しかない根拠
- `as_of_date` 不明の比較数値
- 出典が追跡不能な sector-wide assertion

---

## 実務運用ルール

### P0: レポート前に必ずやること

- 主要 Source のうち synthetic URL を棚卸し
- 一次ソース置換を試行
- `Fact.source_url` を実 URL に同期
- `Fact.as_of_date` を可能な範囲で補完

### P1: 一次ソースが見つからなかった場合

- Source は残す
- ただし「引用可能な source」とは見なさない
- その Source に依存する Fact は比較表候補から除外
- 補足説明用に使う場合も断定を避ける

### P2: 恒久的に一次ソースが取りにくい場合

以下のような情報は、二次ソース前提で別扱いにする。

- 業界シェア推計
- セルサイドの forward estimate
- 競争環境のナラティブ

この場合でも:

- source tier を明示する
- official source と混ぜない
- 比較表の「実績値」と同列に置かない

---

## 推奨する実装上の扱い

現行スキーマを大きく変えずに運用する場合、最低限以下を徹底する。

### Source

- `url`: 実 URL があるなら必ず保持
- `domain`: URL 由来で補完
- `publisher`: 取得できるなら明示
- `published_at`: 実日付があるなら保持

### Fact

- `source_url`: 実 URL を優先
- `as_of_date`: `YYYY-MM-DD` で保持
- `RELATES_TO`: 主語 Entity を明確化

### Insight

- 一次ソースなし Fact/Claim のみから結論を作らない
- multi-entity / ambiguous derivation は `ABOUT` を無理に補完しない

---

## 将来の拡張候補

必要なら将来的に以下のプロパティ追加を検討する。

### Source

- `source_tier`: `primary | secondary | synthetic`
- `citation_ready`: `true | false`
- `needs_replacement`: `true | false`

### Fact

- `verification_status`: `verified | provisional | unverifiable`
- `report_usable`: `true | false`

ただし現時点では、まず URL / domain / publisher / published_at / as_of_date の充填を優先する。

---

## 判断の優先順位

1. 一次ソースがあるか
2. 実 URL で追跡できるか
3. published_at / as_of_date があるか
4. Entity が明確か
5. 比較表・判断材料に使うべきか

この順で判定し、曖昧さが残る場合は **使わない側に倒す**。
