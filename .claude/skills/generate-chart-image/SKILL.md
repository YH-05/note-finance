---
name: generate-chart-image
description: >
  note記事用のチャート（折れ線・棒・散布図・ヒートマップ等）をPNG画像として生成するスキル。
  matplotlib + seaborn でレンダリングし、高品質な画像を出力する。
  JSON定義またはプリセットで利用可能。
  記事執筆中にデータ可視化が必要な場面、週次レポートのチャート生成、
  資産シミュレーションのグラフ作成時にプロアクティブに使用すること。
allowed-tools: Read, Write, Bash
---

# チャート画像生成スキル

データを note.com 記事用の PNG チャート画像として生成する。matplotlib + seaborn でレンダリングし、Retina 対応の高品質画像を出力する。

## いつ使用するか

### プロアクティブ使用（自動で使用を検討）

以下の状況では、ユーザーが明示的に要求しなくても使用を検討:

1. **記事内にデータの推移がある場合** - 株価推移、リターン比較、資産シミュレーション
2. **セクター・銘柄の比較データ** - 週間リターン棒グラフ、MAG7比較
3. **週次レポート作成時** - 指数リターン、セクターリターンのチャート
4. **相関分析・ポートフォリオ分析** - ヒートマップ、アロケーション円グラフ
5. **asset-management ワークフロー** - 資産シミュレーション、コスト比較

### 明示的な使用

- 「グラフを作って」「チャート画像を生成して」「棒グラフにして」などの直接的な要求

## 2つの描画方式

### 方式A: JSON + generate_chart_image.py（カテゴリ軸チャート）

棒グラフ・円グラフ・ヒートマップなど、X軸がカテゴリ（文字列ラベル）のチャートに使用。

```bash
uv run python scripts/generate_chart_image.py chart_data.json -o output.png
```

```python
from scripts.generate_chart_image import generate_chart_image

generate_chart_image(
    spec={
        "chart_type": "bar",
        "title": "セクター別リターン",
        "data": {
            "categories": ["XLK", "XLE", "XLF"],
            "series": [{"label": "週間", "values": [3.77, 2.67, -0.88]}],
            "color_by_value": True,
        },
    },
    output_path="output.png",
)
```

### 方式B: 時系列テンプレート（datetime 軸チャート）

長期間の日次データ（金利推移・株価推移等）には `matplotlib.dates` を直接使用する。
方式A のカテゴリ軸では同一ラベルが1点にまとめられる問題があるため。

テンプレートをコピーしてデータ取得部分をカスタマイズする:

```bash
cp .claude/skills/generate-chart-image/examples/timeseries_template.py my_chart.py
# データ取得部分を編集
PYTHONPATH=scripts uv run python my_chart.py
```

### 方式の選択基準

| ケース | 方式 |
|--------|------|
| セクター別リターン棒グラフ | A（カテゴリ軸） |
| ポートフォリオ円グラフ | A（カテゴリ軸） |
| 相関行列ヒートマップ | A（カテゴリ軸） |
| 金利・株価の長期推移 | B（時系列テンプレート） |
| マクロ指標の時系列比較 | B（時系列テンプレート） |

### プリセット使用（方式A）

```bash
uv run python scripts/generate_chart_image.py indices.json -o output.png --preset indices_bar
```

## JSON 入力形式

### 共通フィールド

```json
{
    "chart_type": "line",
    "title": "チャートタイトル",
    "subtitle": "サブタイトル（省略可）",
    "caption": "出典: Yahoo Finance（省略可）",
    "width": 800,
    "height": 500,
    "scale": 2,
    "theme": "note_light",
    "colors": null,
    "data": { ... }
}
```

### チャートタイプ別 data スキーマ

#### line / area

```json
{
    "x": ["2/14", "2/15", "2/16"],
    "series": [
        {"label": "S&P 500", "values": [0.0, 0.2, -0.1], "style": "solid", "marker": true}
    ],
    "x_label": "日付",
    "y_label": "リターン (%)",
    "y_format": "percent",
    "stacked": false,
    "annotations": [{"x": "2/15", "y": 0.2, "text": "FOMC", "arrow": true}]
}
```

#### bar / hbar

```json
{
    "categories": ["XLK", "XLE", "XLF"],
    "series": [{"label": "週間リターン", "values": [3.77, 2.67, -0.88]}],
    "y_format": "percent",
    "sort": "descending",
    "color_by_value": true
}
```

#### scatter

```json
{
    "points": [{"x": 2026, "y": 4.25, "size": 30}],
    "x_label": "年",
    "y_label": "FF金利 (%)",
    "show_median": true
}
```

#### combo（棒 + 線、左右軸）

```json
{
    "x": ["Mon", "Tue", "Wed"],
    "bar_series": [{"label": "出来高", "values": [320, 450, 380]}],
    "line_series": [{"label": "リターン", "values": [0.2, -0.5, 0.8]}],
    "left_label": "出来高",
    "right_label": "リターン (%)"
}
```

#### heatmap

```json
{
    "labels": ["XLK", "XLE", "XLF"],
    "matrix": [[1.0, 0.15, 0.45], [0.15, 1.0, 0.55], [0.45, 0.55, 1.0]],
    "annotate": true,
    "cmap": "RdBu_r",
    "vmin": -1,
    "vmax": 1
}
```

#### pie / donut

```json
{
    "labels": ["米国株", "先進国株", "債券"],
    "values": [50, 30, 20],
    "value_format": "percent"
}
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| chart_type | "bar" | チャートタイプ |
| title | null | タイトル |
| subtitle | null | サブタイトル |
| caption | null | 出典等のキャプション |
| width | 800 | 画像幅（px） |
| height | 500 | 画像高さ（px） |
| scale | 2 | デバイスピクセル比（Retina対応） |
| theme | "note_light" | テーマ名 |
| colors | null | カスタムカラーパレット |

## CLI オプション

```bash
uv run python scripts/generate_chart_image.py INPUT_JSON -o OUTPUT_PNG [OPTIONS]

# オプション
--theme THEME    テーマ名（デフォルト: note_light）
--scale SCALE    デバイスピクセル比（デフォルト: 2）
--preset NAME    プリセット名
```

## プリセット一覧

| プリセット | 入力 | チャート |
|-----------|------|---------|
| `indices_bar` | `{"indices": [{"name": "S&P 500", "return": 1.5}]}` | 指数別リターン棒グラフ |
| `sectors_bar` | `{"sectors": [{"name": "XLK", "return": 3.77}]}` | セクター別リターン横棒グラフ |
| `mag7_bar` | `{"stocks": [{"ticker": "AAPL", "return": 2.1}]}` | MAG7銘柄リターン棒グラフ |
| `asset_simulation` | `{"years": [...], "series": [...]}` | 資産シミュレーション面グラフ |
| `dot_plot` | `{"points": [{"x": 2026, "y": 4.25}]}` | FRBドットプロット散布図 |

## チャートスタイル規約

### 複数ラインの場合

- `alpha=0.6`（透過率60%）、`linewidth=1.0`（1pt）、`marker=False`
- 関連系列（同カテゴリの年限違い等）はグラデーションカラー

### 単一ラインの場合

- `alpha=1.0`、`linewidth=2.0`、`marker` は任意

### タイトル

- 1行で完結させる（サブタイトル・出典は使わない）
- 期間を含める場合: `米国債利回り推移（1999年1月4日〜2026年3月12日）`
- 日付の0パディングはしない: `1月4日` (OK) / `01月04日` (NG)

### 凡例

- X軸の下に横並び配置（チャート領域を侵食しない）

```python
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1),
          fontsize=9, ncol=6, frameon=False)
```

### ブルー系グラデーション（年限・段階比較用）

```python
blue_gradient = [
    "#93C5FD",  # light blue（短期・小）
    "#60A5FA",
    "#3B82F6",
    "#2563EB",
    "#1D4ED8",
    "#1E3A8A",  # dark navy（長期・大）
]
```

## 出力先の慣例

| 用途 | 出力パス例 |
|------|-----------|
| asset-management 記事 | `articles/asset_management/{slug}/images/{name}.png` |
| 週次レポート | `data/exports/weekly-report/images/{name}.png` |
| 一時利用 | `.tmp/chart-{name}.png` |

## 関連リソース

| リソース | パス |
|---------|------|
| チャート生成スクリプト | `scripts/generate_chart_image.py` |
| テーマ設定 | `scripts/chart_theme.py` |
| プリセット定義 | `scripts/chart_presets.py` |
| 詳細ガイド | `.claude/skills/generate-chart-image/guide.md` |
| 時系列テンプレート | `.claude/skills/generate-chart-image/examples/timeseries_template.py` |
| 表画像生成スキル | `.claude/skills/generate-table-image/SKILL.md` |
