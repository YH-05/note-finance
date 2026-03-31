# 玄人領域 投稿スケジューリングアルゴリズム

## 概要

**1日5投稿（Threads） + 1日1本note（7本/週）** の半自動パイプライン。
7日サイクル制で4本柱+書籍紹介の比率を保証し、5スロットで投稿タイミングを管理する。

## 1. 日次スロット設計（5投稿/日）

| スロット | 時間 | カテゴリ | 狙い |
|---------|------|---------|------|
| S1 | 07:30 | 哲学的基盤 | 朝の思索層をキャッチ。ストア派一日一言 |
| S2 | 12:00 | 思考フレームワーク | 昼休みの生産性関心層。FW・メソッド紹介 |
| S3 | 18:00 | 海外メソッド翻訳 | 帰宅途中の自己投資層。Huberman/Newport等 |
| S4 | 20:00 | 内向型戦略 | 夜のリフレクション層。変革Story + 共感フック |
| S5 | 21:30 | 書籍紹介（週2-3回） / 補強投稿 | 就寝前の読書層 + Amazon収益 |

## 2. 7日サイクル（35投稿/週）

| 曜日 | S1(7:30) | S2(12:00) | S3(18:00) | S4(20:00) | S5(21:30) |
|------|----------|-----------|-----------|-----------|-----------|
| 月 | 哲学 | FW | 海外メソッド | 内向型Story | 書籍紹介 |
| 火 | 哲学 | FW | 海外メソッド | 内向型Story | 補強(FW深掘り) |
| 水 | 哲学 | FW | 海外メソッド | 内向型Story | 書籍紹介 |
| 木 | 哲学 | FW | 海外メソッド | 内向型Story | 補強(哲学深掘り) |
| 金 | 哲学 | FW | 海外メソッド | 内向型Story | 書籍紹介 |
| 土 | 哲学 | FW | 海外メソッド | 内向型Story | 補強(海外深掘り) |
| 日 | 哲学 | FW | 海外メソッド | 内向型Story | note誘導 |

カテゴリ比率（35投稿/週）:
- 哲学的基盤: 7本（20%）— S1毎日
- 思考FW: 7本（20%）— S2毎日
- 海外メソッド: 7本（20%）— S3毎日
- 内向型戦略: 7本（20%）— S4毎日
- 書籍紹介: 3本（9%）— S5（月・水・金）
- 補強投稿: 3本（9%）— S5（火・木・土）
- note誘導: 1本（3%）— S5（日）

## 3. 投稿テンプレート（PAS構成ベース）

```
[感情フック 1-2行]
↓
[問題の増幅 2-3行]
↓
[解決策: Tip/Skill/FW 3-5行]
↓
[行動の第一歩 1行]
```

## 4. テーマ選択アルゴリズム

### 4.1 ネタ選定ロジック（3軸）

ランダム選択は禁止。以下の3軸で選定する:

**軸1: Concept充実度ランキング**
creator-neo4j から充実度順にConceptを取得し、上位から消化。

**軸2: 著者Entity紐づけ**
James Clear / Cal Newport / Huberman / Epictetus 等の著者Entityで権威性担保。

**軸3: Concept接続マップ**
ENABLES / RELATES_TO リレーションで関連Conceptをシリーズ化。

### 4.2 哲学テーマ

ストア派の教えから巡回選択（重複排除付き）。

```python
STOIC_THEMES = [
    {"id": "PH1", "concept": "制御二分法", "author": "Epictetus", "weight": 1.2},
    {"id": "PH2", "concept": "memento mori", "author": "Marcus Aurelius", "weight": 1.0},
    {"id": "PH3", "concept": "premeditatio malorum", "author": "Seneca", "weight": 1.0},
    {"id": "PH4", "concept": "amor fati", "author": "Marcus Aurelius", "weight": 0.8},
    {"id": "PH5", "concept": "virtue ethics", "author": "Epictetus", "weight": 0.8},
]
```

### 4.3 思考FWテーマ

```python
FW_THEMES = [
    {"id": "FW1", "concept": "習慣スタッキング", "author": "James Clear", "weight": 1.2},
    {"id": "FW2", "concept": "2分間ルール", "author": "James Clear", "weight": 1.0},
    {"id": "FW3", "concept": "ポモドーロテクニック", "author": "Francesco Cirillo", "weight": 1.0},
    {"id": "FW4", "concept": "Deep Work", "author": "Cal Newport", "weight": 1.0},
    {"id": "FW5", "concept": "意思決定バイアス", "author": "Daniel Kahneman", "weight": 0.8},
]
```

### 4.4 海外メソッドテーマ

```python
METHOD_THEMES = [
    {"id": "MT1", "concept": "睡眠最適化", "author": "Andrew Huberman", "weight": 1.0},
    {"id": "MT2", "concept": "Digital Minimalism", "author": "Cal Newport", "weight": 1.0},
    {"id": "MT3", "concept": "Tiny Habits", "author": "BJ Fogg", "weight": 1.0},
    {"id": "MT4", "concept": "Reverse Engineering", "author": "Ron Friedman", "weight": 0.8},
    {"id": "MT5", "concept": "セルフコンパッション", "author": "Kristin Neff", "weight": 0.8},
]
```

### 4.5 内向型Storyテーマ

```python
INTRO_THEMES = [
    {"id": "IN1", "concept": "社会的比較", "keywords": ["常に他人より遅れてる"], "weight": 1.2},
    {"id": "IN2", "concept": "完璧主義の罠", "keywords": ["先延ばし", "動けない"], "weight": 1.0},
    {"id": "IN3", "concept": "モチベーション依存", "keywords": ["やる気待ち", "夜にやる気爆発"], "weight": 1.0},
    {"id": "IN4", "concept": "青春の後悔", "keywords": ["18歳の後悔", "遅れて始めた"], "weight": 0.8},
    {"id": "IN5", "concept": "環境デザイン", "keywords": ["意志力不要", "仕組み化"], "weight": 0.8},
]
```

## 5. 素材 ↔ 型のマッピング

| スロット | 優先素材タイプ | 理由 |
|---------|--------------|------|
| S1 哲学 | Fact + Tip | 哲学的知見 + 実践的解釈 |
| S2 FW | Tip | 具体的なフレームワーク手順 |
| S3 海外メソッド | Fact + Tip | 科学的知見 + 実践方法 |
| S4 内向型 | Story | 変革体験 + 共感フック |
| S5 書籍 | Fact | 書籍の要点・名言 |

素材選択時の重複排除:
- `used_material_ids` に記録済みの素材は除外
- 全素材の70%使用済みでリセット（再利用可能に）

## 6. 状態管理

`posting_state.json` で全状態を管理。

## 7. 素材枯渇予測

5投稿/日 × 7日 = 35投稿/週

- Fact: 117件 → 約16週分
- Tip: 74件 → 約10週分
- Story: 55件 → 約8週分

**補充推奨タイミング**: `used_material_ids` の消化率が70%を超えたら `/creator-research` 実行。

## 8. 将来拡張

Phase 2 で実装予定:
```
投稿24h後 → エンゲージメントメトリクス取得
  → カテゴリ × 型 × テーマのパフォーマンスマトリクス構築
  → 高パフォーマンス組み合わせの重みを上げる
  → note記事へのコンバージョン率トラッキング
  → メンバーシップ開設タイミング判定
```
