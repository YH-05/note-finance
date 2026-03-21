---
name: alphaxiv-search
description: |
  alphaxiv MCP を使った学術論文検索のナレッジベース。ツール選択・並列制御・トークン節約のルールを提供する。
  alphaxiv MCP のどのツールをいつ使うか、並列数をどう制御するかの判断基準を集約。
  Use PROACTIVELY when alphaxiv MCP で論文検索、arXiv 論文調査、学術リサーチ、
  先行研究サーベイ、圏論・KG・金融論文の検索を行う場面。
  「論文検索」「arXiv」「alphaxiv」「先行研究」「academic search」「paper search」
  「学術調査」「research papers」と言われたら必ずこのスキルを参照すること。
allowed-tools: ToolSearch
---

# alphaxiv-search スキル

alphaxiv MCP を使った学術論文検索の効率化ガイド。
トークン消費を最小化しつつ、必要な論文情報を確実に取得するための判断基準を提供する。

## なぜこのスキルが必要か

alphaxiv MCP のツールは返却データ量に大きな差がある。
適切に使い分けないと、1回の検索セッションでコンテキストウィンドウを圧迫し、
タイムアウトや拒否が連発する。2026-03-19 に 7件並列 `get_paper_content` で
この問題が顕在化したことを受けて策定。

## ツール特性

| ツール | 返却サイズ | 速度 | 精度 | 用途 |
|--------|-----------|------|------|------|
| `embedding_similarity_search` | **小**（Abstract + メタ） | 速い | 高い（セマンティック） | **主軸** |
| `full_text_papers_search` | **大**（snippets 付き） | 遅い | 中（キーワード） | 補助・確認用 |
| `get_paper_content` | **巨大**（全文レポート） | 非常に遅い | - | 厳選した1-2件のみ |
| `agentic_paper_retrieval` | **予測不能** | 非常に遅い | 高い（マルチターン） | **使わない** |

## 選択フローチャート

```
学術論文検索が必要
    |
    +-- テーマ・概念ベースの探索？
    |   +-- YES --> embedding_similarity_search（主軸）
    |   +-- NO
    |
    +-- 特定の著者名・論文タイトル・手法名の確認？
    |   +-- YES --> full_text_papers_search（1回限り）
    |   +-- NO
    |
    +-- 論文の Method/Results の詳細が必要？
    |   +-- YES --> get_paper_content（最大2件）
    |   +-- NO
    |
    +-- 網羅的サーベイ（50件以上の候補リスト）？
    |   +-- YES --> embedding_similarity_search を複数角度で
    |   +-- NO
    |
    +-- 上記いずれでもない --> embedding_similarity_search
```

## 3フェーズ検索プロトコル

### Phase 1: 広域探索（embedding_similarity_search）

Abstract とメタデータのみ返却されるため、最もコンパクト。
1回のクエリは2-3文で概念を多角的に記述する。

**並列制限**: 最大3クエリ同時

```
embedding_similarity_search(
  query="Research on applying category theory and sheaf theory to knowledge
  graphs for emergent discovery. Papers covering functors, natural
  transformations, and Grothendieck topologies for cross-domain reasoning
  and hypothesis generation from graph databases."
)
```

**クエリ設計のコツ**:
- 1つのクエリに複数の関連概念を詰め込む（2-3文）
- 同義語・関連用語を含める（「knowledge graph」と「ontology」など）
- 応用分野も明記する（「financial analysis」「scientific discovery」など）

**Phase 1 の出力**: arXiv ID、タイトル、著者、Abstract の一覧。
ここで Abstract を読んで Phase 2 に進む論文を選別する。

### Phase 2: 補完検索（full_text_papers_search、任意）

Phase 1 で見つからなかった特定のキーワード・著者名・手法名がある場合のみ。
snippets が重いため、1回の検索セッションで最大1回に抑える。

**並列制限**: 他のツールと合わせて合計4件以下

```
full_text_papers_search(
  query="knowledge sheaves graph embedding categorical"
)
```

**使うべき場面**:
- 特定の著者名で検索したい（"Buehler graph reasoning"）
- 特定の手法名で検索したい（"Lawvere Laplacian"）
- embedding_similarity_search で見つからなかった既知の論文を確認したい

**使わない方がいい場面**:
- 広いテーマの探索（→ embedding_similarity_search の方が精度が高い）
- 曖昧なキーワード（無関係な結果が大量にヒットする）

### Phase 3: 深掘り（get_paper_content、厳選）

詳細な Claim、Method、Results の抽出が必要な場合のみ。
Phase 1-2 で収集した Abstract から「この論文の詳細が KG 投入や記事執筆に不可欠」
と判断した論文に限定する。

**並列制限**: 最大2件同時。3件以上は必ずバッチ分割。

```
get_paper_content(
  url="https://arxiv.org/abs/2503.11718"
  // fullText: false がデフォルト（構造化レポート）
)
```

**get_paper_content を呼ぶ判断基準**:
- KG に投入する Fact/Claim を正確に抽出する必要がある
- 記事で引用する具体的なデータや数値が必要
- Abstract だけでは手法の核心が判断できない

**呼ばない場合**:
- Abstract で十分に内容が把握できる（大半の論文がこれに該当）
- 論文の存在確認だけが目的
- 類似論文が複数あり、個々の詳細より全体の傾向が重要

## 並列数の制御ルール

| ツールの組み合わせ | 最大並列数 | 例 |
|-------------------|-----------|-----|
| embedding_similarity_search のみ | 3 | 3角度から同時検索 |
| embedding + full_text | 合計4 | embedding 3 + full_text 1 |
| get_paper_content のみ | 2 | 重要論文2件を同時取得 |
| get_paper_content + 他 | 合計3 | content 2 + embedding 1 |

**8件以上の並列呼び出しは絶対禁止。**
必ず4件以下のバッチに分割して逐次実行する。

## 検索結果から KG 投入への接続

検索で見つかった論文を research-neo4j に投入する場合:

```
Phase 1-2 で論文リスト取得
    |
    v
arXiv ID を抽出
    |
    v
/academic-fetch --arxiv-ids <id1> <id2> ...
    |
    v
.tmp/academic/papers.json 出力
    |
    v
/emit-graph-queue --command academic-fetch --input .tmp/academic/papers.json
    |
    v
/save-to-graph
```

## 典型的な検索セッション例

### 例1: テーマ探索（圏論 × KG）

```
# Step 1: 3角度から embedding search（並列3件）
embedding_similarity_search("Category theory applied to knowledge graphs...")
embedding_similarity_search("Sheaf theory for emergent discovery in graphs...")
embedding_similarity_search("Functorial semantics for database and ontology...")

# Step 2: Abstract を読んで選別（5-10件に絞る）
# → arXiv ID リスト作成

# Step 3: 特定著者の確認（任意、1回）
full_text_papers_search("Buehler agentic graph reasoning 2025")

# Step 4: 最重要2件の詳細取得（並列2件）
get_paper_content(url="https://arxiv.org/abs/2503.11718")
get_paper_content(url="https://arxiv.org/abs/2601.04878")

# Step 5: KG 投入
/academic-fetch --arxiv-ids 2503.11718 2601.04878 ...
/save-to-graph
```

### 例2: 特定論文の存在確認

```
# embedding search 1回で十分
embedding_similarity_search("Hypothesis generation abductive reasoning
knowledge graphs. Papers on generating plausible explanations from
graph structures using logical inference and LLMs.")

# → Abstract で内容を確認、get_paper_content は不要
```

## agentic_paper_retrieval を使わない理由

- マルチターン検索でツール内部で複数回の API 呼び出しが発生
- 返却トークン数が予測不能（数千〜数万トークンの幅）
- embedding_similarity_search を3角度で呼べば同等の網羅性を達成可能
- タイムアウトリスクが高い

## 関連リソース

| リソース | パス |
|---------|------|
| academic-fetch コマンド | `.claude/commands/academic-fetch.md` |
| academic パッケージ | `src/academic/` |
| graph-queue 生成 | `scripts/emit_graph_queue.py` |
| Neo4j 投入 | `.claude/skills/save-to-graph/SKILL.md` |
| Web 検索ガイド | `.claude/skills/web-search/SKILL.md` |
| alphaxiv 使い方メモリ | `memory/feedback_alphaxiv_usage.md` |
