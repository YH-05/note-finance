# ノート:ナレッジグラフ構築

Created time: 2026年3月11日 6:41
tags: memo

# 知識グラフ構築のメモ

## 要件

エージェントが知識グラフに基づき投資レポート作成、投資仮説構築、知見の創発を行うことができる

## 入力データ

### 1次データ

- 企業公表情報
    - sec filings、IR資料など
    - 財務などの数値データは今後拡充予定
- ニュース

### 2次データ

- レポート
    - セルサイド
    - 各国中央銀行
    - コンサル
    - ブログ

---

## 実装

### 1. Neo4j DB管理

- dockerコンテナでneo4jをデプロイし、その中にDBを保存

### 2. MCPサーバー/プラグイン

- neo4j MCPサーバーを使う
    - mcp-neo4j-cypher：自然言語からCypherクエリへの変換と実行
    - mcp-neo4j-data-modeling：プロパティやノード追加時に既存のスキーマを壊さないためのチェック機能として使う
    - mcp-neo4j-memory
- neo4jプラグインにAPOCを追加

### 3. メタデータの保存

`Source` ノードにすべてのメタデータを詰め込むのではなく、必要に応じて `Metadata` ノードを分離し、`Key-Value` ペアで保持する構成にすると、将来的に新しいデータソース（例：オルタナティブデータ）が増えても柔軟に対応可能。

---

## データベース構成

### 1. ソース・メタデータ層

任意の情報の起点となるノード。

- Node: `Source`
    - `source_id`: ファイルのハッシュ値（重複検知用）
    - `title`: レポート名、ニュース見出し
    - `type`: `PDF`, `Markdown`, `News`, `Filing`
    - `url` / `file_path`: 元データへのアクセスパス
    - `published_at`: 発行日（ISO 8601）
    - `author`: 発行体（証券会社名、通信社名など）

### 2. レキシカル層（Lexical Layer）

マークダウンファイルとテキストデータを管理する。元データの検証のために必要。

- **Node: `Chunk`**
    - `text`: 実際のテキスト断片
    - `chunk_index`: ソース内での順序
- **Relationship:** `(Source)-[:HAS_CHUNK]->(Chunk)`

### 3. ナレッジ抽出層（Knowledge/Claim Layer）

AIが抽出した事実や主張を正規化した形式で保持する。

- **Node: `Claim`**
    - `description`: 「2025年度の売上成長率は10%を見込む」といった自然言語の主張
    - `sentiment`: `Positive`, `Negative`, `Neutral`
    - `confidence`: LLMによる確信度（0.0〜1.0）
- **Relationship:** `(Claim)-[:EXTRACTED_FROM]->(Chunk)` （**← 根拠へのリンク**）

### 4. マスターデータ層（Master Entity Layer）

企業の基本情報などの、更新頻度が少ない静的データを管理。

- **Node: `Organization` / `Security`**
    - `ticker`: ティッカーシンボル
    - `isin`: 国際証券識別番号
    - `official_name`: 正式名称
    - `sector`: 業種分類
- **Relationship:** `(Claim)-[:ABOUT]->(Organization)`

### 5. 時間・イベント層（Temporal Layer）

時系列分析のために時間情報を保持するインデックス層。

- **Node: `FiscalPeriod` / `Date`**
    - `period`: `2024-Q3` など
- **Relationship:** `(Claim)-[:PERTAINS_TO]->(FiscalPeriod)`

---

## Neo4j DB構築ワークフロー

1. 情報ソースを収集：手動でレポジトリやGoogleドライブ、NASに保存
    1. 情報ソース種類：企業開示情報、各種レポート、ニュースなど
    2. データ形式：PDF、マークダウンファイル
2. データ形式変換：pdfのテキストデータをマークダウンに変換。全ての情報ソースの内容をマークダウンに統一する。
    1. 変換方法：IBMのDocling MCPサーバーを使用。AIはgemini cliを使用。リソース節約の観点から、claude codeでpdf→マークダウン変換は行わない。
    2. pdfと変換先のマークダウンファイルは1対1対応するように管理する。
3. チャンキング：マークダウンファイルのテキストをセクション単位でチャンキングし、チャンクノードを作成する。
4. 抽出：AIがチャンクを読み、`Claim`と`Entity` を抽出。
5. リンク：抽出された`Entity` を`Master Entity` に名寄せする。
6. DB書き込み：MCP経由でNeo4jにグラフ構造を書き込む。
