"""1:1 アスペクト比の概念図を PNG 画像として生成するスクリプト.

HTML/CSS + Playwright でレンダリングし、高品質な概念図画像を出力する。
Instagram カルーセル風のデザインで、4種類のレイアウトに対応。

Usage
-----
CLI:
    uv run python scripts/generate_concept_image.py concept_data.json -o output.png

モジュール:
    from scripts.generate_concept_image import generate_concept_image

    generate_concept_image(
        type="grid",
        title="投資信託の選び方",
        items=[
            {"label": "低コスト", "description": "インデックスファンド", "icon": "🎯"},
            {"label": "分散投資", "description": "全世界株式", "icon": "🌍"},
            {"label": "長期保有", "description": "15年以上", "icon": "⏳"},
            {"label": "積立投資", "description": "毎月定額", "icon": "💰"},
        ],
        output_path="output.png",
    )

JSON 入力形式
------------
# grid / matrix
{
    "type": "grid",
    "title": "タイトル",
    "subtitle": "サブタイトル（省略可）",
    "items": [
        {"label": "セル1", "description": "説明", "icon": "🎯", "accent_color": "#22c55e"},
        {"label": "セル2", "description": "説明", "icon": "📊"},
        {"label": "セル3", "description": "説明", "icon": "🛡️"},
        {"label": "セル4", "description": "説明", "icon": "⚠️"}
    ],
    "axes": {"x_label": "コスト →", "y_label": "↑ リターン"},
    "caption": "注記（省略可）"
}

# comparison
{
    "type": "comparison",
    "title": "A vs B",
    "items": [
        {"label": "A案", "icon": "📊", "accent_color": "#2563eb",
         "points": ["ポイント1", "ポイント2", "ポイント3"]},
        {"label": "B案", "icon": "🎯", "accent_color": "#f59e0b",
         "points": ["ポイント1", "ポイント2", "ポイント3"]}
    ]
}

# steps
{
    "type": "steps",
    "title": "投資を始めるステップ",
    "items": [
        {"label": "口座開設", "description": "ネット証券で無料開設", "icon": "🏦"},
        {"label": "商品選択", "description": "インデックスファンドを選ぶ", "icon": "🔍"},
        {"label": "積立設定", "description": "毎月の金額を決める", "icon": "⚙️"},
        {"label": "長期保有", "description": "15年以上ほったらかし", "icon": "🌱"}
    ]
}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import structlog
from jinja2 import Template
from playwright.async_api import async_playwright

logger = structlog.get_logger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "concept.html"

DEFAULT_THEME_COLOR = "#2563eb"
DEFAULT_WIDTH = 720   # viewport px (scale 2 → 1440px output)
DEFAULT_HEIGHT = 540  # viewport px (scale 2 → 1080px output) → 4:3
DEFAULT_SCALE = 2
DEFAULT_BG_COLOR = "#ffffff"

VALID_TYPES = {"matrix", "grid", "comparison", "steps"}

# comparison の背景色
LEFT_BG = "#eef2ff"
RIGHT_BG = "#fff7ed"


def _validate_input(data: dict) -> None:
    """入力データのバリデーション."""
    layout_type = data.get("type")
    if layout_type not in VALID_TYPES:
        msg = f"type は {VALID_TYPES} のいずれか。取得値: {layout_type!r}"
        raise ValueError(msg)

    if not data.get("title"):
        msg = "title は必須です"
        raise ValueError(msg)

    items = data.get("items", [])
    if not items:
        msg = "items は1つ以上必要です"
        raise ValueError(msg)

    if layout_type in ("matrix", "grid") and len(items) != 4:
        msg = f"{layout_type} は items が4つ必要です（取得: {len(items)}）"
        raise ValueError(msg)

    if layout_type == "comparison" and len(items) != 2:
        msg = f"comparison は items が2つ必要です（取得: {len(items)}）"
        raise ValueError(msg)

    if layout_type == "steps" and not (3 <= len(items) <= 5):
        msg = f"steps は items が3〜5つ必要です（取得: {len(items)}）"
        raise ValueError(msg)

    if layout_type == "comparison":
        for i, item in enumerate(items):
            if not item.get("points"):
                msg = f"comparison の items[{i}] には points が必要です"
                raise ValueError(msg)


def _build_template_data(
    layout_type: str,
    title: str,
    items: list[dict],
    *,
    subtitle: str | None = None,
    axes: dict | None = None,
    caption: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    bg_color: str = DEFAULT_BG_COLOR,
) -> dict:
    """Jinja2 テンプレートに渡すデータを構築する."""
    return {
        "type": layout_type,
        "title": title,
        "subtitle": subtitle,
        "items": items,
        "axes": axes,
        "caption": caption,
        "theme_color": theme_color,
        "width": width,
        "height": height,
        "bg_color": bg_color,
        "left_bg": LEFT_BG,
        "right_bg": RIGHT_BG,
    }


async def generate_concept_image_async(
    layout_type: str,
    title: str,
    items: list[dict],
    output_path: str | Path,
    *,
    subtitle: str | None = None,
    axes: dict | None = None,
    caption: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    scale: int = DEFAULT_SCALE,
    bg_color: str = DEFAULT_BG_COLOR,
) -> Path:
    """概念図から PNG 画像を生成する（非同期版）.

    Parameters
    ----------
    layout_type : str
        レイアウト種別（matrix / grid / comparison / steps）。
    title : str
        概念図のタイトル。
    items : list[dict]
        各セルのデータ。必須キー: label。任意: description, accent_color, points。
    output_path : str | Path
        出力 PNG 画像のパス。
    subtitle : str | None
        サブタイトル（省略可）。
    axes : dict | None
        matrix 用の軸ラベル。キー: x_label, y_label。
    caption : str | None
        下部注記（省略可）。
    theme_color : str
        テーマカラー（CSS カラーコード）。
    width : int
        ビューポート幅（px）。
    height : int
        ビューポート高さ（px）。
    scale : int
        デバイスピクセル比（2 で Retina 対応）。
    bg_color : str
        背景色。

    Returns
    -------
    Path
        生成された画像のパス。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)

    data = _build_template_data(
        layout_type,
        title,
        items,
        subtitle=subtitle,
        axes=axes,
        caption=caption,
        theme_color=theme_color,
        width=width,
        height=height,
        bg_color=bg_color,
    )
    html_content = template.render(**data)

    logger.info(
        "Rendering concept image",
        output=str(output_path),
        type=layout_type,
        items=len(items),
        size=f"{width}x{height}",
        scale=scale,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(device_scale_factor=scale)
        await page.set_viewport_size({"width": width, "height": height})
        await page.set_content(html_content, wait_until="networkidle")

        container = page.locator(".concept-container")
        await container.screenshot(
            path=str(output_path),
            type="png",
            omit_background=True,
        )
        await browser.close()

    logger.info("Concept image generated", path=str(output_path))
    return output_path


def generate_concept_image(
    layout_type: str,
    title: str,
    items: list[dict],
    output_path: str | Path,
    *,
    subtitle: str | None = None,
    axes: dict | None = None,
    caption: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    scale: int = DEFAULT_SCALE,
    bg_color: str = DEFAULT_BG_COLOR,
) -> Path:
    """概念図から PNG 画像を生成する（同期版）."""
    return asyncio.run(
        generate_concept_image_async(
            layout_type,
            title,
            items,
            output_path,
            subtitle=subtitle,
            axes=axes,
            caption=caption,
            theme_color=theme_color,
            width=width,
            height=height,
            scale=scale,
            bg_color=bg_color,
        )
    )


def _load_json(path: str) -> dict:
    """JSON ファイルを読み込む."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(
        description="1:1 概念図を PNG 画像として生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
レイアウト種別:
  matrix      2×2 マトリクス（軸ラベル付き）
  grid        2×2 特徴グリッド
  comparison  左右比較
  steps       ステップフロー（3〜5項目）
        """,
    )
    parser.add_argument("input", help="入力 JSON ファイルのパス")
    parser.add_argument("-o", "--output", required=True, help="出力 PNG ファイルのパス")
    parser.add_argument("--color", default=DEFAULT_THEME_COLOR, help="テーマカラー")
    parser.add_argument(
        "--width", type=int, default=DEFAULT_WIDTH, help="ビューポート幅 px"
    )
    parser.add_argument(
        "--height", type=int, default=DEFAULT_HEIGHT, help="ビューポート高さ px"
    )
    parser.add_argument(
        "--scale", type=int, default=DEFAULT_SCALE, help="デバイスピクセル比"
    )
    parser.add_argument("--bg", default=DEFAULT_BG_COLOR, help="背景色")

    args = parser.parse_args()

    data = _load_json(args.input)
    _validate_input(data)

    generate_concept_image(
        layout_type=data["type"],
        title=data["title"],
        items=data["items"],
        output_path=args.output,
        subtitle=data.get("subtitle"),
        axes=data.get("axes"),
        caption=data.get("caption"),
        theme_color=data.get("theme_color", args.color),
        width=data.get("width", args.width),
        height=data.get("height", args.height),
        scale=data.get("scale", args.scale),
        bg_color=data.get("bg_color", args.bg),
    )

    print(f"Generated: {args.output}")


if __name__ == "__main__":
    main()
