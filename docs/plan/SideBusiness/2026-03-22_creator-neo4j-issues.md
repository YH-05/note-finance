# 議論メモ: creator-neo4j 課題分析

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-enrichment セッション（4サイクル）完了後、creator-neo4j の全体的な品質を定量分析。
Entity 層の導入はこのセッションが初めてであり、旧データとの乖離が明確になった。

## 定量分析結果

### ノード分布

| ラベル | 件数 |
|--------|------|
| Topic | 1,058 |
| Fact | 313 |
| Tip | 213 |
| Source | 211 |
| Entity | 88 |
| Story | 61 |
| Service（旧） | 16 |
| Genre | 3 |
| Account（旧） | 3 |

### リレーション分布

| タイプ | 件数 |
|--------|------|
| ABOUT | 1,668 |
| IN_GENRE | 1,148 |
| FROM_SOURCE | 562 |
| MENTIONS | 95 |
| RELATES_TO | 25 |

### 課題サマリー

| # | 課題 | 定量データ | 優先度 |
|---|------|-----------|--------|
| 1 | Entity 未接続 84% | MENTIONS 95件 / コンテンツ 587件 = 0.16/件 | **高** |
| 2 | Source authority_level 欠損 | 185/211件（88%）が null | **高** |
| 3 | RELATES_TO 疎 | 25件 / Entity 88件 = 28.4% | 中 |
| 4 | Story 不足 | 61件（10%）vs 理想 25% | 中 |
| 5 | ジャンルバランス偏り | career 45% / spiritual 31% / beauty-romance 25% | 中 |
| 6 | 旧スキーマ残骸 | Service 16件, Account 3件 | 低 |

## 決定事項

1. **Entity 後付け抽出バッチが最優先**: Phase 4.5（横断 RELATES_TO）は Entity 層が充実してこそ効果を発揮する。順序は Entity backfill → Phase 4.5 活用。
2. **Source authority_level 一括更新**: URL ドメインから推定するバッチを実装。マッピング: 官公庁→official, 大手メディア→media, ブログ/note→blog, SNS/Reddit→social。

## アクションアイテム

- [ ] Entity 後付け抽出バッチ実装（MENTIONS/コンテンツ比率 0.16→2.0 目標）(優先度: 高)
- [ ] Source authority_level 一括更新バッチ (優先度: 高)
- [ ] 旧スキーマノード整理（Service/Account → Entity 移行 or Archived） (優先度: 低)
- [ ] Story 比率改善（Reddit 体験談検索の強化、10%→20%目標） (優先度: 中)

## 改善の実行順序

```
Step 1: Entity backfill（既存コンテンツにEntity後付け）
    ↓
Step 2: Source authority_level 一括更新
    ↓
Step 3: Phase 4.5 横断 RELATES_TO 実行（Entity増加後に効果大）
    ↓
Step 4: Story 比率改善（次回 enrichment セッション）
    ↓
Step 5: 旧スキーマ整理
```

## 次回の議論トピック

- Entity backfill の実装方式（バッチサイズ、LLMコスト見積もり）
- creator-neo4j のデータを記事執筆にどう活用するかのフロー設計
