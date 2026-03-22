# 議論メモ: creator-neo4j オントロジー設計

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 背景・コンテキスト

A-1 で目的を「a) 記事素材検索 + b) トピックギャップ発見 + c) クロスジャンルパターン」の3つに定義。
A-2 としてオントロジーの具体的な概念構造を設計した。

## オントロジー構造

### 層構成

```
ConceptCategory（上位概念カテゴリ、初期12種、柔軟拡張可能）
  ↑ IS_A
Concept（ドメイン概念、ジャンル中立、成長する）
  ↑ SERVES_AS
Entity（固有名詞、具体的なサービス・人物・企業）
  ↑ MENTIONS
Fact / Tip / Story（コンテンツ）
  → IN_GENRE → Genre
  → ABOUT → Concept
  → FROM_SOURCE → Source
```

### ConceptCategory 初期12種

#### What層（何を書くか）7種

| カテゴリ | 説明 |
|---------|------|
| MonetizationMethod | 収益化手段（スキル販売、鑑定、アフィリエイト等） |
| AcquisitionChannel | 集客チャネル（SNS集客、SEO、口コミ等） |
| Skill | スキル・技能（タロット、プログラミング、SNS運用等） |
| Audience | ターゲット層（副業初心者、30代婚活女性等） |
| RevenueModel | 収益モデル（フロント→バックエンド、サブスク等） |
| SuccessMetric | 成果指標（月収、フォロワー数、成約率等） |
| ContentFormat | コンテンツ形式（リール動画、ブログ記事、PDF教材等） |

#### How層（どう書くか）5種

| カテゴリ | 説明 |
|---------|------|
| PersuasionTechnique | 説得技法（社会的証明、希少性、権威性等） |
| EmotionalHook | 感情トリガー（不安・焦り、憧れ、好奇心、FOMO等） |
| CopyFramework | 文章構成パターン（AIDA、PAS、ビフォーアフター等） |
| Objection | 読者の反論・障壁（「スキルがない」「怪しい」等） |
| Transformation | 変化パターン（未経験→月3万円、趣味→プロ等） |

### 拡張ルール

- ConceptCategory は固定ではなくデータ駆動で拡張可能
- 既存カテゴリに収まらない概念が3件以上出現 → 新カテゴリ提案 → 採用判断
- 抽出プロンプトに「既存カテゴリに該当しない場合は新カテゴリを提案せよ」と記載

### Concept vs Entity の境界ルール

| 判定基準 | → Concept | → Entity |
|---------|-----------|----------|
| 一般的な概念・カテゴリ | タロット、SNS集客 | — |
| 特定の固有名詞 | — | ココナラ、Instagram |
| テスト:「○○とは何か」で説明できる | ○ | × |
| テスト: 固有の運営者・URLがある | × | ○ |

Entity は SERVES_AS で Concept に紐付き、ドメイン上の役割を表現する:
```
Entity("Instagram") --SERVES_AS--> Concept("SNS集客") [AcquisitionChannel]
Entity("ココナラ")   --SERVES_AS--> Concept("スキル販売マーケットプレイス") [MonetizationMethod]
```

### リレーション一覧

| リレーション | From → To | 用途 |
|------------|-----------|------|
| IS_A | Concept → ConceptCategory | 概念の分類 |
| SERVES_AS | Entity → Concept | Entity のドメイン上の役割 |
| MENTIONS | Fact/Tip/Story → Entity | コンテンツ内の固有名詞参照 |
| ABOUT | Fact/Tip/Story → Concept | コンテンツの主題 |
| IN_GENRE | Fact/Tip/Story → Genre | ジャンル所属 |
| FROM_SOURCE | Fact/Tip/Story → Source | 出典 |
| ENABLES | Concept → Concept | AがBを可能にする |
| REQUIRES | Concept → Concept | AにはBが必要 |
| COMPETES_WITH | Concept → Concept | AとBは代替関係 |

## 決定事項

1. **12カテゴリ初期セット + 柔軟拡張**: 固定しない、データ駆動で成長
2. **Concept vs Entity 境界**: 一般概念 vs 固有名詞、SERVES_AS で役割表現
3. **Topic → Concept 移行**: 1,058件のTopicをConceptにリラベル、粒度整理、Topic廃止
4. **ソース目的管理なし**: JSON設定で定義せず、スキル拡充で対応

## アクションアイテム

- [ ] A-3: Neo4j スキーマ設計（制約・インデックス・マイグレーション Cypher） (優先度: 高)

## 次回の議論トピック

- A-3: スキーマ設計の具体的な制約・インデックス定義
- A-4: Entity 正規化ルール（表記揺れ吸収）
- B-1: Entity 抽出プロンプトのオントロジー準拠改修
