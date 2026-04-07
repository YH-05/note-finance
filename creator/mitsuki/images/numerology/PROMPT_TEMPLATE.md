# みつき数秘術シンボル — Google Flow 画像生成プロンプトテンプレート

## 使い方

1. **ベーステンプレート**をコピー
2. `{scene}`, `{mood}`, `{detail_focus}`, `{detail_scene}` 等の変数を各ライフパスの定義で差し替え
3. Google Flow に貼り付けて生成
4. 各ライフパスにつき**2回生成**（全体図 + クローズアップ）
5. 保存: `creator/mitsuki/images/numerology/lp_{番号}_{variant}.png`

---

## デザインコンセプト

数秘術は数字そのものがシンボル。各数字の本質的なエネルギーを**抽象的・幻想的な風景**として表現する。数字を直接描くのではなく、その数字の意味を情景・風景として視覚化する。

- タロットと同じブランドの画風・色調を維持
- 人物は登場させず、**風景・自然現象・抽象的オブジェクト**でエネルギーを表現
- 各ライフパスの本質を「一枚の風景画」として凝縮する

---

## ベーステンプレート

### バリエーション A: 全体図（冒頭ヒーロー用 — 800×1200px 縦長 2:3）

```
A mystical landscape illustration representing numerological energy.
Style: soft watercolor with gentle pastel tones. Warm, dreamy, introspective atmosphere. Muted gold accents. The overall mood is contemplative and healing. No human figures. No numbers or text in the image.
Color palette: lavender, soft rose, cream, muted gold, dusty blue.
Composition: vertical format (2:3 ratio), an ethereal landscape with depth and gentle luminosity. Soft vignette at edges.

Subject: {scene}

Mood: {mood}. The image should feel like a quiet portal into an inner world — a dreamscape that resonates with the viewer's soul.
```

### バリエーション B: クローズアップ（解説内用 — 800×800px 正方形 1:1）

```
A close-up detail from a mystical watercolor landscape.
Style: soft watercolor with gentle pastel tones. Warm, dreamy, introspective atmosphere. Muted gold accents.
Color palette: lavender, soft rose, cream, muted gold, dusty blue.
Composition: square format (1:1 ratio), a cropped intimate view focusing on {detail_focus}. Soft bokeh background. No text.

Subject: {detail_scene}

Mood: {mood}. Quiet intimacy, as if leaning closer to examine a meaningful detail in a dream.
```

---

## 全12枚 ライフパス別変数定義

### LP1 — リーダー/独立

| 変数 | 値 |
|------|-----|
| `{scene}` | A single luminous path stretching straight toward a distant horizon at dawn. The first ray of golden light breaks through dark clouds, casting a long beam across a vast open plain. A solitary ancient tree stands at the path's beginning, its branches reaching upward. The landscape is untouched and pristine — the very first morning of something new. |
| `{mood}` | The courage of being first, the solitude of leadership, the electric thrill of a new beginning |
| `{detail_focus}` | the single beam of dawn light breaking through clouds, illuminating the straight path ahead |
| `{detail_scene}` | A single golden ray of light piercing through parting clouds, illuminating dust particles and morning mist, the edge of a straight path visible below |
| 保存名 | `lp_01` |

### LP2 — 調和/協力

| 変数 | 値 |
|------|-----|
| `{scene}` | A tranquil lake at twilight reflecting a crescent moon perfectly — the moon above and its mirror image below creating a symmetrical composition. Two graceful willows lean toward each other from opposite banks, their branches almost touching over the water. Fireflies drift gently between them. The water is absolutely still, creating perfect balance. |
| `{mood}` | Gentle receptivity, the beauty of perfect balance, the quiet strength of harmony and partnership |
| `{detail_focus}` | the crescent moon reflected in the perfectly still water, with fireflies hovering above the surface |
| `{detail_scene}` | A crescent moon mirrored in glass-still water, tiny fireflies creating dots of warm light around the reflection, willow leaves barely touching the surface |
| 保存名 | `lp_02` |

### LP3 — 表現/創造

| 変数 | 値 |
|------|-----|
| `{scene}` | A magical garden where flowers bloom in impossible colors — coral, lilac, and gold — and butterflies carry tiny trails of light as they dance through the air. A gentle fountain at the center sprays water that catches rainbow prisms. Musical notes seem to float as visible sparkles in the warm breeze. Everything is in joyful motion, alive with creative energy. |
| `{mood}` | The effervescence of pure creative joy, self-expression flowing freely, playful abundance |
| `{detail_focus}` | butterflies trailing luminous paths through the air, surrounded by fantastical blooming flowers |
| `{detail_scene}` | Three butterflies in flight leaving gentle trails of golden-pink light, surrounded by oversized flowers in coral and lilac, tiny prism sparkles floating in the air |
| 保存名 | `lp_03` |

### LP4 — 安定/基盤

| 変数 | 値 |
|------|-----|
| `{scene}` | A vast ancient stone formation standing firm on a grassy plateau — four standing stones arranged in a perfect square, covered in soft moss and lichen. At the center, a small crystalline pool reflects the steady blue sky. Deep roots from nearby oaks weave visibly through the earth between the stones. The scene radiates permanence, patience, and timeless stability. |
| `{mood}` | Unshakable foundation, the quiet dignity of endurance, the beauty of structure built to last |
| `{detail_focus}` | the moss-covered surface of one standing stone, with oak roots weaving around its base |
| `{detail_scene}` | Close-up of an ancient standing stone covered in soft green moss and pale lichen, thick oak roots wrapping around its base, tiny wildflowers growing in the crevices |
| 保存名 | `lp_04` |

### LP5 — 自由/変化

| 変数 | 値 |
|------|-----|
| `{scene}` | A dramatic clifftop overlooking a vast ocean where five different winds carry colorful autumn leaves, flower petals, and seeds in swirling spirals across the sky. A winding road below splits into multiple paths leading to different horizons. Clouds shift rapidly in the sky, forming and dissolving. The air itself seems alive with movement and possibility. |
| `{mood}` | Exhilarating freedom, the thrill of the unknown, embracing change as adventure |
| `{detail_focus}` | swirling leaves and petals caught in a spiral of wind against the open sky |
| `{detail_scene}` | Autumn leaves in amber, crimson, and gold spinning in a graceful spiral with flower petals, caught mid-flight against a vast sky with rapidly shifting clouds |
| 保存名 | `lp_05` |

### LP6 — 愛/責任

| 変数 | 値 |
|------|-----|
| `{scene}` | A warm cottage garden at golden hour, overflowing with roses, lavender, and honeysuckle climbing an old stone wall. A round wooden table is set for tea under a flowering arbor, with a soft blanket draped over a chair. Bees hum among the flowers. A gentle path of stepping stones leads to a welcoming open gate. Everything radiates warmth, safety, and belonging. |
| `{mood}` | Unconditional warmth, the beauty of nurturing and being nurtured, a safe harbor of love |
| `{detail_focus}` | roses climbing the stone wall with warm golden hour light filtering through the petals |
| `{detail_scene}` | Climbing roses in soft pink and cream cascading over an old stone wall, golden hour sunlight filtering through translucent petals, a honeybee resting on one bloom |
| 保存名 | `lp_06` |

### LP7 — 探求/内省

| 変数 | 値 |
|------|-----|
| `{scene}` | A deep enchanted forest clearing where a perfectly still pool reflects the stars above, though it is twilight — as if the water sees a deeper sky. Ancient trees form a natural cathedral. A single shaft of silver moonlight penetrates the canopy, illuminating the pool. Mushrooms and crystals glow faintly at the water's edge. The silence is almost tangible. |
| `{mood}` | Profound inner knowing, the sacred solitude of deep thought, mysteries revealed in stillness |
| `{detail_focus}` | the still pool reflecting stars that are not visible in the sky above, with faintly glowing crystals at its edge |
| `{detail_scene}` | A perfectly still dark pool reflecting a starfield, surrounded by faintly luminescent crystals and small mushrooms, a single moonbeam touching the water's surface |
| 保存名 | `lp_07` |

### LP8 — 力/豊かさ

| 変数 | 値 |
|------|-----|
| `{scene}` | A majestic mountain summit at sunrise, where eight peaks are visible in an endless mountain range receding into golden mist. The foreground peak has a natural stone throne formed by the rock, catching the first golden light. An eagle soars at eye level. Below, a river of golden-amber light flows through the valley. The scene conveys earned achievement and vast vision. |
| `{mood}` | Mastery and earned abundance, the panoramic view from the summit, confident power |
| `{detail_focus}` | the golden sunrise light hitting the natural stone formation at the summit, with the eagle silhouette nearby |
| `{detail_scene}` | A natural stone formation bathed in warm golden sunrise light, an eagle in flight nearby, distant mountain peaks fading into golden amber mist |
| 保存名 | `lp_08` |

### LP9 — 完成/奉仕

| 変数 | 値 |
|------|-----|
| `{scene}` | A vast circular garden viewed from above, with nine concentric rings of different flowers — each ring a different color — converging toward a central fountain that overflows gently in all directions. Petals drift outward on the water like offerings. The garden sits on a hilltop overlooking a patchwork of villages and fields below. Sunset paints everything in warm amber and rose. |
| `{mood}` | The wisdom of completion, generous overflow, compassion that embraces all, graceful release |
| `{detail_focus}` | flower petals floating outward on the overflowing fountain water, carrying color in every direction |
| `{detail_scene}` | Delicate flower petals in nine different colors floating on gently overflowing water, catching sunset light, drifting outward in a circular pattern |
| 保存名 | `lp_09` |

### LP11 — 啓示/直感（マスターナンバー）

| 変数 | 値 |
|------|-----|
| `{scene}` | Two parallel pillars of ethereal light rise from the earth to the heavens, framing an aurora-like luminescence between them. The pillars are translucent, shimmering between lavender and silver. Between them, a gateway of light opens to reveal a cosmic starfield. The ground is a mirror-like surface reflecting the entire scene. Lightning bugs create a path leading to the gateway. |
| `{mood}` | Spiritual awakening, the electricity of divine inspiration, seeing beyond the veil |
| `{detail_focus}` | the gateway of light between the two pillars, revealing the cosmic starfield beyond |
| `{detail_scene}` | A luminous gateway formed between two translucent pillars of lavender-silver light, revealing a deep cosmic starfield, tiny lightning bugs drifting toward the opening |
| 保存名 | `lp_11` |

### LP22 — 建設/ビジョン（マスターナンバー）

| 変数 | 値 |
|------|-----|
| `{scene}` | A breathtaking bridge of crystalline light arching across an impossibly wide canyon, connecting two distant lands. The bridge appears to be built from solidified starlight and sacred geometry — hexagons and golden spirals visible in its structure. Below, a vast river flows. On both sides, cities of soft light glow on the horizon. The sky holds both sun and moon simultaneously. |
| `{mood}` | Visionary creation made manifest, the architect of dreams, bridging the impossible |
| `{detail_focus}` | the crystalline bridge structure showing sacred geometry patterns — hexagons and golden spirals woven from light |
| `{detail_scene}` | Close-up of a translucent crystalline surface with golden spiral and hexagonal geometric patterns glowing within, like solidified starlight, with the soft glow of distant lights visible through it |
| 保存名 | `lp_22` |

### LP33 — 慈愛/導き（マスターナンバー）

| 変数 | 値 |
|------|-----|
| `{scene}` | An ancient, enormous tree of light at the center of a gentle valley, its branches spreading wide like sheltering arms. The tree emits a warm, golden-rose glow from within. Smaller trees and all manner of flowers grow in its light, oriented toward it. Soft paths radiate outward from the tree in every direction like gentle rays. Birds of different kinds rest peacefully in its branches. The scene radiates unconditional welcome. |
| `{mood}` | Boundless compassion, the teacher who illuminates by simply being, unconditional love that heals |
| `{detail_focus}` | the trunk of the great tree emitting warm golden-rose light, with diverse flowers growing in its radiance |
| `{detail_scene}` | A luminous tree trunk radiating warm golden-rose light from within its bark, surrounded by diverse flowers all leaning gently toward its warmth, soft light filtering through like a blessing |
| 保存名 | `lp_33` |

---

## 生成手順

### Step 1: 全体図を生成

1. ベーステンプレートA をコピー
2. 対象ライフパスの `{scene}`, `{mood}` を差し替え
3. Google Flow に貼り付けて生成（800×1200px / 縦長 2:3 を指定）
4. 気に入った画像を `lp_{番号}_full.png` で保存

### Step 2: クローズアップを生成

1. ベーステンプレートB をコピー
2. 対象ライフパスの `{detail_focus}`, `{detail_scene}`, `{mood}` を差し替え
3. Google Flow に貼り付けて生成（800×800px / 正方形 1:1 を指定）
4. 気に入った画像を `lp_{番号}_detail.png` で保存

### Step 3: サムネイルテンプレート（別途作成）

サムネイルは数秘画像 + テキストの合成。Pythonスクリプト（Pillow）で自動合成。
→ タロットと同様のスクリプトで対応予定

---

## デザインの統一ポイント（タロットと共通）

| 要素 | 統一ルール |
|------|----------|
| 画風 | 水彩画（soft watercolor） |
| 色調 | ラベンダー、ソフトローズ、クリーム、くすみゴールド、ダスティブルー |
| 雰囲気 | 温かい、夢想的、内省的（warm, dreamy, introspective） |
| テキスト | 画像内にテキストなし（サムネイルで別途合成） |
| トーン | 数字を直接描かない。エネルギーを風景・情景として表現 |
| 人物 | 登場させない（風景・自然・抽象オブジェクトのみ） |

## タロットとの差別化ポイント

| 要素 | タロット | 数秘術 |
|------|---------|--------|
| 主題 | 人物 + シンボル | 風景 + 自然現象 |
| 構図 | カード枠あり | 枠なし（風景画） |
| フォーマットA | 縦長カード形式 | 縦長風景（2:3） |
| フォーマットB | カード内クローズアップ | 風景クローズアップ（1:1） |
| 数字の表現 | カード上部に番号表示 | 数字を直接描かない |

## ファイル命名規則

```
creator/mitsuki/images/numerology/
├── PROMPT_TEMPLATE.md
├── prompts/
│   ├── lp_01.md
│   ├── lp_02.md
│   ├── lp_03.md
│   ├── lp_04.md
│   ├── lp_05.md
│   ├── lp_06.md
│   ├── lp_07.md
│   ├── lp_08.md
│   ├── lp_09.md
│   ├── lp_11.md
│   ├── lp_22.md
│   └── lp_33.md
├── lp_01_full.png
├── lp_01_detail.png
├── ...
├── lp_33_full.png
└── lp_33_detail.png
```
