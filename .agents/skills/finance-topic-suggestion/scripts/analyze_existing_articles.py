import json
import os
from collections import Counter
from pathlib import Path

def analyze_articles(articles_dir: Path):
    """
    articles/*/article-meta.json を読み取って、カテゴリ分布と最新のトピックを抽出する。
    """
    categories = []
    latest_topics = []
    
    # articles/配下のディレクトリを走査
    if not articles_dir.exists():
        return {"total": 0, "categories": {}, "latest_topics": []}
        
    for article_path in articles_dir.iterdir():
        if article_path.is_dir():
            meta_file = article_path / "article-meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        categories.append(meta.get("category", "未分類"))
                        latest_topics.append({
                            "title": meta.get("title", article_path.name),
                            "category": meta.get("category", "未分類"),
                            "created_at": meta.get("created_at", "不明")
                        })
                except Exception:
                    continue
    
    # 最新5件を表示
    latest_topics.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "total": len(latest_topics),
        "categories": dict(Counter(categories)),
        "latest_topics": latest_topics[:5]
    }

if __name__ == "__main__":
    project_root = Path(os.getcwd())
    articles_dir = project_root / "articles"
    result = analyze_articles(articles_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
