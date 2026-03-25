---
description: note.com記事をスクレイピングしcreator-neo4jに投入
skill-preload: note-scrape
---

# /note-scrape

> **スキル参照**: `.claude/skills/note-scrape/SKILL.md`

note.com クリエイターの記事を Playwright でスクレイピングし、RawStore に保存後、creator-neo4j に投入します。

## 使用例

```bash
# クリエイターの記事を一括取得 → creator-neo4j に投入
/note-com-pipeline {username}

# 最大記事数を指定
/note-com-pipeline {username} --max-articles 30

# research-neo4j に投入
/note-com-pipeline {username} --target research

# スクレイピングのみ（Neo4j投入なし）
/note-com-pipeline {username} --scrape-only

# RSSモニタリング実行
/note-com-pipeline --monitor

# クリエイター管理
/note-com-pipeline --list
/note-com-pipeline --add {username}
/note-com-pipeline --remove {username}

# 既存データを別ターゲットに再投入
/note-com-pipeline --ingest {username} --target research
```

## 引数

$ARGUMENTS
