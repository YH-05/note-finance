# 議論メモ: self-devアカウント noteコンテンツ設計

**日付**: 2026-03-27
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-27-selfdev-note-content-design
**前提**: disc-2026-03-27-selfdev-monetization-strategy で確定した収益化戦略

---

## 背景・コンテキスト

- 収益化ゴール・5スロット設計・KPIロードマップは前セッションで確定済み
- 本セッション: noteコンテンツの「質向上」方針を設計
  - 売り出しポイント（なぜメンバーになるか）
  - 何を書くか（ネタの選定方法）
  - Amazonアフィリの自然な組み込み
  - creator-neo4jを活用した次記事選定ロジック

---

## 決定事項

### dec-2026-03-27-selfdev-nc001
**noteの売り出しポイント: 「実行可能なシステムと哲学的土台を両方提供する」**

- 自己啓発の2大弱点「感情論で終わる」「すぐ忘れる」を解決
- Threads = 気づき提供（無料）、note = 実装ガイド提供（有料）の棲み分け
- 「読んで終わり」ではなく「読んだ翌日に使えるFW」を毎回提供

### dec-2026-03-27-selfdev-nc002
**ネタ選定ロジック: Concept充実度ランキング × 接続マップ × 著者Entity**

creator-neo4jから以下の3軸でネタを選定する（ランダム禁止）:

**軸1: Concept充実度ランキング（優先テーマ一覧）**

| Concept | 件数 | 優先度 |
|---------|------|--------|
| 習慣スタッキング | 6 | 最高（記事化1番目） |
| 2分間ルール | 3 | 高 |
| ストイシズム | 3 | 高 |
| ポモドーロテクニック | 3 | 高 |
| 制御二分法 | 2 | 中 |
| Deep Work | 2 | 中 |
| モーニングルーティン | 2 | 中 |

**軸2: 著者Entity紐づけ（ブランド強度の高いソース）**

| 著者 | 件数 | 推奨テーマ |
|------|------|-----------|
| James Clear | 10 | Atomic Habits系（習慣/2分ルール/スタッキング） |
| Cal Newport | 6 | Deep Work/Digital Minimalism |
| Andrew Huberman | 6 | 睡眠最適化/朝のルーティン |
| Kristin Neff | 5 | セルフコンパッション（内向型層に刺さる） |
| Epictetus | 5 | ストア派制御二分法 |

**軸3: Concept接続マップ（シリーズ設計用）**

```
習慣スタッキング → モーニングルーティン（ENABLES）
2分間ルール → Tiny Habits（RELATES_TO）
ポモドーロテクニック → Deep Work（ENABLES）
制御二分法 → ストイシズム（RELATES_TO）
セルフコンパッション → 内向型（RELATES_TO）
```

### dec-2026-03-27-selfdev-nc003
**無料note初回10本ロードマップ（変容ジャーニー設計）**

読者が「気づき → 行動 → 哲学 → 内面 → 環境 → 統合」の変容を体験する順序で公開:

| # | タイトル案 | 主Concept | 軸 | 字数 |
|---|----------|-----------|---|------|
| 1 | 2分でいい。習慣スタッキングが自己改造を加速する理由 | 習慣スタッキング | James Clear | 3000 |
| 2 | 「やる気待ち」は科学的に間違いだった。2分ルールの神経科学 | 2分間ルール | James Clear | 2500 |
| 3 | B=MAP理論: Foggが証明した「行動が起きる唯一の条件」 | Tiny Habits | BJ Fogg | 2500 |
| 4 | Huberman式モーニングルーティン — 朝90分で1日のパフォーマンスが決まる | モーニングルーティン | Huberman | 3000 |
| 5 | ストア派の制御二分法: 悩み続けることを今日やめる | 制御二分法 | Epictetus | 2500 |
| 6 | Deep Workとは何か。なぜ4時間の深い集中が人生を変えるのか | Deep Work | Cal Newport | 3000 |
| 7 | 完璧主義という名の先延ばし — 内向型がはまる最大の罠 | セルフコンパッション | Kristin Neff | 2500 |
| 8 | 環境設計の科学: 意志力を使わずに行動を変える | 環境デザイン | BJ Fogg / Clear | 2500 |
| 9 | ポモドーロ × Deep Work: 集中力を設計するシステム | ポモドーロ | Newport / Cirillo | 2000 |
| 10 | 静かな自己改造の全体像: 哲学・行動・環境の統合フレームワーク | 統合 | 全体 | 4000 |

### dec-2026-03-27-selfdev-nc004
**Amazonアフィリエイト自然組み込みパターン（2箇所配置）**

**配置1: 本文中（出典として）**
```
2分ルールを最初に提唱したのは James Clear です。彼の著書
『Atomic Habits（[Amazon](https://www.amazon.co.jp/dp/XXXX)）』
では、習慣の4ステップ（cue→craving→response→reward）として…
```

**配置2: 記事末尾（参考文献セクション）**
```markdown
## 参考文献・おすすめ書籍

この記事を書くにあたって参考にした本です。より深く学びたい方へ:

- [Atomic Habits](https://www.amazon.co.jp/dp/XXXX) — James Clear
  → 習慣の科学を最も体系的に解説。本記事の主要ソース
- [Tiny Habits](https://www.amazon.co.jp/dp/XXXX) — BJ Fogg
  → 2分ルールの科学的根拠。Atomic Habitsの補完的一冊
```

**ルール**:
- 記事1本につきAmazonリンクは2-3冊まで（詰め込まない）
- Tier 1（Atomic Habits/Deep Work/自省録/Quiet）は繰り返し登場させてOK
- Threadsではコメント欄にリンクを貼る（本文ER低下防止）

---

## アクションアイテム

- [ ] **act-2026-03-27-selfdev-nc001** Cypherクエリでself-dev Conceptを習慣スタッキング→2分ルール→ストイシズム順にフルリスト取得 (優先度: 高)
- [ ] **act-2026-03-27-selfdev-nc002** 無料note記事#1「習慣スタッキング」の初稿執筆（3000字、James Clear軸、アフィリ2箇所） (優先度: 高)
- [ ] **act-2026-03-27-selfdev-nc003** Amazon Associates申請（書籍アフィリ運用の前提条件） (優先度: 高)
- [ ] **act-2026-03-27-selfdev-nc004** self-devアカウントのペルソナ設計（アカウント名・自己紹介文・プロフ画像トーン） (優先度: 高)
- [ ] **act-2026-03-27-selfdev-nc005** Threads初期70投稿の一括ドラフト（creator-neo4jのTip/Story/Factから変換） (優先度: 中)

---

## 次回の議論トピック

- ペルソナ確定（アカウント名・bio・ビジュアルトーン）
- Threads初期70投稿の実際の生成フロー
- note記事#1「習慣スタッキング」の執筆・公開

---

## 関連ドキュメント

- 収益化ゴール: `2026-03-27_discussion-selfdev-monetization-goals.md`
- 収益化戦略プラン: `2026-03-27_discussion-selfdev-monetization-strategy.md`
- creator-neo4j初期投入: `2026-03-27_discussion-self-dev-creator-research.md`
- 3ブランド役割分割: `2026-03-27_discussion-3brand-role-design.md`
