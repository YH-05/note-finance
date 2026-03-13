"""共通ユーティリティ — scripts/ 内のスクリプトで使用される共通関数・定数。"""

from __future__ import annotations

from pathlib import Path

from data_paths import get_path

# ---------------------------------------------------------------------------
# Well-known paths（スクリプト間で共有されるデータパス定数）
# ---------------------------------------------------------------------------

FINANCE_NEWS_THEMES_CONFIG = get_path("config/finance-news-themes.json")
"""金融ニューステーマ設定ファイルのパス。"""


def resolve_output_dir(arg: str | None, default_sub: str = "market") -> Path:
    """CLI --output 引数をパスに解決する。

    Parameters
    ----------
    arg : str | None
        CLI から渡された出力ディレクトリパス。None の場合はデフォルトを使用。
    default_sub : str
        デフォルトのサブパス名。

    Returns
    -------
    Path
        解決された出力ディレクトリの絶対パス。
    """
    if arg:
        return Path(arg)
    return get_path(default_sub)
