"""career_sister カルーセル画像レンダリングスクリプト.

JSON定義からHTML→Playwright→PNGのパイプラインでInstagramカルーセル画像を生成する。

Usage:
    uv run --with playwright python scripts/render_carousel.py <input.json> [--output-dir <dir>]

Input JSON format:
    {
        "slides": [
            {"type": "title", "hook": "フック文", "sub": "サブテキスト"},
            {"type": "content", "heading": "見出し", "body": "本文", "number": "01"},
            {"type": "points", "heading": "まとめ", "items": ["ポイント1", "ポイント2"]},
            {"type": "cta", "message": "メッセージ", "account": "@career_sister"}
        ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "career_sister" / "carousel.html"


def _render_title_slide(slide: dict) -> str:
    hook = escape(slide.get("hook", "")).replace("\n", "<br>")
    return f"""
    <div class="slide slide-title">
        <div class="top-block">
            <div class="top-label">CAREER TIPS</div>
        </div>
        <div class="bottom-block">
            <div class="hook">{hook}</div>
            <div class="account-name">@career_sister</div>
            <div class="swipe-hint">スワイプで読む →</div>
        </div>
    </div>"""


# スライド総数を追跡するためのカウンタ（build_html側で設定）
_total_body_slides = 0
_current_body_index = 0


def _render_content_slide(slide: dict) -> str:
    global _current_body_index
    _current_body_index += 1
    heading = escape(slide.get("heading", "")).replace("\n", "<br>")
    body = slide.get("body", "")
    number = escape(slide.get("number", ""))
    import re

    body_html = re.sub(
        r"\*\*(.+?)\*\*",
        r'<span class="highlight">\1</span>',
        escape(body),
    )
    body_html = body_html.replace("\n", "<br>")
    page = f"{_current_body_index}/{_total_body_slides}"
    return f"""
    <div class="slide slide-content">
        <div class="accent-bar"></div>
        <div class="main-area">
            <div class="content-number">{number}</div>
            <div class="content-heading">{heading}</div>
            <div class="content-body">{body_html}</div>
            <div class="divider"></div>
        </div>
        <div class="footer">
            <div class="footer-account">@career_sister</div>
            <div class="footer-page">{page}</div>
        </div>
    </div>"""


def _render_points_slide(slide: dict) -> str:
    global _current_body_index
    _current_body_index += 1
    heading = escape(slide.get("heading", ""))
    items = slide.get("items", [])
    closing = escape(slide.get("closing", ""))
    number = f"{_current_body_index:02d}"
    items_html = "\n".join(
        f'            <div class="point-item">✔ {escape(item)}</div>'
        for item in items
    )
    page = f"{_current_body_index}/{_total_body_slides}"
    closing_html = ""
    if closing:
        closing_html = f'<div class="closing">{closing.replace(chr(10), "<br>")}</div>'
    return f"""
    <div class="slide slide-points">
        <div class="accent-bar"></div>
        <div class="main-area">
            <div class="points-number">{number}</div>
            <div class="points-heading">{heading}</div>
            <div class="summary-box">
{items_html}
            </div>
            <div class="divider"></div>
            {closing_html}
        </div>
        <div class="footer">
            <div class="footer-account">@career_sister</div>
            <div class="footer-page">{page}</div>
        </div>
    </div>"""


def _render_cta_slide(slide: dict) -> str:
    return f"""
    <div class="slide slide-cta">
        <div class="cta-heading">この投稿が<br>役に立ったら</div>
        <div class="cta-emphasis">♡ いいね &amp; 保存</div>
        <div class="cta-divider"></div>
        <div class="cta-button">フォローする</div>
        <div class="cta-account">@career_sister</div>
        <div class="cta-tagline">転職の不安を、<br>一歩踏み出す勇気に変える。</div>
    </div>"""


RENDERERS = {
    "title": _render_title_slide,
    "content": _render_content_slide,
    "points": _render_points_slide,
    "cta": _render_cta_slide,
}


def build_html(slides: list[dict]) -> str:
    """スライドJSONからフルHTMLを生成."""
    global _total_body_slides, _current_body_index
    # title と cta を除いた本文スライド数をカウント
    _total_body_slides = sum(
        1 for s in slides if s.get("type") in ("content", "points")
    )
    _current_body_index = 0

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    body_parts: list[str] = []
    for slide in slides:
        slide_type = slide.get("type", "content")
        renderer = RENDERERS.get(slide_type)
        if renderer is None:
            logger.warning("Unknown slide type: %s", slide_type)
            continue
        body_parts.append(renderer(slide))

    # templateの</body>の前にスライドHTMLを挿入
    html = template.replace("</body>", "\n".join(body_parts) + "\n</body>")
    return html


async def render_slides(slides: list[dict], output_dir: Path) -> list[Path]:
    """PlaywrightでスライドをPNG画像にレンダリング."""
    from playwright.async_api import async_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    html = build_html(slides)

    # 完全なHTMLを保存（デバッグ・再編集用）
    html_path = output_dir / "slides.html"
    html_path.write_text(html, encoding="utf-8")
    logger.info("HTML saved: %s", html_path)

    output_paths: list[Path] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        await page.set_content(html)

        # 各スライドをスクリーンショット
        slide_elements = await page.query_selector_all(".slide")
        for i, element in enumerate(slide_elements):
            out_path = output_dir / f"slide_{i + 1:02d}.png"
            await element.screenshot(path=str(out_path))
            output_paths.append(out_path)
            logger.info("Slide %d rendered: %s", i + 1, out_path)

        await browser.close()

    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Render carousel slides to PNG")
    parser.add_argument("input", help="JSON file with slide definitions")
    parser.add_argument("--output-dir", "-o", default=None, help="Output directory")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    slides = data.get("slides", [])

    if not slides:
        logger.error("No slides found in input JSON")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent / "carousel"

    import asyncio

    paths = asyncio.run(render_slides(slides, output_dir))
    logger.info("Rendering complete: %d slides in %s", len(paths), output_dir)

    # 結果JSONを出力
    result = {"slides": [str(p) for p in paths], "html": str(output_dir / "slides.html")}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
