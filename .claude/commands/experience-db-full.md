---
description: 体験談DB記事の全工程を一括実行。ソース収集→合成→執筆→批評→修正→Neo4j保存。
argument-hint: [--theme konkatsu|sidehustle|shisan] [--pattern-name "パターン名"] [--skip-note] [--skip-hf]
---

// turbo-all

# /experience-db-full - 体験談DB記事フルパイプライン

体験談DB（合成パターン法）の記事作成を全自動で実行します。

## 使用例

```bash
# テーマを対話で選択
/experience-db-full

# テーマ指定
/experience-db-full --theme konkatsu

# パターン名も指定
/experience-db-full --theme sidehustle --pattern-name "Webライター未経験→月5万達成型"

# note.com巡回をスキップ（高速化）
/experience-db-full --theme shisan --skip-note

# HFゲートをスキップ（非推奨）
/experience-db-full --theme konkatsu --skip-hf
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --theme | 対話で選択 | konkatsu, sidehustle, shisan |
| --pattern-name | 自動生成 | パターンの日本語名 |
| --skip-note | false | note.com Chrome巡回をスキップ |
| --skip-hf | false | HFゲートをスキップ（非推奨） |

## 処理フロー

このコマンドは `experience-db-workflow` スキルを読み込んで実行します。

```
Phase 1: ソース収集          ← Reddit + RSS + Web検索 + note.com
    ↓ [HF1] ソース確認
Phase 2: 合成パターン生成    ← experience-synthesizer
    ↓
Phase 3: 記事執筆            ← experience-writer (6,000-8,000字)
    ↓
Phase 4: 4エージェント並列批評 ← experience-db-critique
    ↓ [HF2] 批評結果確認
Phase 5: 批評反映・修正      ← experience-reviser
    ↓
Phase 6: Neo4j保存 + 完了    ← ExperiencePattern + EmbeddableResource
```

## 実行手順

### Step 0: パラメータ解析

1. 引数からテーマと各オプションを取得
2. テーマ未指定の場合はユーザーに選択させる:
   ```
   テーマを選択してください:
   1. 婚活 (konkatsu)
   2. 副業 (sidehustle)
   3. 資産形成 (shisan)
   ```
3. パターン名が未指定の場合は Phase 2 で自動生成

### Step 1: スキル読み込み

`experience-db-workflow` スキルを読み込む。

### Step 2: スキルの処理フローに従い Phase 1〜6 を実行

スキルの各Phaseを順次実行する。
詳細は `.claude/skills/experience-db-workflow/SKILL.md` を参照。

## 出力

### フォルダ構造

```
articles/exp-{theme}-{NNN}-{english-slug}/
├── article-meta.json          ← ワークフロー管理
├── 01_sources/
│   ├── reddit.json            ← Reddit体験談
│   ├── rss.json               ← Google News RSS
│   ├── web_search.json        ← Web検索結果
│   └── note_com.json          ← note.comハッシュタグ巡回
├── 02_synthesis/
│   └── synthesis.json         ← 合成パターン
├── 03_edit/
│   ├── first_draft.md         ← 初稿（6,000-8,000字）
│   ├── critic.json            ← 4エージェント批評結果
│   └── revised_draft.md       ← 改訂版
└── 04_published/
    └── YYYYMMDD_pattern-name.md  ← 最終版
```

## 所要時間の目安

| Phase | 所要時間 |
|-------|---------|
| Phase 1: ソース収集 | 3-5分 |
| Phase 2: 合成 | 2-3分 |
| Phase 3: 執筆 | 3-5分 |
| Phase 4: 批評 | 2-3分 |
| Phase 5: 修正 | 2-3分 |
| Phase 6: Neo4j保存 | 1分 |
| **合計** | **15-20分**（HF待ち時間除く） |

## 関連コマンド

| コマンド | 説明 |
|----------|------|
| `/collect-experience-stories` | Phase 1 のみ実行（ソース収集単体） |
| `/experience-db-critique` | Phase 4 のみ実行（批評単体） |
| `/publish-to-note` | 完成した記事をnote.comに下書き投稿 |

## 関連エージェント

| エージェント | Phase | 役割 |
|-------------|-------|------|
| experience-synthesizer | 2 | ソース合成 |
| experience-writer | 3 | 記事執筆 |
| exp-critic-reality | 4 | リアリティ批評 |
| exp-critic-empathy | 4 | 共感度批評 |
| exp-critic-embed | 4 | 埋め込みリンク批評 |
| exp-critic-balance | 4 | 文字量バランス批評 |
| experience-reviser | 5 | 批評反映修正 |
