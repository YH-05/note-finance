---
name: article-earnings-thumbnail
description: 決算記事（category=earnings）の note.com サムネイルを自動生成するスキル。Pencilテンプレ「Thumbnail - 決算」を使って、企業ロゴ・ティッカー・決算発表日・タイトル（プレビュー/レビュー）を埋め込んだPNGを出力する。revised_draft.md 作成後にプロアクティブに使用する。
---

# article-earnings-thumbnail スキル

決算記事用の note.com サムネイル（1280×670 PNG）を自動生成する。

- **企業ロゴ**: Wikidata P154 経由で Wikipedia/Commons から取得しローカルキャッシュ（`assets/company_logos/{ticker}.png`）
- **テンプレート**: Pencil `.pen` ファイル内の「Thumbnail - 決算」フレーム（nodeId = `CAXCU`）
- **出力**: `articles/earnings/{slug}/images/thumbnail.png`

## いつ使用するか

### プロアクティブ使用（自動発動）

`category: earnings` の記事で **revised_draft.md が作成/更新された直後**、ユーザーが明示的に要求しなくても自動で実行する。発動元の主要コマンド:

- `/article-revise` の Step 4 完了後
- `/article-critique` の finance-reviser によるリライト完了後

### 明示的な使用

- 「決算記事のサムネイルを作って」
- `/article-earnings-thumbnail @articles/earnings/{slug}/`

## 入力

| パラメータ | 必須 | 取得元 | 説明 |
|-----------|------|--------|------|
| `article_dir` | ○ | 引数 | 記事ディレクトリ（例: `articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/`） |
| `ticker` | ○ | `meta.yaml` の `symbols[0]` | ティッカーシンボル |
| `earnings_date` | ○ | `meta.yaml` の `earnings_date` | 決算発表日（`YYYY-MM-DD`） |
| `type` | ○ | `meta.yaml` の `type` | `earnings_preview` または `earnings_review` |
| `fiscal_quarter` | 推奨 | `meta.yaml` の `fiscal_quarter` | 例: `Q1 2026`。省略時は `earnings_date` から推定 |

## 処理フロー

```
Step 1: meta.yaml 読み込み・バリデーション
Step 2: ロゴ取得（Wikidata P154 → Commons → キャッシュ）
Step 3: Pencil テンプレ（CAXCU）に内容を上書き
Step 4: PNG エクスポート → articles/{dir}/images/thumbnail.png
Step 5: テンプレをプレースホルダー状態に戻す（次回のクリーンな初期状態を維持）
```

## Step 1: meta.yaml 読み込み

```python
# 必須フィールド
ticker = meta["symbols"][0]  # 例: "NFLX"
earnings_date = meta["earnings_date"]  # 例: "2026-04-22"
article_type = meta["type"]  # "earnings_preview" or "earnings_review"
fiscal_quarter = meta.get("fiscal_quarter", "")  # 例: "Q1 2026"

# サブタイトル生成
if article_type == "earnings_preview":
    label = "決算プレビュー"
elif article_type == "earnings_review":
    label = "決算レビュー"
else:
    raise ValueError(f"Unsupported type for earnings thumbnail: {article_type}")

subtitle = f"{fiscal_quarter} {label}".strip()  # "Q1 2026 決算プレビュー"
date_text = f"発表日 {earnings_date}"  # "発表日 2026-04-22"
```

バリデーション失敗時は警告を出してスキップ（記事ワークフロー自体はブロックしない）。

## Step 2: ロゴ取得

```bash
uv run python scripts/fetch_company_logo.py --meta-yaml {article_dir}/meta.yaml
```

出力: `assets/company_logos/{TICKER}.png`（既にキャッシュ済みの場合は再利用）

スクリプト内部のフォールバック順:
1. **SEC EDGAR 公式名**（`company_tickers.json`）で Wikipedia 検索 — 曖昧ティッカー対策（例: UNH → UnitedHealth Group）
2. ユーザー指定の `company_name` からタイトル候補生成
3. Wikipedia 検索API のトップヒット

取得失敗時はサムネイル生成をスキップし警告を返す。

## Step 3: Pencil テンプレに上書き

テンプレフレーム `CAXCU` の子ノードに対して以下を `mcp__pencil__batch_design` で一括更新:

| nodeId | 役割 | 更新内容 |
|--------|------|---------|
| `f8jSq` | Logo Container | `fill = { type: "image", url: "file://<logo_path>", mode: "fit" }` |
| `ZByjU` | Logo Placeholder (text) | `content = ""`（LOGO文字を消す） |
| `CFBpG` | Title (ticker big) | `content = "{TICKER}"` |
| `VbtEH` | Subtitle | `content = "{fiscal_quarter} {label}"` |
| `mlUJ1` | EarningsDate | `content = "発表日 {YYYY-MM-DD}"` |

### 具体的な呼び出し例

```python
# 絶対パスを file:// URL に変換
logo_url = f"file://{Path('assets/company_logos/NFLX.png').resolve()}"

mcp__pencil__batch_design(
    filePath="/Users/yukihata/Desktop/new.pen",
    operations=f'''
U("f8jSq",{{"fill":{{"enabled":true,"mode":"fit","type":"image","url":"{logo_url}"}}}})
U("ZByjU",{{"content":""}})
U("CFBpG",{{"content":"NFLX"}})
U("VbtEH",{{"content":"Q1 2026 決算プレビュー"}})
U("mlUJ1",{{"content":"発表日 2026-04-22"}})
'''
)
```

## Step 4: PNG エクスポート

```python
mcp__pencil__export_nodes(
    filePath="/Users/yukihata/Desktop/new.pen",
    nodeIds=["CAXCU"],
    outputDir="/tmp/earnings-thumb",
    format="png",
    scale=2  # Retina対応（実際の出力は 2560x1340）
)
# 出力: /tmp/earnings-thumb/CAXCU.png
```

エクスポート後、`{article_dir}/images/thumbnail.png` へ移動:

```bash
mkdir -p {article_dir}/images
mv /tmp/earnings-thumb/CAXCU.png {article_dir}/images/thumbnail.png
```

## Step 5: テンプレをプレースホルダー状態に戻す

次回実行時のクリーンな初期状態を維持するため、使用後にテンプレをリセット:

```python
mcp__pencil__batch_design(
    filePath="/Users/yukihata/Desktop/new.pen",
    operations='''
U("f8jSq",{"fill":"#FFFFFFFF"})
U("ZByjU",{"content":"LOGO"})
U("CFBpG",{"content":"[Ticker]"})
U("VbtEH",{"content":"Q1 YYYY 決算プレビュー"})
U("mlUJ1",{"content":"発表日 YYYY-MM-DD"})
'''
)
```

## テンプレート情報

| 項目 | 値 |
|------|-----|
| Pencil ファイル | `/Users/yukihata/Desktop/new.pen` |
| フレームノードID | `CAXCU` |
| フレーム名 | `Thumbnail - 決算` |
| サイズ | 1280×670 px |
| 背景色 | `#FFFFFF`（白） |
| レイアウト | 左半分ロゴ、右半分テキスト（縦線セパレーター中央） |

### 子ノード構造

```
CAXCU (frame, 1280×670, white bg)
├── f8jSq  (frame, Logo Container, 480×400 at x=80,y=135)
│   └── ZByjU  (text, "LOGO" placeholder)
├── tXa3j  (rect, Separator, 2×400 at x=640,y=135)
├── CFBpG  (text, Title, 88px Inter Bold, at y=180)
├── VbtEH  (text, Subtitle, 44px Inter Bold, at y=300)
├── mlUJ1  (text, EarningsDate, 28px Inter Medium, at y=420)
└── uGtyD  (frame, Brand Badge "株投資ラボ", bottom-right)
    └── 59GuP  (text inside badge)
```

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| ロゴ取得失敗（P154 無し） | 警告ログを出しサムネイル生成をスキップ。記事ワークフローは継続 |
| Pencil ファイルが開けない | `open_document(/Users/yukihata/Desktop/new.pen)` を再実行 |
| `category != earnings` | 早期リターン（スキルは earnings 専用） |
| `type` が preview/review 以外 | 警告を出しスキップ |

## 関連リソース

| リソース | パス |
|---------|------|
| ロゴ取得スクリプト | `scripts/fetch_company_logo.py` |
| ロゴキャッシュ | `assets/company_logos/{TICKER}.png` |
| Pencil テンプレ | `/Users/yukihata/Desktop/new.pen` (frame `CAXCU`) |
| 記事品質ルール | `.claude/rules/article-quality-standards.md` |
