# チャート画像生成 詳細ガイド

## 2つの描画方式

### 方式1: JSON + generate_chart_image.py（カテゴリ軸向け）

棒グラフ・円グラフ・ヒートマップなど、X軸がカテゴリ（文字列ラベル）のチャートに最適。

```bash
uv run python scripts/generate_chart_image.py chart.json -o output.png
```

**適するケース**: セクター別リターン、ポートフォリオ配分、相関行列

### 方式2: 直接 matplotlib スクリプト（時系列向け）

長期間の日次データなど、X軸が datetime の時系列チャートには `matplotlib.dates` を直接使用する。
`generate_chart_image.py` のカテゴリ軸では、同一ラベルが1点にまとめられる問題が発生するため。

**適するケース**: 金利推移、株価推移、マクロ指標の長期トレンド

テンプレート: `examples/timeseries_template.py`

## チャートスタイル規約

### 複数ラインの場合

| 項目 | 値 | 理由 |
|------|-----|------|
| alpha | 0.6 | ラインが重なっても視認できる |
| linewidth | 1.0pt | 細めで情報密度を確保 |
| marker | False | 日次データではノイズになる |

### 単一ラインの場合

| 項目 | 値 |
|------|-----|
| alpha | 1.0 |
| linewidth | 2.0pt |
| marker | 任意 |

### カラーパレット

#### 関連系列（同カテゴリの年限違い等）→ グラデーション

```python
# ブルー系グラデーション（短期=薄い → 長期=濃い）
blue_gradient = [
    "#93C5FD",  # light blue
    "#60A5FA",
    "#3B82F6",
    "#2563EB",
    "#1D4ED8",
    "#1E3A8A",  # dark navy
]
```

#### 独立系列（異なるカテゴリの比較）→ テーマパレット

```python
from chart_theme import NOTE_LIGHT
# NOTE_LIGHT.palette の 8 色を使用
```

### タイトル

- タイトル1行で完結させる（サブタイトルは使わない）
- 期間を含める場合: `f"米国債利回り推移（{start}〜{end}）"`
- 日付の0パディングはしない: `1月4日` (OK) / `01月04日` (NG)

```python
def fmt_date(dt: datetime) -> str:
    return f"{dt.year}年{dt.month}月{dt.day}日"
```

### 凡例

- X軸の下に横並び配置（チャート領域を侵食しない）

```python
ax.legend(
    loc="upper center",
    bbox_to_anchor=(0.5, -0.1),
    fontsize=9,
    ncol=6,       # 系列数に応じて調整
    frameon=False,
)
```

### 出典

- チャート内には出典を記載しない（記事本文側で記述する）

### X軸（時系列）

- `mdates.YearLocator(5)` で5年間隔のメジャーティック
- `mdates.YearLocator(1)` でマイナーティック
- フォーマット: `%Y`（西暦のみ）

```python
ax.xaxis.set_major_locator(mdates.YearLocator(5))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.xaxis.set_minor_locator(mdates.YearLocator(1))
```

## データ取得パターン

### FRED（米国経済指標）

```python
import csv, io, httpx
from datetime import datetime

series_ids = ["DGS3MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS30"]
url = (
    f"https://fred.stlouisfed.org/graph/fredgraph.csv"
    f"?cosd={start_date}&coed={end_date}"
    f"&id={','.join(series_ids)}"
)
resp = httpx.get(url, follow_redirects=True, timeout=30)
rows = list(csv.DictReader(io.StringIO(resp.text)))
# カラム名: "observation_date", series_id ごとの列
# 欠損値: 空文字列 or "."
```

### 主要 FRED Series ID

| カテゴリ | Series ID | 説明 |
|---------|-----------|------|
| 米国債3ヶ月 | DGS3MO | 3-Month Treasury |
| 米国債1年 | DGS1 | 1-Year Treasury |
| 米国債2年 | DGS2 | 2-Year Treasury |
| 米国債5年 | DGS5 | 5-Year Treasury |
| 米国債10年 | DGS10 | 10-Year Treasury |
| 米国債30年 | DGS30 | 30-Year Treasury |
| FF金利 | DFF | Federal Funds Rate |
| CPI | CPIAUCSL | Consumer Price Index |
| 失業率 | UNRATE | Unemployment Rate |
| GDP | GDP | Gross Domestic Product |

## レイアウト調整

```python
# 凡例が下にある場合のレイアウト
fig.tight_layout(rect=[0, 0.05, 1, 1.0])

# 保存時の設定
fig.savefig(
    output, dpi=200,
    bbox_inches="tight",
    facecolor=theme.background_color,
    pad_inches=0.2,
)
```
