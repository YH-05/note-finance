# 画像プロンプト生成スキル -- 詳細ガイド

SKILL.md からオフロードした詳細ルール。実装時の参照用。

---

## ブランドガイドライン（全カテゴリ共通）

noteアカウント全体で「同じギャラリーの作品」としてのビジュアル統一感を持たせる。
基本スタイルは**抽象画（油彩/アクリル）**。具体物は描かず、色・形・動きで記事の本質を表現する。

### 共通スタイル基盤

全カテゴリで **abstract painting** を基本スタイルとする。
写真、イラスト、3Dレンダー、デジタルアートは使用しない。

### 共通ビジュアルシグネチャ（全プロンプト必須）

| 要素 | プロンプト記述 | 効果 |
|------|-------------|------|
| 背景 | `deep charcoal black background` | 暗い背景で色彩を最大限に際立たせる |
| テクスチャ | `thick impasto brushstrokes with visible palette knife texture` | 絵画の物質感。AI生成のツルツル感を回避 |
| ゴールド | `metallic gold accents` or `flecks of metallic gold` | ブランド共通のアクセント。高級感と統一性 |
| メディウム | `oil on canvas texture` | キャンバスの質感で「美術作品」としての存在感 |

### AI生成っぽさを回避するための必須テクスチャ指定

以下のいずれかを必ず含めること（複数可）:

- `thick impasto` — 厚塗り
- `palette knife texture` — パレットナイフの跡
- `visible brushwork` — 筆跡が見える
- `drips running downward` — 下方に垂れるペイント
- `cracking and layered depth` — ひび割れと層の深み
- `splatters` — 飛沫

これらが「本物の油絵」感を出し、AIが生成しがちな滑らかで均一な表面を防ぐ。

### 共通禁止語（AI臭くなる語）

- `smooth`, `clean`, `polished`, `glossy`
- `digital art`, `3D render`, `CGI`, `vector`
- `photorealistic`, `photograph`, `camera`
- `neon`, `glowing`, `holographic`
- `futuristic`, `sci-fi`

---

## カテゴリ別カラープリセット（詳細）

全カテゴリが抽象画ベース。差別化はカラーパレットと動勢（ストロークの方向性）で行う。

### macro_economy

- **カラー**: deep blue + gold + touches of dark grey
- **動勢**: 水平に広がる大きな面。重厚でゆったりした動き
- **参照**: Mark Rothko (色面の深み), Robert Motherwell (大胆な黒と色の対比)
- **ムード**: authoritative, contemplative, monumental

```
例: Abstract painting in the style of Mark Rothko, two vast horizontal bands of deep blue and dark gold floating on a charcoal black background, thick impasto with subtle texture variations across the surface, edges of the color fields are soft and breathing, flecks of metallic gold scattered along the boundary where blue meets gold, oil on canvas texture with layered depth, contemplative and monumental atmosphere, landscape 1280x670, no text, no letters, no words
```

### asset_management

- **カラー**: warm green + earth tones (sienna, ochre) + soft gold
- **動勢**: 下から上へ有機的に成長する。植物の生長のような自然な上昇
- **参照**: Helen Frankenthaler (染み込む色彩), Claude Monet (late abstract waterlilies)
- **ムード**: organic, nurturing, steady growth

```
例: Abstract painting inspired by Helen Frankenthaler, organic warm green forms rising upward from the bottom of the canvas, earth tone washes of sienna and ochre bleeding into each other, soft gold veins branching through the composition like roots growing, deep charcoal background visible at the edges, thick impasto texture in the central growth area thinning to transparent washes at the periphery, metallic gold leaf accents, oil on canvas, landscape 1280x670, no text, no letters, no words
```

### stock_analysis

- **カラー**: navy blue + teal + silver + white
- **動勢**: 鋭い対角線が交差する。切れ味のある分析的な動き
- **参照**: Franz Kline (力強い黒のストローク), Pierre Soulages (黒の光)
- **ムード**: precise, sharp, investigative

```
例: Abstract painting in the spirit of Franz Kline, bold diagonal strokes of navy blue and teal crossing each other at sharp angles on a deep black background, silver-white lines cutting through the composition with precision, thick impasto where the strokes intersect creating ridges of paint, palette knife scrapes revealing layers beneath, metallic gold flecks at the intersection points, oil on canvas with visible texture, landscape 1280x670, no text, no letters, no words
```

### market_report

- **カラー**: dark blue + red + green + gold
- **動勢**: 力強い水平の衝突。二つの力がぶつかり合う緊張感
- **参照**: Willem de Kooning (激しいジェスチャー), Hans Hartung (書のような動き)
- **ムード**: dynamic, urgent, tension between opposing forces

```
例: Abstract expressionist painting in the energy of de Kooning, aggressive horizontal strokes of red and green colliding in the center of a dark blue-black canvas, thick impasto paint piled up at the collision point, palette knife drags creating texture, paint drips running downward from the impact zone, splatters of metallic gold marking the point of maximum tension, oil on canvas with cracking texture, landscape 1280x670, no text, no letters, no words
```

### side_business

- **カラー**: amber + violet + teal + gold
- **動勢**: 複数の流れが一点に収束する。多方向からのエネルギーの合流
- **参照**: Wassily Kandinsky (動的構成), Zaha Hadid (流線的な曲線)
- **ムード**: energetic, convergent, multidirectional momentum

```
例: Abstract painting in the style of Wassily Kandinsky meets Zaha Hadid, three bold sweeping curves in amber, violet, and teal converging toward a single bright focal point at the center, thick impasto brushstrokes with visible palette knife texture, the three streams originate from different corners of the canvas and intertwine as they approach the center, splatters of metallic gold paint at the intersection, deep charcoal black background making the colors pop, oil on canvas texture with cracking and layered depth, landscape 1280x670, no text, no letters, no words
```

### quant_analysis

- **カラー**: cool blue + cyan + black + silver
- **動勢**: 精密な幾何学パターン。秩序と構造
- **参照**: Piet Mondrian (幾何学的秩序), Victor Vasarely (光学的深度)
- **ムード**: systematic, precise, mathematical beauty

```
例: Abstract geometric painting inspired by Mondrian and Vasarely, a grid of cool blue and cyan rectangles of varying sizes on a deep black background, some rectangles filled with thick impasto paint, others with transparent washes revealing the dark canvas beneath, thin silver lines delineating the grid structure, metallic gold accent in one focal rectangle, oil on canvas with precise palette knife edges but organic paint texture within each cell, landscape 1280x670, no text, no letters, no words
```

### investment_education

- **カラー**: warm gold + cream + soft blue + white
- **動勢**: 中心から外側へ柔らかく展開する。光が広がるような動き
- **参照**: J.M.W. Turner (光の抽象化), Mark Rothko (暖色面)
- **ムード**: illuminating, inviting, gradual revelation

```
例: Abstract painting inspired by Turner's luminous abstractions, a warm golden light expanding outward from the center of the canvas, soft blue and cream tones blending at the edges, the gold area has thick impasto texture suggesting warmth and substance, the outer regions fade to deeper tones with visible brushwork, metallic gold highlights at the bright core, deep charcoal visible only at the far corners, oil on canvas with layered translucent glazes, landscape 1280x670, no text, no letters, no words
```

---

## テーマ→抽象モチーフ変換ガイド

記事の内容を具体物ではなく、**動勢・エネルギー・色の関係性**として翻訳する。

### 記事構造と動勢の対応

| 記事の構造 | 抽象的な動勢 | ストローク表現 |
|-----------|------------|-------------|
| 比較・対立 | 二つの色面がぶつかる | 水平の衝突、対角線の交差 |
| 成長・蓄積 | 下から上へ有機的に伸びる | 上昇する曲線、層の積み重ね |
| 分散・多角化 | 中心から放射状に広がる | 放射線、スプラッタ |
| 収束・統合 | 複数の流れが一点に集まる | 曲線の収束、渦 |
| 段階・プロセス | 左から右へ変化する | グラデーション、段階的な色変化 |
| 危機・警告 | 激しい衝突と飛散 | 荒いストローク、ドリップ、スプラッタ |
| 安定・安心 | 水平な色面が静かに存在する | ロスコ的な色面、柔らかい境界 |

### テーマ数とカラー対応

| 記事の要素数 | カラー構成 |
|------------|----------|
| 単一テーマ | メインカラー1色 + ゴールドアクセント |
| 2つの対比 | 2色の対比 + ゴールド |
| 3つの要素 | 3色の流れ + ゴールド |
| 多要素 | グラデーションまたは幾何学パターン |

### 記事トーンとテクスチャの対応

| トーン | テクスチャ・ストロークの性質 |
|--------|------------------------|
| ポジティブ | 流麗で滑らかな曲線、明るいハイライト |
| ニュートラル | バランスのとれた配置、均等な質感 |
| 警告的 | 荒いストローク、ドリップ、深い影 |
| 教育的 | 柔らかいグラデーション、展開する光 |

---

## X投稿用プロンプトの調整ポイント

noteサムネイルをベースに以下を調整:

1. **要素の削減**: 構成をシンプルにし、1つの大胆なジェスチャーに集中
2. **コントラスト強化**: 色の対比をより強く、背景をより暗く
3. **抽象表現主義的な爆発力**: "bold", "explosive", "raw", "powerful" を追加
4. **サイズ変更**: `1200x675, 16:9 aspect ratio`

### 調整例

**noteサムネイル（元）:**
```
Abstract painting in the style of Wassily Kandinsky meets Zaha Hadid, three bold sweeping curves in amber, violet, and teal converging toward a single bright focal point at the center, thick impasto brushstrokes with visible palette knife texture, the three streams originate from different corners of the canvas and intertwine as they approach the center, splatters of metallic gold paint at the intersection, deep charcoal black background, oil on canvas texture with cracking and layered depth, landscape 1280x670, no text, no letters, no words
```

**X投稿用（調整後）:**
```
Bold abstract expressionist painting, a single explosive burst of three colors — amber, violet, and teal — radiating outward from the center of a deep black canvas, thick impasto oil paint with heavy texture and visible brushwork, the three colors swirl and collide creating energy at the core with flecks of metallic gold, raw and powerful composition, oil paint texture with drips running downward, landscape 1200x675 16:9, no text, no letters, no words
```

---

## 季節感の反映

季節モチーフは抽象的な色温度の調整で表現する（具体物は描かない）:

| 月 | 色温度の調整 |
|----|------------|
| 1-2月 | クールトーン強め、白のハイライト、霜のような薄い層 |
| 3-4月 | ピンク〜淡い桜色のアクセント、柔らかい光の質感 |
| 5-6月 | 深い緑のウォッシュ、水のような透明レイヤー |
| 7-8月 | 暖色を強め、黄色のハイライト、熱のバイブレーション |
| 9-10月 | オレンジ・赤茶のアクセント、深みのある暖色 |
| 11-12月 | 暗めの全体トーン、わずかなゴールドの温もり |

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

- `investment_education` のプリセット（暖色系の拡散する光）をフォールバックとして使用
- ユーザーに「カテゴリ '{category}' のプリセットがないため、デフォルトカラーを使用します」と通知

### 既存の image_prompts.md がある場合

- ユーザーに「既存の image_prompts.md を上書きしますか?」と確認
- 上書きする場合は新しい `generated_at` で更新

---

## トラブルシューティング

### 症状: AI生成っぽいツルツルした表面になる

**原因**: テクスチャ指定が不十分

**解決策**:
1. `thick impasto` と `palette knife texture` を強調
2. `cracking`, `drips`, `splatters` など不完全さを追加
3. `oil on canvas` を明記
4. 禁止語リスト（smooth, clean, digital art 等）に該当する語がないか確認

### 症状: 具体的なオブジェクトが生成される

**原因**: プロンプト内に具体物を連想させる記述がある

**解決策**:
1. "abstract painting" をプロンプト冒頭に配置
2. 具体名詞（building, person, device等）を全て除去
3. 色・形・動きのみで記述

### 症状: 色がカテゴリのイメージと合わない

**原因**: カラーパレットの指定が曖昧

**解決策**:
1. 具体的な色名を使う（例: "deep navy blue", "burnt sienna"）
2. カテゴリプリセットの色を明示的に列挙する
3. `metallic gold accents` を忘れていないか確認

### 症状: プロンプトが長すぎる

**原因**: 要素を詰め込みすぎている

**解決策**:
1. テクスチャ記述を2-3種に絞る
2. 参照アーティストは1-2名まで
3. 動勢の説明は1文に凝縮する
