---
description: 体験談DB用のソースを巡回し、合成パターン法の素材となる体験談を収集します。テーマ別（婚活/副業/資産形成）にReddit・RSS・note.comから収集。
argument-hint: [--theme konkatsu|sidehustle|shisan|all] [--source reddit|rss|note|all] [--top-n 10]
---

# /collect-experience-stories - 体験談ソース巡回・収集

体験談DB（合成パターン法）の素材収集コマンド。3テーマ×複数ソースから体験談を収集し、構造化データとして保存する。

## 使用例

```bash
# 全テーマ・全ソースで収集
/collect-experience-stories

# 婚活テーマのみ、Reddit から
/collect-experience-stories --theme konkatsu --source reddit

# 資産形成テーマのみ、RSS から
/collect-experience-stories --theme shisan --source rss

# 副業テーマ、上位20件
/collect-experience-stories --theme sidehustle --top-n 20
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --theme | all | 対象テーマ: konkatsu, sidehustle, shisan, all |
| --source | all | 収集ソース: reddit, rss, note, all |
| --top-n | 10 | 各ソースの最大取得件数 |

## 処理フロー

```
1. パラメータ解析
2. ソース別収集（並列可能）
   ├── Reddit MCP → サブレディット巡回
   ├── RSS MCP → Google News体験談フィード取得
   └── note.com → Chrome自動化でハッシュタグ巡回
3. 体験談フィルタリング（AI判定）
4. 構造化データとして保存（JSON）
5. サマリー表示
```

## ソース定義

### Reddit サブレディット（テーマ別）

#### 婚活 (konkatsu)
| サブレディット | 用途 | 優先度 |
|---------------|------|--------|
| r/hingeapp | 真剣交際の体験談（質が高い） | 高 |
| r/OnlineDating | マッチングアプリ全般の体験 | 高 |
| r/dating_advice | デート・交際の相談 | 中 |
| r/Bumble | Bumbleアプリ体験 | 中 |
| r/Tinder | Tinder体験（ミーム多め、選別必要） | 低 |

#### 副業 (sidehustle)
| サブレディット | 用途 | 優先度 |
|---------------|------|--------|
| r/sidehustle | 副業全般の体験談 | 高 |
| r/freelance | フリーランス実務体験 | 高 |
| r/WorkOnline | オンライン副業 | 中 |
| r/Entrepreneur | 起業・副業ストーリー | 中 |
| r/beermoney | 小額副収入 | 低 |

#### 資産形成 (shisan)
| サブレディット | 用途 | 優先度 |
|---------------|------|--------|
| r/Bogleheads | インデックス投資体験（質が最高） | 高 |
| r/personalfinance | 資産形成全般 | 高 |
| r/financialindependence | FIRE・長期資産形成 | 高 |
| r/investing | 投資判断の体験 | 中 |
| r/stocks | 個別株体験 | 中 |

### RSS フィードカテゴリ

| カテゴリ | フィード数 | 説明 |
|---------|-----------|------|
| experience-db-konkatsu | 3 | 婚活体験談（Google News） |
| experience-db-sidehustle | 3 | 副業体験談（Google News） |
| experience-db-shisan | 3 | 資産形成体験談（Google News） |

### note.com ハッシュタグ（Chrome巡回用）

| テーマ | ハッシュタグ | URL |
|--------|------------|-----|
| 婚活 | #婚活 | https://note.com/hashtag/婚活 |
| 婚活 | #マッチングアプリ | https://note.com/hashtag/マッチングアプリ |
| 婚活 | #婚活体験記 | https://note.com/hashtag/婚活体験記 |
| 副業 | #副業 | https://note.com/hashtag/副業 |
| 副業 | #Webライター | https://note.com/hashtag/Webライター |
| 副業 | #フリーランス | https://note.com/hashtag/フリーランス |
| 資産形成 | #NISA | https://note.com/hashtag/NISA |
| 資産形成 | #資産形成 | https://note.com/hashtag/資産形成 |
| 資産形成 | #投資信託 | https://note.com/hashtag/投資信託 |

## 収集手順

### Step 1: Reddit MCP 収集

各テーマの対象サブレディットに対して `mcp__reddit__get_subreddit_new_posts` を実行。

体験談フィルタリング基準:
- タイトルに体験を示すキーワードが含まれる（"experience", "story", "journey", "update", "progress", "finally", "success", "failed"）
- 自己投稿（self post）であること
- 一定のスコア（upvote数）以上

### Step 2: RSS フィード収集

`mcp__rss__rss_search_items` で各カテゴリのフィードを検索。

```
category: experience-db-{theme}
```

### Step 3: note.com 収集（オプション）

Chrome自動化（`mcp__claude-in-chrome__*`）でハッシュタグページを巡回。
- `mcp__claude-in-chrome__navigate` でハッシュタグページを開く
- `mcp__claude-in-chrome__get_page_text` でタイトル・概要を取得
- 体験談と判定されるものをピックアップ

### Step 4: フィルタリング・構造化

収集した体験談候補を以下の基準でスクリーニング:

| 基準 | 閾値 | 説明 |
|------|------|------|
| 最低文字数 | 200字以上 | 断片的な投稿を除外 |
| 具体性 | 数値・期間が含まれる | 「月5万稼いだ」「3ヶ月で成婚」等 |
| 一人称視点 | I/私/僕 | 第三者レポートではなく当事者体験 |
| AI生成判定 | 連載形式・感情描写あり | テンプレ的な記事を除外 |

### Step 5: 保存

収集結果を `.tmp/experience-stories/` に日付付きJSONで保存:

```json
{
  "collection_date": "2026-03-09",
  "theme": "konkatsu",
  "stories": [
    {
      "source": "reddit",
      "subreddit": "r/hingeapp",
      "title": "...",
      "url": "...",
      "summary": "...",
      "score": 150,
      "attributes": {
        "age_range": "30s",
        "gender": "female",
        "duration": "8 months",
        "outcome": "success"
      }
    }
  ],
  "stats": {
    "total_collected": 30,
    "filtered_in": 12,
    "by_source": {"reddit": 8, "rss": 3, "note": 1}
  }
}
```

## 出力

実行後に以下を表示:

```
## 体験談収集結果 (2026-03-09)

### 婚活
- Reddit: 8件 (r/hingeapp 3, r/OnlineDating 3, r/dating_advice 2)
- RSS: 3件 (Google News)
- 合計: 11件

### 副業
- Reddit: 6件 (r/sidehustle 3, r/freelance 2, r/WorkOnline 1)
- RSS: 4件 (Google News)
- 合計: 10件

### 資産形成
- Reddit: 7件 (r/Bogleheads 3, r/personalfinance 2, r/financialindependence 2)
- RSS: 3件 (Google News)
- 合計: 10件

💾 保存先: .tmp/experience-stories/2026-03-09_collection.json
```

## 関連リソース

| リソース | パス |
|---------|------|
| ソース検証結果 | `docs/plan/SideBusiness/2026-03-09_db-experience-source-verification.md` |
| 匿名化戦略 | `docs/plan/SideBusiness/2026-03-09_anonymization-strategy.md` |
| テンプレートv2 | `docs/plan/SideBusiness/体験談DB統一テンプレート_v2.md` |
| 試作パターン | `docs/plan/SideBusiness/2026-03-09_*-pattern-001-v2.md` |
