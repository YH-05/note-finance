---
name: article-earnings-thumbnail
description: 決算記事（category=earnings）の note.com サムネイルを自動生成するスキル。Pencilテンプレ「Thumbnail - 決算」を使って、企業ロゴ・ティッカー・決算発表日・タイトル（プレビュー/レビュー）を埋め込んだPNGを出力する。revised_draft.md 作成後にプロアクティブに使用する。
---

# article-earnings-thumbnail スキル

決算記事用の note.com サムネイル（1280×670 PNG）を自動生成する。

- **企業ロゴ**: Wikidata P154 経由で Wikipedia/Commons から取得しローカルキャッシュ（`assets/company_logos/{ticker}.png`）
- **テンプレート**: Pencil `.pen` 内に2種類のフレームを用意
  - **「Thumbnail - 決算」**（nodeId = `CAXCU`）→ `type: earnings_preview` 用。バッジ色 `#111827`（ネイビー）
  - **「Thumbnail - 決算レビュー」**（nodeId = `har1R`）→ `type: earnings_review` 用。バッジ色 `#059669`（グリーン）で視覚的に差別化
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
uv run python scripts/fetch_company_logo.py --meta-yaml {article_dir}/meta.yaml --pad-ratio 1.2
```

出力: `assets/company_logos/{TICKER}.png`（既にキャッシュ済みの場合は再利用）

### `--pad-ratio 1.2` は必須

Pencil の `fill.mode: "fit"` には極端なアスペクト比のロゴで縦方向にゴースト/ストレッチが発生するレンダリングバグがある（例: BLK 6.9:1 → 縦棒のアーティファクト）。これを回避するため、ロゴを Logo Container と同じアスペクト比 `1.2:1`（480×400）に透明パディングしてから貼り付ける。パディングはピクセル本体には触れず、上下／左右に透明余白を追加するだけなので「実質、原画像をそのまま使う」状態となる。

### ロゴ加工ポリシー

**Wikidata P154 のオリジナルロゴをそのまま貼る**（透過化処理は行わない）。Netflix のような赤背景ワードマークも、ブランド公式表現として尊重する。白背景のサムネイルに赤ブロックが入る構図は許容する。

`--remove-background` オプションは保持するが、earnings スキルのデフォルトでは使用しない。特定記事で透過版を望む場合のみ、手動でオプションを付けて実行する。

スクリプト内部のフォールバック順:
1. **SEC EDGAR 公式名**（`company_tickers.json`）で Wikipedia 検索 — 曖昧ティッカー対策（例: UNH → UnitedHealth Group）
2. ユーザー指定の `company_name` からタイトル候補生成
3. Wikipedia 検索API のトップヒット

取得失敗時はサムネイル生成をスキップし警告を返す。

## Step 3: Pencil テンプレに上書き

`meta.yaml` の `type` に応じてテンプレフレームを選択:

| type | フレーム名 | root nodeId | export_nodes 対象 |
|------|-----------|------------|------------------|
| `earnings_preview` | Thumbnail - 決算 | `CAXCU` | `CAXCU` |
| `earnings_review` | Thumbnail - 決算レビュー | `har1R` | `har1R` |

### 子ノードID対応表

| 役割 | プレビュー (`CAXCU` 配下) | レビュー (`har1R` 配下) | 更新内容 |
|------|-----|-----|---------|
| Logo Container | `f8jSq` | `9JHoC` | `fill = { type: "image", url: "file://<logo_path>", mode: "fit" }` |
| Logo Placeholder | `ZByjU` | `RUMba` | `content = ""`（LOGO文字を消す） |
| CompanyName (大) | `6g00c` | `psqPo` | `content = "{COMPANY_NAME}"`（例: `Netflix, Inc.`） |
| Ticker (小) | `CFBpG` | `8Zjbx` | `content = "{TICKER}"` |
| Subtitle | `VbtEH` | `xUTDJ` | `content = "{fiscal_quarter} {label}"` |
| EarningsDate | `mlUJ1` | `9z5hB` | `content = "発表日 {YYYY-MM-DD}"` |

### 企業名の解決

`COMPANY_NAME` は以下の優先順で決定する:

1. `meta.yaml` の `tags[]` から ASCII の企業名を抽出（例: `tags: [NFLX, Netflix, ...]` → `Netflix`）
2. 1 が取れない場合、SEC EDGAR `company_tickers.json` で公式名を解決して `_normalize_sec_name()` 相当で整形（例: `NETFLIX INC` → `Netflix, Inc.`）
3. どちらも失敗した場合は空文字列を設定（ロゴ + ティッカーのみ表示）

### 具体的な呼び出し例

> **重要**: Pencil は画像 URL をキャッシュするため、同じ `file://` パスで内容が変わった場合、古い画像がそのまま使われる。ロゴを更新した場合や透過化処理を追加した場合は、**実行ごとに一時コピーを作ってユニークなパスを渡す**こと（例: `/tmp/{TICKER}_{timestamp}.png` へコピー）。

```python
# キャッシュ回避のため /tmp にユニーク名でコピー
import shutil, time
src = Path("assets/company_logos/NFLX.png").resolve()
tmp_logo = Path(f"/tmp/NFLX_{int(time.time())}.png")
shutil.copy(src, tmp_logo)
logo_url = f"file://{tmp_logo}"

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

次回実行時のクリーンな初期状態を維持するため、使用後にテンプレをリセット。

**プレビュー版 (`CAXCU`) リセット**:
```python
mcp__pencil__batch_design(
    filePath="/Users/yukihata/Desktop/new.pen",
    operations='''
U("f8jSq",{"fill":"#FFFFFFFF"})
U("ZByjU",{"content":"LOGO"})
U("6g00c",{"content":"[Company Name]"})
U("CFBpG",{"content":"[Ticker]"})
U("VbtEH",{"content":"Q1 YYYY 決算プレビュー"})
U("mlUJ1",{"content":"発表日 YYYY-MM-DD"})
'''
)
```

**レビュー版 (`har1R`) リセット**:
```python
mcp__pencil__batch_design(
    filePath="/Users/yukihata/Desktop/new.pen",
    operations='''
U("9JHoC",{"fill":"#FFFFFFFF"})
U("RUMba",{"content":"LOGO"})
U("psqPo",{"content":"[Company Name]"})
U("8Zjbx",{"content":"[Ticker]"})
U("xUTDJ",{"content":"Q1 YYYY 決算レビュー"})
U("9z5hB",{"content":"発表日 YYYY-MM-DD"})
'''
)
```

## テンプレート情報

| 項目 | プレビュー版 | レビュー版 |
|------|-----|-----|
| Pencil ファイル | `/Users/yukihata/Desktop/new.pen` | `/Users/yukihata/Desktop/new.pen` |
| フレームノードID | `CAXCU` | `har1R` |
| フレーム名 | `Thumbnail - 決算` | `Thumbnail - 決算レビュー` |
| サイズ | 1280×670 px | 1280×670 px |
| 背景色 | `#FFFFFF`（白） | `#FFFFFF`（白） |
| バッジ色 | `#111827`（ネイビー） | `#059669`（グリーン） |
| レイアウト | 左半分ロゴ、右半分テキスト | 左半分ロゴ、右半分テキスト |

### 子ノード構造（プレビュー版 `CAXCU`）

```
CAXCU (frame, 1280×670, white bg)
├── f8jSq  (frame, Logo Container, 480×400 at x=80,y=135)
│   └── ZByjU  (text, "LOGO" placeholder)
├── tXa3j  (rect, Separator, 2×400 at x=640,y=135)
├── 6g00c  (text, CompanyName, 64px Inter Bold, at y=150)      ← 大見出し
├── CFBpG  (text, Ticker, 32px Inter Medium, at y=260)          ← 小見出し
├── VbtEH  (text, Subtitle, 44px Inter Bold, at y=320)
├── mlUJ1  (text, EarningsDate, 28px Inter Medium, at y=430)
└── uGtyD  (frame, Brand Badge ネイビー, bottom-right)
    └── 59GuP  (text "株投資ラボ")
```

### 子ノード構造（レビュー版 `har1R`）

```
har1R (frame, 1280×670, white bg)
├── 9JHoC  (frame, Logo Container, 480×400 at x=80,y=135)
│   └── RUMba  (text, "LOGO" placeholder)
├── v6wFe  (rect, Separator, 2×400 at x=640,y=135)
├── psqPo  (text, CompanyName, 64px Inter Bold, at y=150)      ← 大見出し
├── 8Zjbx  (text, Ticker, 32px Inter Medium, at y=260)          ← 小見出し
├── xUTDJ  (text, Subtitle "Q1 YYYY 決算レビュー", 44px, at y=320)
├── 9z5hB  (text, EarningsDate, 28px Inter Medium, at y=430)
└── D4lnA  (frame, Brand Badge グリーン, bottom-right)
    └── zwHOb  (text "株投資ラボ")
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
