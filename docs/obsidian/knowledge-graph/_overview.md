# Neo4j 知識グラフ概要

> **同期元**: Neo4j (note-finance)
> **最終同期**: 2026-03-09

---

## グラフ統計

### ノード数

| ラベル | 件数 | 説明 |
|--------|------|------|
| Source | 693 | RSS/記事ソース |
| Claim | 686 | 主張・事実（sentiment付与予定） |
| Entity | 72 | 企業・人物・概念 |
| Memory | 28 | プロジェクト記憶ノード |
| ActionItem | 23 | タスク・TODO |
| Decision | 17 | 決定事項 |
| Topic | 16 | トピック分類 |
| Concept | 10 | 投資概念（NISA等） |
| Discussion | 8 | 議論記録 |
| FinancialProduct | 7 | 金融商品 |
| CandidateTheme | 6 | DB型候補テーマ |
| EmbeddableResource | 6 | 埋め込みリソース |
| Document | 4 | 参照ドキュメント |
| MonetizationModel | 4 | 収益化モデル |
| ExperiencePattern | 3 | 体験談パターン |
| その他 | 15 | Organization, ContentPolicy, etc. |
| **合計** | **約1,598** | |

### 主要リレーション

| リレーション | 件数 | 説明 |
|-------------|------|------|
| TAGGED | 825 | Source→Topic |
| MAKES_CLAIM | 694 | Source→Claim |
| ABOUT | 380 | Claim→Entity |
| PRODUCED | 27 | Discussion→ActionItem/etc |
| RESULTED_IN | 15 | Discussion→Decision |
| IMPLEMENTS | 12 | →Concept |
| COVERS | 10 | Article→Concept |

## 4層アーキテクチャ（設計済・実装待ち）

```
Layer 3: 知見発見
  Narrative, Insight, Signal
  ↑
Layer 2: 時系列集約
  TimePeriod, EntitySnapshot, TopicSnapshot
  ↑
Layer 1: 構造化メタデータ
  Claim (sentiment/claim_type拡張), Sector, Industry
  ↑
Layer 0: 基盤（現在）
  Source, Claim, Entity, Topic, FinancialProduct, ...
```

## ドメイン別グラフ

### 金融ドメイン
- Source(693) → MAKES_CLAIM → Claim(686) → ABOUT → Entity(72)
- Source → TAGGED → Topic(16)
- FinancialProduct(7) → ELIGIBLE_FOR → Concept(NISA等)

### 副業プロジェクトドメイン
- Project → HAS_DISCUSSION → Discussion(8)
- Discussion → RESULTED_IN → Decision(17)
- Discussion → PRODUCED → ActionItem(23)
- Project → HAS_THEME_CANDIDATE → CandidateTheme(6)
- ExperiencePattern(3) → EMBEDS → EmbeddableResource(6)

### プラットフォームドメイン
- Platform(note.com, X) → DRIVES_TRAFFIC_TO
- Competitor(3) → ACTIVE_ON → Platform
- MonetizationModel(4): 有料記事, メンバーシップ, 定期マガジン, tip

## 未実装の予定拡張

1. **Claim sentiment付与**: 686件にsentiment(-1.0〜1.0)とclaim_type(12種)を追加
2. **TimePeriod導入**: 週次/月次の時間軸ノード
3. **Sector/Industry**: Entity(72件)にセクター・業界情報を追加
4. **EntitySnapshot**: 週次のエンティティ状態スナップショット
5. **Narrative/Insight/Signal**: AI自動生成の知見レイヤー

## 関連リンク

- [[../_dashboard|全体ダッシュボード]]
- [[../sidebusiness/_discussions#Neo4jスキーマ設計|スキーマ設計議論]]
