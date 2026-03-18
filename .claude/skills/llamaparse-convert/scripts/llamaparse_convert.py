"""LlamaParse REST API を使った PDF → Markdown 変換スクリプト.

Parse のみ（Index 不要）で LlamaCloud クレジットを最小限に抑える。
Agentic tier: 10 credits/page, Cost Effective: 3 credits/page, Fast: 1 credit/page.

Usage
-----
    # Agentic tier (デフォルト)
    uv run python -m scripts.llamaparse_convert /path/to/report.pdf

    # Cost Effective tier
    uv run python -m scripts.llamaparse_convert --tier cost_effective /path/to/report.pdf

    # 出力先指定
    uv run python -m scripts.llamaparse_convert -o /output/dir /path/to/report.pdf

    # 複数 PDF
    uv run python -m scripts.llamaparse_convert *.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LLAMAPARSE_UPLOAD_URL = "https://api.cloud.llamaindex.ai/api/parsing/upload"
LLAMAPARSE_JOB_URL = "https://api.cloud.llamaindex.ai/api/parsing/job"

TIER_CREDITS: dict[str, int] = {
    "fast": 1,
    "cost_effective": 3,
    "agentic": 10,
    "agentic_plus": 45,
}

MAX_POLL_SECONDS = 300
POLL_INTERVAL_SECONDS = 3


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def _get_api_key() -> str:
    """Retrieve LLAMA_CLOUD_API_KEY from environment or .env file."""
    key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if key:
        return key

    env_path = Path.cwd() / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("LLAMA_CLOUD_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
                if key:
                    return key

    msg = (
        "LLAMA_CLOUD_API_KEY が見つかりません。"
        "環境変数または .env ファイルに設定してください。"
    )
    raise RuntimeError(msg)


def _compute_sha256(pdf_path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with pdf_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_pdf(
    pdf_path: Path,
    api_key: str,
    *,
    tier: str = "agentic",
) -> str:
    """Upload a PDF to LlamaParse and return the job ID.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.
    api_key : str
        LlamaCloud API key.
    tier : str
        Parsing tier: fast, cost_effective, agentic, agentic_plus.

    Returns
    -------
    str
        Job ID for polling.
    """
    logger.info(
        "Uploading PDF to LlamaParse: %s (tier=%s, %s cr/page)",
        pdf_path.name, tier, TIER_CREDITS.get(tier, "?"),
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "accept": "application/json",
    }

    with pdf_path.open("rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        data = {"result_type": "markdown"}

        resp = requests.post(
            LLAMAPARSE_UPLOAD_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )

    resp.raise_for_status()
    result = resp.json()
    job_id = result["id"]
    logger.info("Upload succeeded: job_id=%s status=%s", job_id, result.get("status"))
    return job_id


def poll_job(job_id: str, api_key: str) -> str:
    """Poll a LlamaParse job until completion.

    Parameters
    ----------
    job_id : str
        The parsing job ID.
    api_key : str
        LlamaCloud API key.

    Returns
    -------
    str
        Final status: SUCCESS or ERROR.

    Raises
    ------
    TimeoutError
        If the job does not complete within MAX_POLL_SECONDS.
    RuntimeError
        If the job fails.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{LLAMAPARSE_JOB_URL}/{job_id}"

    elapsed = 0.0
    while elapsed < MAX_POLL_SECONDS:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "UNKNOWN")

        if status == "SUCCESS":
            logger.info("Parsing completed: job_id=%s", job_id)
            return status
        if status in ("ERROR", "FAILED"):
            error_msg = data.get("error_message", "Unknown error")
            msg = f"LlamaParse job failed: {error_msg}"
            raise RuntimeError(msg)

        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS
        if int(elapsed) % 15 == 0:
            logger.debug("Still parsing... job_id=%s elapsed=%ds", job_id, int(elapsed))

    msg = f"LlamaParse job timed out after {MAX_POLL_SECONDS}s"
    raise TimeoutError(msg)


def get_markdown(job_id: str, api_key: str) -> str:
    """Retrieve the parsed Markdown result.

    Parameters
    ----------
    job_id : str
        The completed parsing job ID.
    api_key : str
        LlamaCloud API key.

    Returns
    -------
    str
        Parsed Markdown text.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{LLAMAPARSE_JOB_URL}/{job_id}/result/markdown"

    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    markdown = data.get("markdown", "")
    logger.info("Markdown retrieved: %d chars", len(markdown))
    return markdown


def convert_pdf(
    pdf_path: Path,
    output_dir: Path | None = None,
    *,
    tier: str = "agentic",
) -> dict:
    """Convert a single PDF to Markdown via LlamaParse REST API.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.
    output_dir : Path | None
        Output directory. If None, uses ``{pdf_stem}_{hash8}/`` next to the PDF.
    tier : str
        Parsing tier.

    Returns
    -------
    dict
        Result metadata including output paths and credit estimate.
    """
    if not pdf_path.exists():
        msg = f"PDF ファイルが見つかりません: {pdf_path}"
        raise FileNotFoundError(msg)
    if pdf_path.suffix.lower() != ".pdf":
        msg = f"PDF ファイルではありません（拡張子: {pdf_path.suffix}）"
        raise ValueError(msg)

    api_key = _get_api_key()
    sha256 = _compute_sha256(pdf_path)
    hash8 = sha256[:8]

    if output_dir is None:
        output_dir = pdf_path.parent / f"{pdf_path.stem}_{hash8}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Page count (best-effort via fitz) ---
    page_count = 0
    try:
        import fitz  # type: ignore[import-untyped]

        with fitz.open(str(pdf_path)) as doc:
            page_count = len(doc)
        logger.info("Page count: %d", page_count)
    except ImportError:
        logger.warning("PyMuPDF not available; page count unknown")

    credits_per_page = TIER_CREDITS.get(tier, 10)
    estimated_credits = page_count * credits_per_page if page_count else 0

    # --- Upload → Poll → Get Markdown ---
    job_id = upload_pdf(pdf_path, api_key, tier=tier)
    poll_job(job_id, api_key)
    markdown = get_markdown(job_id, api_key)

    if not markdown.strip():
        msg = "LlamaParse returned empty markdown"
        raise RuntimeError(msg)

    # --- Save outputs ---
    report_path = output_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    logger.info("report.md saved: %s", report_path)

    metadata = {
        "sha256": sha256,
        "pdf_path": str(pdf_path.resolve()),
        "pdf_name": pdf_path.name,
        "pages": page_count,
        "converter": "llamaparse",
        "tier": tier,
        "credits_per_page": credits_per_page,
        "estimated_credits": estimated_credits,
        "job_id": job_id,
        "processed_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("metadata.json saved: %s", metadata_path)

    return {
        "status": "success",
        "pdf": str(pdf_path),
        "output_dir": str(output_dir),
        "report_md": str(report_path),
        "metadata_json": str(metadata_path),
        "pages": page_count,
        "estimated_credits": estimated_credits,
        "markdown_length": len(markdown),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for llamaparse_convert."""
    parser = argparse.ArgumentParser(
        description="LlamaParse REST API で PDF を Markdown に変換",
    )
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        type=Path,
        help="変換対象の PDF ファイルパス",
    )
    parser.add_argument(
        "--tier",
        choices=list(TIER_CREDITS.keys()),
        default="agentic",
        help="パースティア (default: agentic, 10 credits/page)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="出力ディレクトリ（省略時は PDF と同階層に自動生成）",
    )
    args = parser.parse_args()

    results = []
    for pdf_path in args.pdf_paths:
        try:
            out_dir = args.output_dir
            if out_dir and len(args.pdf_paths) > 1:
                out_dir = out_dir / pdf_path.stem
            result = convert_pdf(pdf_path, out_dir, tier=args.tier)
            results.append(result)
            print(f"✓ {pdf_path.name} → {result['output_dir']}")
        except Exception as e:
            logger.error("Conversion failed: %s - %s", pdf_path, e)
            results.append({"status": "error", "pdf": str(pdf_path), "error": str(e)})
            print(f"✗ {pdf_path.name}: {e}")

    # Print summary JSON
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
