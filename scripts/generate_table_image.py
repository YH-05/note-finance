"""表データからPNG画像を生成するスクリプト.

HTML/CSS + Playwright でレンダリングし、高品質な表画像を出力する。

Usage
-----
CLI:
    # JSON ファイルから生成
    uv run python scripts/generate_table_image.py table_data.json -o output.png

    # テーマカラー・フォントサイズ指定
    uv run python scripts/generate_table_image.py table_data.json -o output.png --color "#2563eb" --font-size 16

モジュール:
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

JSON 入力形式
------------
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

セル値で **テキスト** と書くと太字+テーマカラーで強調表示される。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import structlog
from jinja2 import Template
from playwright.async_api import async_playwright

logger = structlog.get_logger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "table.html"

DEFAULT_THEME_COLOR = "#2563eb"
DEFAULT_FONT_SIZE = 15
DEFAULT_SCALE = 2


def _parse_cell(value: str) -> dict[str, str | bool]:
    """セル値をパースし、太字マーカーを処理する."""
    bold_match = re.fullmatch(r"\*\*(.+?)\*\*", value.strip())
    if bold_match:
        return {"text": bold_match.group(1), "bold": True, "align": "left"}
    return {"text": value, "bold": False, "align": "left"}


def _detect_alignment(headers: list[str], rows: list[list[str]]) -> list[str]:
    """数値が多い列を右寄せに自動判定する."""
    num_cols = len(headers)
    alignments = ["left"] * num_cols

    for col_idx in range(num_cols):
        numeric_count = 0
        total = 0
        for row in rows:
            if col_idx >= len(row):
                continue
            raw = re.sub(r"\*\*(.+?)\*\*", r"\1", row[col_idx].strip())
            if re.search(r"[\d,.]+万?円|[\d.]+%", raw):
                numeric_count += 1
            total += 1
        if total > 0 and numeric_count / total >= 0.5:
            alignments[col_idx] = "right"

    return alignments


def _build_template_data(
    headers: list[str],
    rows: list[list[str]],
    *,
    title: str | None = None,
    caption: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    font_size: int = DEFAULT_FONT_SIZE,
) -> dict:
    """Jinja2 テンプレートに渡すデータを構築する."""
    alignments = _detect_alignment(headers, rows)

    parsed_rows = []
    for row in rows:
        parsed_cells = []
        for col_idx, cell_value in enumerate(row):
            cell = _parse_cell(cell_value)
            if col_idx < len(alignments):
                cell["align"] = alignments[col_idx]
            parsed_cells.append(cell)
        parsed_rows.append(parsed_cells)

    return {
        "title": title,
        "caption": caption,
        "headers": headers,
        "rows": parsed_rows,
        "theme_color": theme_color,
        "font_size": font_size,
    }


async def generate_table_image_async(
    headers: list[str],
    rows: list[list[str]],
    output_path: str | Path,
    *,
    title: str | None = None,
    caption: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    font_size: int = DEFAULT_FONT_SIZE,
    scale: int = DEFAULT_SCALE,
) -> Path:
    """表データからPNG画像を生成する（非同期版）.

    Parameters
    ----------
    headers : list[str]
        ヘッダー行のテキストリスト。
    rows : list[list[str]]
        各行のセルテキストリスト。**text** で太字強調。
    output_path : str | Path
        出力PNG画像のパス。
    title : str | None
        表のタイトル（省略可）。
    caption : str | None
        表の下部に表示する注記（省略可）。
    theme_color : str
        テーマカラー（CSSカラーコード）。
    font_size : int
        基本フォントサイズ（px）。
    scale : int
        デバイスピクセル比（Retina対応。2で2倍解像度）。

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
        headers,
        rows,
        title=title,
        caption=caption,
        theme_color=theme_color,
        font_size=font_size,
    )
    html_content = template.render(**data)

    logger.info(
        "Rendering table image",
        output=str(output_path),
        headers=len(headers),
        rows=len(rows),
        scale=scale,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # 初回: 広いビューポートで自然な表幅を測定
        page = await browser.new_page(device_scale_factor=scale)
        await page.set_content(html_content, wait_until="networkidle")

        # table の自然な幅を取得してビューポートをフィットさせる
        natural_width = await page.evaluate(
            "document.querySelector('table').scrollWidth"
        )
        container_padding = 0
        if title or caption:
            container_padding = 48  # padding-left + padding-right (24px * 2)
        fit_width = max(natural_width + container_padding, 300)

        await page.set_viewport_size({"width": fit_width, "height": 800})
        await page.set_content(html_content, wait_until="networkidle")

        container = page.locator(".table-container")
        await container.screenshot(
            path=str(output_path),
            type="png",
            omit_background=True,
        )
        await browser.close()

    logger.info("Table image generated", path=str(output_path))
    return output_path


def generate_table_image(
    headers: list[str],
    rows: list[list[str]],
    output_path: str | Path,
    *,
    title: str | None = None,
    caption: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    font_size: int = DEFAULT_FONT_SIZE,
    scale: int = DEFAULT_SCALE,
) -> Path:
    """表データからPNG画像を生成する（同期版）."""
    return asyncio.run(
        generate_table_image_async(
            headers,
            rows,
            output_path,
            title=title,
            caption=caption,
            theme_color=theme_color,
            font_size=font_size,
            scale=scale,
        )
    )


def _load_json(path: str) -> dict:
    """JSON ファイルを読み込む."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(
        description="表データからPNG画像を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
JSON入力例:
{
    "headers": ["項目", "値A", "値B"],
    "rows": [["行1", "100", "**200**"]],
    "title": "タイトル",
    "caption": "注記"
}
        """,
    )
    parser.add_argument("input", help="入力JSONファイルのパス")
    parser.add_argument("-o", "--output", required=True, help="出力PNGファイルのパス")
    parser.add_argument("--color", default=DEFAULT_THEME_COLOR, help="テーマカラー")
    parser.add_argument(
        "--font-size", type=int, default=DEFAULT_FONT_SIZE, help="フォントサイズ (px)"
    )
    parser.add_argument(
        "--scale", type=int, default=DEFAULT_SCALE, help="デバイスピクセル比"
    )

    args = parser.parse_args()

    data = _load_json(args.input)

    headers = data.get("headers")
    rows = data.get("rows")
    if not headers or not rows:
        print("Error: JSON に 'headers' と 'rows' が必要です", file=sys.stderr)
        sys.exit(1)

    generate_table_image(
        headers=headers,
        rows=rows,
        output_path=args.output,
        title=data.get("title"),
        caption=data.get("caption"),
        theme_color=data.get("theme_color", args.color),
        font_size=data.get("font_size", args.font_size),
        scale=data.get("scale", args.scale),
    )

    print(f"Generated: {args.output}")


if __name__ == "__main__":
    main()
