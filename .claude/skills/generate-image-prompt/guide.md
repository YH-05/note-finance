# 画像プロンプト生成スキル -- 詳細ガイド

SKILL.md からオフロードした詳細ルール。実装時の参照用。

---

## カテゴリ別スタイルプリセット（詳細）

### macro_economy

- **スタイル**: photorealistic
- **カラートーン**: deep blue, gold accents
- **イメージ方向性**: 中央銀行ビル、都市スカイライン、経済会議、グローバルマップ
- **キーワード例**: central bank building, global economy, city skyline at dusk, world map with financial connections, government institution, policy meeting room
- **ムード**: authoritative, serious, institutional

```
例: Photorealistic image of a grand central bank building at twilight, deep blue sky with golden hour lighting, reflecting pool in foreground, subtle financial data overlay as light bokeh, landscape orientation 1280x670, high quality, detailed, professional, no text, no letters, no words
```

### asset_management

- **スタイル**: flat illustration
- **カラートーン**: warm green, soft blue
- **イメージ方向性**: 成長する植物/木、家族の安心感、コイン/資産の積み上げ
- **キーワード例**: growing tree with coins as leaves, piggy bank, nest egg, stepping stones, garden of wealth, watering can nurturing plants
- **ムード**: warm, approachable, optimistic, nurturing

```
例: Flat illustration style, a lush green tree growing from a pot of golden coins, soft blue sky background, warm green and soft blue color palette, small birds perching on branches, gentle sunlight, landscape orientation 1280x670, high quality, clean design, no text, no letters, no words
```

### stock_analysis

- **スタイル**: conceptual art with data elements
- **カラートーン**: navy blue, teal
- **イメージ方向性**: 企業ビル+チャートオーバーレイ、虫眼鏡で分析、パズルピース
- **キーワード例**: magnifying glass over corporate buildings, puzzle pieces forming a chart, abstract data visualization, corporate headquarters with analytical overlay
- **ムード**: analytical, investigative, precise

```
例: Conceptual art, a large magnifying glass hovering over a modern corporate building, abstract candlestick chart flowing in the background, navy blue and teal color palette, clean geometric shapes, landscape orientation 1280x670, high quality, detailed, professional, no text, no letters, no words
```

### market_report

- **スタイル**: photorealistic
- **カラートーン**: dark blue, red/green accents
- **イメージ方向性**: トレーディングフロア、株価ボード、マーケットの動き
- **キーワード例**: trading floor, stock market displays, financial district at night, market pulse visualization, ticker board
- **ムード**: dynamic, urgent, professional

```
例: Photorealistic image of a modern trading floor with multiple glowing screens, dark blue ambient lighting with red and green accent lights reflecting market movements, dramatic perspective, landscape orientation 1280x670, high quality, cinematic, no text, no letters, no words
```

### side_business

- **スタイル**: flat illustration
- **カラートーン**: orange, purple
- **イメージ方向性**: PC作業、副業イメージ、スタートアップ、複数の収入源
- **キーワード例**: laptop workspace, multiple income streams, creative workspace, side hustle tools, home office with plants
- **ムード**: energetic, creative, entrepreneurial

```
例: Flat illustration style, a vibrant workspace with a laptop at center, multiple floating icons representing different income streams (writing, design, investing), orange and purple color palette, modern and clean composition, landscape orientation 1280x670, high quality, no text, no letters, no words
```

### quant_analysis

- **スタイル**: technical/abstract
- **カラートーン**: dark theme, neon blue/cyan
- **イメージ方向性**: データストリーム、アルゴリズム可視化、数式、ニューラルネットワーク
- **キーワード例**: data stream visualization, algorithm flowchart, neural network nodes, matrix rain, quantum computing aesthetic, code visualization
- **ムード**: futuristic, technical, sophisticated

```
例: Abstract technical visualization on dark background, flowing streams of cyan and neon blue data particles forming a financial network, geometric nodes connected by glowing lines, dark theme with neon blue and cyan accents, landscape orientation 1280x670, high quality, 4k render, no text, no letters, no words
```

### investment_education

- **スタイル**: flat illustration
- **カラートーン**: bright blue, yellow
- **イメージ方向性**: 本/教科書、電球アイコン、ステップバイステップ、初心者が学ぶ姿
- **キーワード例**: open book with lightbulb, stepping stones path, compass pointing forward, friendly guide character, staircase of knowledge
- **ムード**: welcoming, educational, encouraging

```
例: Flat illustration style, an open book with a glowing lightbulb rising from its pages, stepping stones leading upward in the background, bright blue and yellow color palette, friendly and inviting atmosphere, landscape orientation 1280x670, high quality, clean vector style, no text, no letters, no words
```

---

## プロンプト構築ルール

### 構造テンプレート

全プロンプトは以下の構造に従う:

```
[Style description], [Main subject/scene], [Color palette], [Mood/atmosphere], [Composition notes], [Technical specs]
```

各要素の詳細:

| 要素 | 説明 | 例 |
|------|------|-----|
| Style description | カテゴリのスタイルプリセットから取得 | "Photorealistic image", "Flat illustration style" |
| Main subject/scene | 記事テーマを視覚的比喩に変換 | "a central bank building at twilight" |
| Color palette | カテゴリのカラートーンを指定 | "deep blue and gold color palette" |
| Mood/atmosphere | 記事のトーンに基づく雰囲気 | "authoritative and serious atmosphere" |
| Composition notes | 構図の指示 | "centered composition, rule of thirds" |
| Technical specs | サイズ・品質・テキスト禁止 | "landscape orientation 1280x670, high quality, no text, no letters, no words" |

### テキスト禁止指示（必須）

以下のフレーズを全プロンプトの末尾に必ず含める:

```
no text, no letters, no words
```

noteはタイトルを自動で重ねるため、画像内のテキストは不要かつ邪魔になる。

### サイズ指定

| 用途 | サイズ | アスペクト比 | 指定方法 |
|------|--------|-------------|---------|
| noteサムネイル | 1280x670 | 約1.91:1 | "landscape orientation 1280x670" |
| X投稿用 | 1200x675 | 16:9 | "landscape orientation 1200x675, 16:9 aspect ratio" |

### 品質指定

以下のキーワードを適宜使用:

- `high quality` -- 基本（必須）
- `detailed` -- ディテールが重要な場合
- `professional` -- ビジネス系トーン
- `cinematic` -- ドラマチックな雰囲気
- `clean design` -- イラスト系
- `4k render` -- テクニカル/アブストラクト系

---

## テーマの視覚的比喩変換

記事の具体的な対象を、画像プロンプトで使える視覚的比喩に変換する。

### 国・地域の比喩

| 対象 | 視覚的比喩 |
|------|-----------|
| 日本 | cherry blossoms, Mount Fuji silhouette, torii gate, Japanese garden |
| 米国 | Wall Street, New York skyline, American eagle, Statue of Liberty silhouette |
| 中国 | Great Wall motif, dragon symbolism, red and gold palette |
| EU | European architecture, blue and gold stars motif |
| 新興国 | rising sun, growing seedlings, construction cranes |

### 金融概念の比喩

| 概念 | 視覚的比喩 |
|------|-----------|
| 利上げ | ascending staircase, rising arrows, tightening rope |
| 利下げ | descending path, easing waves, opening gates |
| インフレ | expanding balloon, melting ice, rising tide |
| デフレ | shrinking objects, frozen landscape |
| 景気後退 | storm clouds, rough seas, dimming lights |
| 景気拡大 | sunrise, blooming garden, expanding circles |
| 分散投資 | colorful mosaic, diverse garden, balanced scale |
| 複利効果 | snowball rolling downhill, branching tree |
| リスク管理 | shield, umbrella, safety net |
| 市場の暴落 | avalanche, falling dominoes, broken bridge |

### 記事トーンの反映

| トーン | ムード指示 | カラー調整 |
|--------|-----------|-----------|
| ポジティブ | optimistic, warm, hopeful | 明るめ、暖色系を追加 |
| ニュートラル | balanced, objective, calm | カテゴリデフォルト |
| 警告的 | cautious, dramatic, intense | コントラスト強め、赤/オレンジのアクセント |

---

## X投稿用プロンプトの調整ポイント

noteサムネイルをベースに以下を調整:

1. **アイキャッチ力**: `bold`, `eye-catching`, `vibrant`, `high contrast` を追加
2. **構図のシンプル化**: 要素を減らし、中心に1つの強いフォーカルポイント
3. **コントラスト強化**: SNSフィードで目立つようにコントラストを上げる
4. **サイズ変更**: `1200x675, 16:9 aspect ratio`

### 調整例

**noteサムネイル（元）:**
```
Photorealistic image of a grand central bank building at twilight, deep blue sky with golden hour lighting, reflecting pool in foreground, subtle financial data overlay as light bokeh, landscape orientation 1280x670, high quality, detailed, professional, no text, no letters, no words
```

**X投稿用（調整後）:**
```
Photorealistic image of a central bank building facade, bold and dramatic golden hour lighting against deep blue sky, high contrast, vibrant colors, simplified composition with strong focal point, eye-catching for social media, landscape orientation 1200x675, 16:9 aspect ratio, high quality, no text, no letters, no words
```

---

## 季節感の反映

記事の公開時期に合わせた季節モチーフを追加可能:

| 月 | 季節モチーフ |
|----|------------|
| 1-2月 | winter landscape, frost, new year, fresh start |
| 3-4月 | cherry blossoms, spring awakening, new beginnings |
| 5-6月 | lush green, rainy season, growth |
| 7-8月 | summer heat, vibrant colors, tropical |
| 9-10月 | autumn leaves, harvest, warm tones |
| 11-12月 | year-end, holiday lights, reflection |

季節感は「あると良い」程度で、記事テーマとの関連性がある場合のみ使用する。

---

## 特殊ケースの対応

### meta.yaml がない場合

- 記事ディレクトリの構造からカテゴリを推測（ディレクトリ名の第1セグメント）
- article_id は `unknown` とする

### revised_draft.md も first_draft.md もない場合

- ユーザーに「記事ドラフトがありません。ファイルを確認してください」と伝える
- 処理を中断する

### カテゴリがプリセットにない場合

- `investment_education` のプリセット（汎用的なフラットイラスト）をフォールバックとして使用
- ユーザーに「カテゴリ '{category}' のプリセットがないため、デフォルトスタイルを使用します」と通知

### 既存の image_prompts.md がある場合

- ユーザーに「既存の image_prompts.md を上書きしますか?」と確認
- 上書きする場合は新しい `generated_at` で更新

---

## トラブルシューティング

### 症状: プロンプトが長すぎる

**原因**: 要素を詰め込みすぎている

**解決策**:
1. Main subject/scene を1文に絞る
2. 形容詞を3-4個に制限する
3. 補助的な要素は省略する

### 症状: 生成画像にテキストが含まれる

**原因**: "no text" 指定が不十分、またはスタイル記述が曖昧

**解決策**:
1. `no text, no letters, no words, no typography, no writing` と強化する
2. 看板・ボード・スクリーンなどテキストが入りやすい要素を避ける

### 症状: カラーがカテゴリのイメージと合わない

**原因**: カラーパレットの指定が曖昧

**解決策**:
1. 具体的な色コードや色名を使う（例: "deep navy blue #1E3A5F"）
2. "color palette" として明示的にリストする
3. "dominant color" で主要色を強調する
