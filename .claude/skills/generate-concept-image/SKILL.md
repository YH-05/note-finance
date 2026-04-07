---
name: generate-concept-image
description: >
  note記事・Instagram カルーセル用の1:1概念図をPNG画像として生成するスキル。
  HTML/CSS + Playwright でレンダリングし、高品質な正方形画像を出力する。
  matrix（2×2マトリクス）/ grid（特徴グリッド）/ comparison（左右比較）/ steps（プロセスフロー）の4レイアウト対応。
  記事内で概念・特徴・比較・手順を視覚化したい場面でプロアクティブに使用すること。
  「概念図」「マトリクス」「比較図」「ステップ図」「カルーセル」「1:1画像」
  「インスタ用画像」「4分割」と言われたら必ずこのスキルを使うこと。
allowed-tools: Read, Write, Bash
---

# 概念図画像生成スキル

1:1 アスペクト比の概念図を note.com 記事や Instagram 投稿用の PNG 画像として生成する。
HTML/CSS + Playwright でレンダリングし、Retina 対応の高品質画像を出力する。

## いつ使用するか

### プロアクティブ使用（自動で使用を検討）

1. **記事内で概念を視覚化したい場合** - 特徴の比較、フレームワーク、プロセスの説明
2. **Instagram カルーセル用画像** - 1:1 の正方形デザインが必要な場面
3. **4つの観点をまとめたい場合** - マトリクスやグリッドで整理

### 明示的な使用

- 「概念図を作って」「マトリクス画像」「比較図」「ステップ図」などの直接的な要求

## レイアウト種別

| タイプ | 説明 | items 数 |
|--------|------|---------|
| `matrix` | 2×2 マトリクス（軸ラベル付き） | 4 |
| `grid` | 2×2 特徴グリッド（アクセントカラー付き） | 4 |
| `comparison` | 左右比較（箇条書きポイント） | 2 |
| `steps` | プロセスフロー（番号付きステップ） | 3〜5 |

## 使用方法

### 方法1: JSON ファイルから生成（推奨）

```bash
uv run python scripts/generate_concept_image.py concept_data.json -o output.png
```

### 方法2: Python モジュールとして使用

```python
from scripts.generate_concept_image import generate_concept_image

generate_concept_image(
    layout_type="grid",
    title="投資信託の4つの選定基準",
    items=[
        {"label": "低コスト", "description": "信託報酬0.2%以下", "accent_color": "#22c55e"},
        {"label": "分散投資", "description": "全世界株式で広く分散", "accent_color": "#3b82f6"},
        {"label": "長期保有", "description": "15年以上ほったらかし", "accent_color": "#f59e0b"},
        {"label": "積立投資", "description": "毎月定額で継続", "accent_color": "#ef4444"},
    ],
    output_path="output.png",
)
```

## JSON 入力形式

### grid / matrix

```json
{
    "type": "grid",
    "title": "タイトル",
    "subtitle": "サブタイトル（省略可）",
    "items": [
        {"label": "セル1", "description": "説明", "accent_color": "#22c55e"},
        {"label": "セル2", "description": "説明", "accent_color": "#3b82f6"},
        {"label": "セル3", "description": "説明", "accent_color": "#f59e0b"},
        {"label": "セル4", "description": "説明", "accent_color": "#ef4444"}
    ],
    "caption": "注記（省略可）"
}
```

matrix の場合、`axes` で軸ラベルを指定できる:

```json
{
    "type": "matrix",
    "axes": {"x_label": "コスト →", "y_label": "↑ リターン"},
    ...
}
```

### comparison

```json
{
    "type": "comparison",
    "title": "A vs B",
    "items": [
        {
            "label": "A案",
            "accent_color": "#2563eb",
            "points": ["ポイント1", "ポイント2", "ポイント3"]
        },
        {
            "label": "B案",
            "accent_color": "#f59e0b",
            "points": ["ポイント1", "ポイント2", "ポイント3"]
        }
    ]
}
```

### steps

```json
{
    "type": "steps",
    "title": "始め方ガイド",
    "items": [
        {"label": "ステップ1", "description": "説明テキスト"},
        {"label": "ステップ2", "description": "説明テキスト"},
        {"label": "ステップ3", "description": "説明テキスト"},
        {"label": "ステップ4", "description": "説明テキスト"}
    ]
}
```

## items の共通フィールド

| フィールド | 必須 | 説明 |
|-----------|------|------|
| label | yes | セル/ステップのタイトル |
| description | no | 補足説明テキスト |
| accent_color | no | アクセントカラー（CSS カラーコード） |
| points | comparison のみ | 箇条書きポイントのリスト |

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| type | (必須) | レイアウト種別（matrix / grid / comparison / steps） |
| title | (必須) | 概念図のタイトル |
| items | (必須) | セルデータの配列 |
| subtitle | null | サブタイトル |
| axes | null | matrix 用の軸ラベル（x_label, y_label） |
| caption | null | 下部注記テキスト |
| theme_color | `#2563eb` | テーマカラー |
| size | 540 | ビューポートサイズ px（scale 2 で 1080px 出力） |
| scale | 2 | デバイスピクセル比 |
| bg_color | `#ffffff` | 背景色 |

## CLI オプション

```bash
uv run python scripts/generate_concept_image.py INPUT_JSON -o OUTPUT_PNG [OPTIONS]

# オプション
--color COLOR    テーマカラー（デフォルト: #2563eb）
--size SIZE      ビューポートサイズ px（デフォルト: 540 → 出力 1080px）
--scale SCALE    デバイスピクセル比（デフォルト: 2）
--bg COLOR       背景色（デフォルト: #ffffff）
```

## 出力仕様

- **アスペクト比**: 1:1（正方形）
- **デフォルト出力サイズ**: 1080 x 1080 px（540px viewport × scale 2）
- **フォーマット**: PNG（透過背景対応）
- **フォント**: Noto Sans JP（400/700/900）

## 出力先の慣例

| 用途 | 出力パス例 |
|------|-----------|
| 記事内概念図 | `articles/{category}/{slug}/images/concept_*.png` |
| Instagram 投稿 | `creator/{persona}/images/concept_*.png` |
| 一時利用 | `.tmp/concept-{name}.png` |

## 関連リソース

| リソース | パス |
|---------|------|
| 生成スクリプト | `scripts/generate_concept_image.py` |
| HTML テンプレート | `scripts/templates/concept.html` |
| 表画像スキル | `.claude/skills/generate-table-image/SKILL.md` |
| チャート画像スキル | `.claude/skills/generate-chart-image/SKILL.md` |
