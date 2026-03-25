# 議論メモ: キャリアお姉さん データソース拡張・ドラフト更新

**日付**: 2026-03-25
**参加**: ユーザー + AI
**前提**: disc-2026-03-25-career-sister-content-value の決定事項に基づく実装

## 背景・コンテキスト

コンテンツ価値分析で「有益投稿の定義をデータ駆動に変更」「テーマ T9/T10 追加」「型5 追加」が決定。
本セッションではその実装として、データ収集基盤の拡張・素材投入・既存ドラフトの書き換えを実施した。

## 実施内容

### 1. creator-neo4j に転職市場データ投入（10 Fact）

| Fact | ソース | データ |
|------|--------|--------|
| doda 求人倍率 | doda.jp | 2026年2月: 2.40倍、IT・通信 前月比102.4% |
| 2026上半期予測 | doda.jp | 15業界中9分野で求人増加 |
| 30代年収アップ率 | マイナビ転職 | 54%が年収アップ、平均+138.7万円 |
| 業種別年収アップ | マイナビ転職 | IT・インターネット43%で最多 |
| CS平均年収 | cs-tenshoku.com | 543万円、未経験歓迎多数 |
| 職種別年収ランキング | マイナビ転職 | 経営戦略コンサル1,410万円、ITコンサル700-1,000万円 |
| SaaS企業年収 | Geekly | TOP5全社800万円以上 |
| 転職率 | マイナビ+厚労省 | 7.6%（30代9.0%） |
| 30代成功事例 | マイナビ転職 | 会計→経理+80万、マーケ→企画800→1,100万 |
| CS未経験転職 | JAC | 飲食・小売からの転職者も活躍中 |

### 2. 既存ドラフト6本をデータ駆動型に書き換え

| 日 | スロット | 変更 | 埋め込んだデータ |
|----|---------|------|---------------|
| 水夜 | 型4→型5 | doda求人倍率2.40倍 + 業界別求人増加 |
| 金昼 | 型4→型5 | 30代年収アップ54%、平均+138.7万円 |
| 日昼 | 型4→型5 | 職種別年収ランキング、SaaS vs SIer比較 |
| 木朝 | 型3+データ | 年収交渉失敗談 + 「+10%が相場」 |
| 日朝 | 型2+データ | CS職543万円、未経験OK |
| 火夜 | 型2+データ | 転職率7.6%、求人倍率2.40倍 |

### 3. enrichment config 拡張

| カテゴリ | Before → After |
|---------|----------------|
| webfetch_sites | 5 → 22件（+17: doda, マイナビ, type, リクナビNEXT, OpenWork, キャリアガーデン, Geekly, レバテック, JAC, 厚労省, JILPT, Wantedly, ビズリーチ） |
| subreddits | 8 → 15件（+7: CustomerSuccess, SaaS, overemployed, japanlife, JapanFinance, ExperiencedDevs, ITCareerQuestions） |
| note.com creators | 1 → 6名（+5: そうた, けい, Career Compass, 高橋良平, みらいキャリア） |
| tavily_queries_en | 11 → 17件（+6: CS職, SaaS市場, Japan特化, テック転職, コンサル比較） |

## 決定事項

1. **enrichment config 拡張**: 転職メディア・公的統計・IT特化エージェントをwebfetch対象に追加
2. **ドラフト書き換え方針**: 型4→型5変換を優先、既存型にもデータを埋め込む

## アクションアイテム

- [x] creator-neo4j に転職市場データ10 Fact投入（優先度: 高）
- [x] 既存ドラフト6本をデータ駆動型に書き換え（優先度: 高）
- [x] enrichment config大幅拡張（優先度: 高）
- [ ] 拡張後の /creator-enrichment 実行と新規ソース検証（優先度: 中）
- [ ] Phase 2 有料マガジン「転職ルート別ガイド」の商品設計（優先度: 低）

## 次回の議論トピック

- `/creator-enrichment` 実行後の収集品質評価
- 型5投稿のエンゲージメント計測（Threads Insights API）
- Phase 2 有料マガジンの具体的なコンテンツ設計
- 転職市場データの自動更新パイプライン（月次 doda レポート取得等）

## 変更ファイル一覧

- `creator/career_sister/persona.md` — コア主張「データで語る」追加、有益投稿定義変更、型5追加
- `creator/career_sister/posting_algorithm.md` — T9/T10テーマ追加、型ローテーション更新
- `.claude/skills/career-sister-writer/SKILL.md` — 型5定義、コア主張7追加
- `data/config/creator-enrichment-config.json` — 全カテゴリ拡張
- `data/config/note-com-creators.json` — クリエイター5名追加
- `drafts/week_2026-03-24/` — 6本のthreads_post.md書き換え + meta.json更新
