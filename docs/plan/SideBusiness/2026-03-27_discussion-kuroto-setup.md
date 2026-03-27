# 議論メモ: 玄人領域 管理フォルダ作成 & 投稿スケジュール確定

**日付**: 2026-03-27
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-27-kuroto-setup
**前提**: disc-2026-03-27-selfdev-persona-design で確定したペルソナ設計

---

## 決定事項

### dec-2026-03-27-kuroto-001
**管理フォルダ構成確定**

`creator/kuroto_area/` に以下のファイル・ディレクトリを作成:

```
creator/kuroto_area/
├── persona.md           # ペルソナ定義（bio・トーン・NG・4本柱・収益化導線）
├── posting_algorithm.md # 投稿スケジューリングアルゴリズム
├── posting_state.json   # 状態管理（投稿数・テーマ消化・素材使用履歴）
├── drafts/              # 投稿ドラフト格納
└── templates/           # 投稿テンプレート格納
```

career_sister・みつきと同じ構造で3ブランドを完全独立管理。

### dec-2026-03-27-kuroto-002
**Threads 投稿スケジュール確定（5スロット × 7日 = 35投稿/週）**

| スロット | 時間 | カテゴリ | 毎日 |
|---------|------|---------|------|
| S1 | 07:30 | 哲学的基盤 | 毎日 |
| S2 | 12:00 | 思考フレームワーク | 毎日 |
| S3 | 18:00 | 海外メソッド翻訳 | 毎日 |
| S4 | 20:00 | 内向型戦略 | 毎日 |
| S5 | 21:30 | 書籍紹介（月・水・金）/ 補強（火・木・土）/ note誘導（日） | 7日サイクル |

カテゴリ比率: 哲学20% / FW20% / 海外メソッド20% / 内向型20% / 書籍9% / 補強9% / note誘導3%

### dec-2026-03-27-kuroto-003
**アカウント名最終確定**

- **表示名**: 玄人領域｜静かに強くなる思考の技術
- **ユーザーネーム**: @kuroto_area
- **Threadsアカウント開設**: 完了
- **bio入力**: 完了（Threads用・note用）

**アカウント名選定経緯**:
第一原理思考（既存・イーロンマスク）→ 原点思考（既存）→ 韓非思考（人物に縛られる）→ 玄人領域（確定）
「玄人（くろうと）」の知的な響き + 「領域」のブランディング感。完全オリジナル造語。

---

## 完了済みアクションアイテム

- [x] **act-2026-03-27-selfdev-pd001** Threadsアカウント開設（玄人領域｜静かに強くなる思考の技術）
- [x] **act-2026-03-27-selfdev-pd002** プロフィール画像作成（アーストーン・石/木テクスチャ系）
- [x] **act-2026-03-27-selfdev-pd003** noteアカウント開設 + プロフィール設定
- [x] **act-2026-03-27-selfdev-s001** self-devアカウントのペルソナ設計確定
- [x] **act-2026-03-27-selfdev-nc004** ペルソナ設計（アカウント名・bio・ビジュアルトーン）

---

## 次回アクションアイテム

- [ ] **act-2026-03-27-kuroto-001** creator-neo4jのTip/Story/Factから初期70投稿を一括生成（/kuroto-draft コマンド作成含む）(優先度: 高)
- [ ] **act-2026-03-27-kuroto-002** 無料note記事#1「習慣スタッキング」執筆（3000字、James Clear軸、Amazonアフィリ2箇所）(優先度: 高)
- [ ] **act-2026-03-27-kuroto-003** Amazon Associates申請（書籍アフィリ運用の前提条件）(優先度: 高)

---

## 現在の投稿状態

- total_posts: 0（未投稿）
- note_mode: free（無料モード）
- note_paid_threshold: 10（10本公開後に有料開設）

---

## 関連ドキュメント

- ペルソナ設計: `2026-03-27_discussion-selfdev-persona-design.md`
- noteコンテンツ設計: `2026-03-27_discussion-selfdev-note-content-design.md`
- 収益化戦略: `2026-03-27_discussion-selfdev-monetization-strategy.md`
- 収益化ゴール: `2026-03-27_discussion-selfdev-monetization-goals.md`
