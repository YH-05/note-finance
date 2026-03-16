from __future__ import annotations

import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


def analyze_articles(articles_dir: Path) -> dict[str, Any]:
    """
    articles/{category}/{YYYY-MM-DD}_{slug}/meta.yaml を読み取って、
    カテゴリ分布と最新のトピックを抽出する。

    新しいネスト構造:
        articles/{category}/{YYYY-MM-DD}_{slug}/meta.yaml

    レガシー構造（フォールバック）:
        articles/{slug}/article-meta.json
    """
    categories = []
    latest_topics = []

    if not articles_dir.exists():
        return {"total": 0, "categories": {}, "latest_topics": []}

    # 新構造: articles/{category}/{article_dir}/meta.yaml
    for category_dir in articles_dir.iterdir():
        if not category_dir.is_dir():
            continue

        # Check if this is a category dir (contains article subdirs)
        # or a legacy flat article dir
        meta_yaml = category_dir / "meta.yaml"
        meta_json = category_dir / "article-meta.json"

        if meta_yaml.exists() or meta_json.exists():
            # Legacy flat structure: articles/{slug}/meta.yaml or article-meta.json
            _read_meta(category_dir, categories, latest_topics)
        else:
            # New nested structure: articles/{category}/{article_dir}/
            for article_path in category_dir.iterdir():
                if article_path.is_dir():
                    _read_meta(article_path, categories, latest_topics)

    # 最新5件を表示
    latest_topics.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "total": len(latest_topics),
        "categories": dict(Counter(categories)),
        "latest_topics": latest_topics[:5],
    }


def _read_meta(
    article_path: Path,
    categories: list[str],
    latest_topics: list[dict[str, str]],
) -> None:
    """Read meta.yaml (preferred) or article-meta.json (legacy) from an article dir."""
    meta_yaml = article_path / "meta.yaml"
    meta_json = article_path / "article-meta.json"

    meta = None
    if meta_yaml.exists():
        try:
            with meta_yaml.open("r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
        except Exception as e:
            warnings.warn(
                f"Failed to parse {meta_yaml}: {e}",
                stacklevel=2,
            )
    elif meta_json.exists():
        try:
            with meta_json.open("r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            warnings.warn(
                f"Failed to parse {meta_json}: {e}",
                stacklevel=2,
            )

    if meta is None:
        return

    categories.append(meta.get("category", "未分類"))
    latest_topics.append({
        "title": meta.get("title", article_path.name),
        "category": meta.get("category", "未分類"),
        "created_at": meta.get("created_at", "不明"),
    })


if __name__ == "__main__":
    project_root = Path.cwd()
    articles_dir = project_root / "articles"
    result = analyze_articles(articles_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
