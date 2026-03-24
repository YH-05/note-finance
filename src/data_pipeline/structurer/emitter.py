"""StructuredOutput → emit_research_queue.py 実行.

Layer 3 の最終ステップ: 構造化データをJSONファイルに保存し、
emit_research_queue.py を呼び出して graph-queue JSON を生成する。
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.structurer.models import StructuredOutput

# AIDEV-NOTE: emit_research_queue.py のパスはプロジェクトルートからの相対パスで解決
_EMIT_SCRIPT = "scripts/emit_research_queue.py"


def _find_project_root() -> Path:
    """pyproject.toml があるディレクトリをプロジェクトルートとする."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current


def save_emit_input(
    output: StructuredOutput,
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """StructuredOutput を emit_research_queue.py 入力 JSON として保存する.

    Parameters
    ----------
    output : StructuredOutput
        構造化出力。
    output_dir : Path | None
        保存先ディレクトリ。None の場合は .tmp/ に保存。
    filename : str | None
        ファイル名。None の場合はタイムスタンプベースで生成。

    Returns
    -------
    Path
        保存された JSON ファイルのパス。
    """
    if output_dir is None:
        project_root = _find_project_root()
        output_dir = project_root / ".tmp"
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"pipeline_emit_input_{ts}.json"

    path = output_dir / filename
    data = output.to_emit_input()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_emit_graph_queue(
    input_path: Path,
    command: str = "web-research",
    output_path: Path | None = None,
) -> Path | None:
    """emit_research_queue.py を実行して graph-queue JSON を生成する.

    Parameters
    ----------
    input_path : Path
        入力JSONファイルのパス。
    command : str
        emit_research_queue.py の --command 値。
    output_path : Path | None
        出力先。None の場合は入力ファイルと同じディレクトリに生成。

    Returns
    -------
    Path | None
        生成された graph-queue JSON のパス。失敗時は None。
    """
    project_root = _find_project_root()
    script = project_root / _EMIT_SCRIPT

    if not script.exists():
        return None

    cmd = [
        "uv", "run", "python", str(script),
        "--command", command,
        "--input", str(input_path),
    ]
    if output_path:
        cmd.extend(["--output", str(output_path)])

    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=120,
    )

    if result.returncode != 0:
        return None

    # stdout から "Queue file: <path>" を探す
    for line in result.stdout.strip().split("\n"):
        if line.startswith("Queue file:"):
            queue_path = Path(line.split(":", 1)[1].strip())
            # 相対パスならプロジェクトルートからの絶対パスに変換
            if not queue_path.is_absolute():
                queue_path = project_root / queue_path
            if queue_path.exists():
                return queue_path

    # フォールバック: 明示的な output_path
    if output_path and output_path.exists():
        return output_path

    return None
