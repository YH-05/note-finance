# generate-chart-image スキル実装計画

## Context

note記事用のチャート（折れ線・棒・散布図等）をPNG画像として生成するスキルが存在しない。既存の `generate-table-image` スキル（テーブル→PNG）はあるが、データ可視化チャートは未対応。記事ドラフトでは「推移グラフ」「セクター別リターン棒グラフ」「ドットプロット」等のニーズが複数確認された。matplotlib + seaborn でレンダリングし、Plotly は将来拡張としてスコープ外とする（理由: kaleido バイナリの macOS ARM 互換性リスク、matplotlib で全チャートタイプをカバー可能）。

## ファイル構成

### 新規作成

| ファイル | 内容 |
|---------|------|
| `.claude/skills/generate-chart-image/SKILL.md` | スキル定義 |
| `scripts/generate_chart_image.py` | メインスクリプト（~500行） |
| `scripts/chart_theme.py` | note.com 統一テーマ設定（~120行） |
| `scripts/chart_presets.py` | プリセットチャート定義（~150行） |
| `tests/scripts/test_generate_chart_image.py` | ユニットテスト |
| `tests/scripts/test_chart_theme.py` | テーマテスト |

### 変更

| ファイル | 変更内容 |
|---------|---------|
| `pyproject.toml` | `chart` optional dependency 追加 |

## 依存関係（`pyproject.toml`）

```toml
[project.optional-dependencies]
# 既存グループの後に追加
chart = ["matplotlib>=3.9.0", "seaborn>=0.13.0"]
```

- `pillow` は matplotlib の transitive dependency で自動インストール
- Plotly/kaleido は不要（matplotlib + seaborn で全チャートタイプをカバー）

## チャートテーマ設計 (`scripts/chart_theme.py`)

```python
@dataclass(frozen=True)
class ChartTheme:
    name: str
    font_family: str         # "Noto Sans JP"
    title_size: int          # 16
    label_size: int          # 12
    tick_size: int           # 10
    caption_size: int        # 9
    background_color: str    # "#FFFFFF"
    text_color: str          # "#333333"
    grid_color: str          # "#E8E8E8"
    grid_alpha: float        # 0.5
    palette: list[str]       # 8色パレット
    positive_color: str      # "#2563EB"
    negative_color: str      # "#DC2626"
    spine_visible: bool      # False
```

### テーマカラーパレット（`note_light`）

| # | 色 | 用途 |
|---|-----|------|
| 1 | `#2563EB` (blue) | Primary / Positive |
| 2 | `#DC2626` (red) | Negative |
| 3 | `#059669` (green) | Series 3 |
| 4 | `#D97706` (amber) | Series 4 |
| 5 | `#7C3AED` (purple) | Series 5 |
| 6 | `#DB2777` (pink) | Series 6 |
| 7 | `#0891B2` (cyan) | Series 7 |
| 8 | `#65A30D` (lime) | Series 8 |

`#2563EB` は generate-table-image の `theme_color` デフォルトと統一。

## JSON 入力スキーマ

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
  "x_label": "年", "y_label": "FF金利 (%)",
  "show_median": true
}
```

#### combo（棒 + 線、左右軸）

```json
{
  "x": ["Mon", "Tue", "Wed"],
  "bar_series": [{"label": "出来高", "values": [320, 450, 380], "axis": "left"}],
  "line_series": [{"label": "リターン", "values": [0.2, -0.5, 0.8], "axis": "right"}],
  "left_label": "出来高", "right_label": "リターン (%)"
}
```

#### heatmap（seaborn）

```json
{
  "labels": ["XLK", "XLE", "XLF"],
  "matrix": [[1.0, 0.15, 0.45], [0.15, 1.0, 0.55], [0.45, 0.55, 1.0]],
  "annotate": true, "cmap": "RdBu_r", "vmin": -1, "vmax": 1
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

## メインスクリプト設計 (`scripts/generate_chart_image.py`)

### アーキテクチャ

```
JSON/dict入力 → バリデーション → テーマ適用 → レンダラー選択
  → matplotlib/seaborn 描画 → savefig() → PNG出力
```

generate-table-image の Playwright 方式ではなく、matplotlib の `savefig()` で直接PNG出力。チャートライブラリはネイティブに高品質PNG出力が可能なため、ブラウザ不要。

### 主要関数

```python
# レンダラーレジストリ（デコレータパターン）
_RENDERERS: dict[str, Callable] = {}

def register_renderer(chart_type: str): ...

# 9つのレンダラー
@register_renderer("line")   def _render_line(ax, data, theme): ...
@register_renderer("bar")    def _render_bar(ax, data, theme): ...
@register_renderer("hbar")   def _render_hbar(ax, data, theme): ...
@register_renderer("scatter") def _render_scatter(ax, data, theme): ...
@register_renderer("area")   def _render_area(ax, data, theme): ...
@register_renderer("combo")  def _render_combo(fig, ax, data, theme): ...
@register_renderer("heatmap") def _render_heatmap(ax, data, theme): ...
@register_renderer("pie")    def _render_pie(ax, data, theme): ...
@register_renderer("donut")  def _render_donut(ax, data, theme): ...

# ユーティリティ
def _apply_annotations(ax, annotations, theme): ...
def _format_axis(ax, fmt, axis="y"): ...
def _add_caption(fig, caption, theme): ...

# メインAPI
def generate_chart_image(spec: dict, output_path: str | Path, *, theme_name=None, scale=None) -> Path: ...
async def generate_chart_image_async(...) -> Path: ...  # run_in_executor 経由
```

### CLI

```bash
uv run python scripts/generate_chart_image.py chart_data.json -o output.png
uv run python scripts/generate_chart_image.py chart_data.json -o output.png --theme note_light --scale 2
uv run python scripts/generate_chart_image.py indices.json -o indices.png --preset indices-bar
```

## プリセット (`scripts/chart_presets.py`)

週次レポートやマクロ記事向けのデータ→チャート仕様変換関数:

| プリセット | 入力 | チャート |
|-----------|------|---------|
| `indices_bar` | indices.json | 指数別リターン棒グラフ |
| `sectors_bar` | sectors.json | セクター別リターン棒グラフ |
| `mag7_bar` | mag7.json | MAG7銘柄リターン棒グラフ |
| `asset_simulation` | パラメータ | 資産シミュレーション面グラフ |
| `dot_plot` | 予測データ | FRBドットプロット散布図 |

## SKILL.md 構成

```yaml
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
```

セクション構成:
1. いつ使用するか（プロアクティブ / 明示的）
2. 使用方法（JSON入力 / Pythonモジュール / プリセット）
3. JSON入力形式（共通 + チャートタイプ別）
4. パラメータ一覧
5. CLI オプション
6. プリセット一覧
7. 出力先の慣例
8. 関連リソース

## 日本語フォント対応

matplotlib で Noto Sans JP を使用:

```python
matplotlib.use("Agg")  # ヘッドレス環境対応

# フォント検出順序:
# 1. CHART_FONT_PATH 環境変数
# 2. システムフォント検索（font_manager.findSystemFonts()）
# 3. フォント未検出時はデフォルト + WARNING ログ
```

## 実装順序

### Step 1: 基盤
- `pyproject.toml` に `chart` dependency 追加
- `scripts/chart_theme.py` 作成（ChartTheme + NOTE_LIGHT/NOTE_DARK）
- テーマのテスト作成

### Step 2: コアスクリプト（line + bar）
- `scripts/generate_chart_image.py` 作成
- レンダラーレジストリ + line, bar レンダラー
- CLI エントリポイント
- テスト作成

### Step 3: 残りのチャートタイプ
- hbar, scatter, area, combo, heatmap, pie, donut レンダラー追加
- アノテーション、軸フォーマット、キャプション
- テスト追加

### Step 4: プリセット
- `scripts/chart_presets.py` 作成
- `--preset` CLI オプション追加

### Step 5: スキル定義
- `.claude/skills/generate-chart-image/SKILL.md` 作成

## 検証方法

```bash
# 1. 依存関係インストール
uv sync --extra chart

# 2. テスト実行
uv run pytest tests/scripts/test_generate_chart_image.py tests/scripts/test_chart_theme.py -v

# 3. CLI 動作確認（各チャートタイプ）
echo '{"chart_type":"bar","title":"テスト","data":{"categories":["A","B","C"],"series":[{"label":"値","values":[10,20,15]}]}}' > /tmp/test_chart.json
uv run python scripts/generate_chart_image.py /tmp/test_chart.json -o /tmp/test_chart.png
open /tmp/test_chart.png

# 4. 品質チェック
make check-all
```
