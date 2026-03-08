---
name: generate-table-image
description: note記事用の表をPNG画像として生成するスキル。HTML/CSS + Playwrightでレンダリングし、高品質な表画像を出力する。JSON定義またはインライン指定で利用可能。
allowed-tools: Read, Write, Bash
---

# 表画像生成スキル

Markdown の表を note.com 記事用の PNG 画像として生成する。HTML/CSS + Playwright でレンダリングし、Retina 対応の高品質画像を出力する。

## いつ使用するか

### プロアクティブ使用（自動で使用を検討）

以下の状況では、ユーザーが明示的に要求しなくても使用を検討:

1. **記事内に表データがある場合** - note記事の執筆中に表が含まれている
2. **比較データの可視化** - 手数料比較、パフォーマンス比較など
3. **asset-management ワークフロー** - 資産形成記事で数値比較を含む場合

### 明示的な使用

- 「表を画像にして」「テーブル画像を作って」などの直接的な要求

## 使用方法

### 方法1: JSON ファイルから生成（推奨）

```bash
uv run python scripts/generate_table_image.py table_data.json -o output.png
```

### 方法2: Python モジュールとして使用

```python
from scripts.generate_table_image import generate_table_image

generate_table_image(
    headers=["項目", "値A", "値B"],
    rows=[
        ["元本100万円", "約1,497万円", "**約918万円**"],
        ["毎月3万円積立", "約7,874万円", "**約5,510万円**"],
    ],
    output_path="output.png",
    title="手数料の影響",
)
```

## JSON 入力形式

```json
{
    "title": "表のタイトル（省略可）",
    "caption": "注記テキスト（省略可）",
    "headers": ["列1", "列2", "列3"],
    "rows": [
        ["セルA", "セルB", "**太字セル**"],
        ["セルD", "セルE", "セルF"]
    ],
    "theme_color": "#2563eb",
    "font_size": 15,
    "scale": 2
}
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| headers | (必須) | ヘッダー行のテキストリスト |
| rows | (必須) | 各行のセルテキストリスト |
| title | null | 表のタイトル（省略可） |
| caption | null | 表の下部に表示する注記（省略可） |
| theme_color | `#2563eb` | テーマカラー（CSSカラーコード） |
| font_size | 15 | 基本フォントサイズ（px） |
| scale | 2 | デバイスピクセル比（2でRetina対応） |

## セル記法

| 記法 | 効果 |
|------|------|
| `テキスト` | 通常表示 |
| `**テキスト**` | 太字 + テーマカラーで強調表示 |

数値・金額・パーセントが多い列は自動で右寄せになる。

## CLI オプション

```bash
uv run python scripts/generate_table_image.py INPUT_JSON -o OUTPUT_PNG [OPTIONS]

# オプション
--color COLOR      テーマカラー（デフォルト: #2563eb）
--font-size SIZE   フォントサイズ px（デフォルト: 15）
--scale SCALE      デバイスピクセル比（デフォルト: 2）
```

## 実行フロー

```
JSON/引数 → テンプレートデータ構築 → Jinja2 HTML レンダリング
  → Playwright でブラウザ起動 → 自然幅測定 → ビューポート調整
  → .table-container をスクリーンショット → PNG 出力
```

## 出力先の慣例

| 用途 | 出力パス例 |
|------|-----------|
| asset-management 記事 | `articles/asset_management/{slug}/images/{name}.png` |
| 週次レポート | `data/exports/weekly-report/images/{name}.png` |
| 一時利用 | `.tmp/table-{name}.png` |

## 関連リソース

| リソース | パス |
|---------|------|
| 生成スクリプト | `scripts/generate_table_image.py` |
| HTML テンプレート | `scripts/templates/table.html` |
| asset-management ワークフロー | `.agents/skills/asset-management-workflow/SKILL.md` |
