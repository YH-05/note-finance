# みつき星座イラスト — 画像生成プロンプトテンプレート

## 使い方

1. **ベーステンプレート**をコピー
2. `{zodiac_name}`, `{scene}`, `{mood}` 等の変数を各星座の定義で差し替え
3. 画像生成AIに貼り付けて生成
4. 各星座につき**2回生成**（全体図 + クローズアップ）
5. 保存: `creator/mitsuki/images/zodiac/zodiac_{英語名}_{variant}.png`

---

## ベーステンプレート

### バリエーション A: 全体図（冒頭ヒーロー用 / 1200x800px 横長 3:2）

```
A zodiac-themed fantasy illustration for "{zodiac_name}".
Style: soft watercolor with gentle pastel tones. Warm, dreamy, introspective atmosphere. Muted gold accents. The overall mood is contemplative and healing, never dark or frightening.
Color palette: lavender, soft rose, cream, muted gold, dusty blue.
Composition: vertical 2:3 format (800x1200px). A thin elegant gold border frames the scene. The zodiac constellation "{zodiac_name}" is subtly traced in faint gold dots in the sky or background. No text on the image.

Subject: {scene}

Mood: {mood}. The image should feel like a quiet moment of cosmic connection, as if the viewer is discovering a piece of their own soul reflected in the stars.
```

### バリエーション B: クローズアップ（解説内用 / 800x800px 正方形）

```
A close-up detail from a zodiac-themed fantasy illustration for "{zodiac_name}".
Style: soft watercolor with gentle pastel tones. Warm, dreamy, introspective atmosphere. Muted gold accents.
Color palette: lavender, soft rose, cream, muted gold, dusty blue.
Composition: square 1:1 format (800x800px). A cropped, intimate view focusing on {detail_focus}. No border. No text.

Subject: {detail_scene}

Mood: {mood}. Quiet intimacy, as if examining a meaningful detail up close.
```

---

## 12星座 変数定義

### 01 — おひつじ座 (Aries)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Aries |
| `{scene}` | A vast dawn-lit grassland with trails of blazing golden light racing across the terrain, as if an invisible force of pure courage is charging forward. Sparks of fire rise from the grass tips, and the horizon glows with the fierce warmth of a new beginning. Wild red poppies bloom defiantly along the light trails. The sky is painted in coral and amber. |
| `{mood}` | Fearless initiation, the thrill of a brand-new beginning, raw pioneering energy |
| `{detail_focus}` | the trails of golden fire light racing through wild poppies at dawn |
| `{detail_scene}` | Close-up of blazing golden light trails cutting through a field of wild red poppies, sparks floating upward like fireflies, the warm amber glow of dawn touching every petal |
| 保存名 | `zodiac_aries` |

### 02 — おうし座 (Taurus)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Taurus |
| `{scene}` | A lush, sunlit meadow at golden hour, where the earth itself seems to breathe with abundance. Ancient moss-covered stones form a natural garden, surrounded by blooming roses, lavender, and ripe fruit trees. A gentle stream meanders through velvet grass. Everything radiates the quiet satisfaction of deep-rooted stability and sensory pleasure. |
| `{mood}` | Grounded abundance, sensory delight, the patient beauty of things that endure |
| `{detail_focus}` | the moss-covered ancient stones surrounded by blooming roses and ripe fruit |
| `{detail_scene}` | Close-up of weathered moss-covered stones nestled among full-bloom roses in soft pink and cream, ripe golden fruits hanging nearby, warm golden-hour light dappling through leaves |
| 保存名 | `zodiac_taurus` |

### 03 — ふたご座 (Gemini)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Gemini |
| `{scene}` | A dreamlike sky-garden floating among gentle clouds, where two mirrored spiral staircases intertwine without ever touching. Butterflies and small birds carry luminous threads between the two paths. Books and scrolls drift in the breeze like leaves. The air shimmers with the energy of endless curiosity and playful dialogue. |
| `{mood}` | Intellectual curiosity, playful duality, the joy of connection and exchange of ideas |
| `{detail_focus}` | the luminous threads carried by butterflies between the two intertwining staircases |
| `{detail_scene}` | Close-up of delicate butterflies carrying shimmering golden threads through soft clouds, with pages from open books drifting nearby, light refracting through the threads like tiny prisms |
| 保存名 | `zodiac_gemini` |

### 04 — かに座 (Cancer)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Cancer |
| `{scene}` | A serene moonlit cove where the ocean meets a sheltered tide pool garden. Bioluminescent water glows in soft blues and silvers. Delicate shells and sea glass form natural mosaics on the sand. A pearl-white moon hangs low, its reflection creating a luminous path across the gentle waves. The entire scene feels like a protective embrace. |
| `{mood}` | Nurturing warmth, emotional depth, the safety of a sacred inner sanctuary |
| `{detail_focus}` | the bioluminescent tide pool with shells and sea glass forming natural patterns |
| `{detail_scene}` | Close-up of a glowing tide pool with bioluminescent blue-silver water, intricate arrangements of pearlescent shells and frosted sea glass on sand, moonlight reflecting in tiny pools |
| 保存名 | `zodiac_cancer` |

### 05 — しし座 (Leo)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Leo |
| `{scene}` | A magnificent sunset amphitheater carved from golden sandstone, where beams of warm light pour through natural arches like spotlights on a grand stage. Sunflowers and marigolds cascade down the tiers. The sky blazes in regal golds, deep oranges, and royal purples. A crown-shaped formation of clouds catches the last rays of the sun, radiating generous warmth. |
| `{mood}` | Radiant self-expression, generous warmth, the courage to shine as one's authentic self |
| `{detail_focus}` | the sunlight pouring through natural golden arches with sunflowers cascading below |
| `{detail_scene}` | Close-up of warm golden sunbeams streaming through a sandstone arch, illuminating cascading sunflowers and marigolds, petals glowing at their edges, dust motes dancing in the light |
| 保存名 | `zodiac_leo` |

### 06 — おとめ座 (Virgo)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Virgo |
| `{scene}` | An enchanted apothecary garden at soft morning light, where herbs and wildflowers grow in exquisite natural patterns. Dewdrops on wheat stalks and lavender catch the light like tiny crystals. A weathered stone sundial stands at the center, surrounded by carefully tended medicinal plants. Everything is arranged with organic precision — nature perfected by loving attention. |
| `{mood}` | Quiet devotion, healing through care, the beauty of thoughtful precision and service |
| `{detail_focus}` | the dewdrop-covered herbs and wheat stalks catching morning light like crystals |
| `{detail_scene}` | Close-up of glistening dewdrops on lavender stems and golden wheat, each droplet catching morning light like a tiny crystal lens, delicate herb leaves in perfect detail, soft focus background of the garden |
| 保存名 | `zodiac_virgo` |

### 07 — てんびん座 (Libra)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Libra |
| `{scene}` | A floating sky pavilion at the golden equilibrium of sunset and twilight, where the sky is perfectly split between warm rose-gold and cool periwinkle blue. Translucent silk curtains billow in a gentle breeze. Two ornamental fountains flow in perfect symmetry, their waters meeting in a central reflecting pool. Cherry blossoms and wisteria frame the scene in balanced harmony. |
| `{mood}` | Elegant harmony, the art of balance, beauty found in the space between opposites |
| `{detail_focus}` | the two symmetrical fountains meeting in the central reflecting pool at twilight |
| `{detail_scene}` | Close-up of two streams of crystalline water meeting in a still reflecting pool, the surface mirroring both the warm rose-gold and cool blue of the sky, scattered cherry blossom petals floating on the water |
| 保存名 | `zodiac_libra` |

### 08 — さそり座 (Scorpio)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Scorpio |
| `{scene}` | A mystical underground grotto where a deep, still pool reflects an impossible starry sky from above. Crystals of deep garnet and amethyst grow from the cavern walls, emitting a soft inner glow. A single phoenix-like ember floats above the water's surface, its reflection creating a bridge between the depths and the heavens. The atmosphere is magnetic and transformative. |
| `{mood}` | Profound transformation, the power of emotional depth, rebirth through unflinching truth |
| `{detail_focus}` | the phoenix ember floating above the still pool with crystal reflections |
| `{detail_scene}` | Close-up of a glowing ember hovering above a perfectly still dark pool, deep garnet and amethyst crystals framing the edges, the ember's warm light reflected in the water alongside distant stars |
| 保存名 | `zodiac_scorpio` |

### 09 — いて座 (Sagittarius)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Sagittarius |
| `{scene}` | A breathtaking mountain vista at the edge of the world, where a natural stone archway frames an infinite horizon of layered purple mountains and golden clouds. A trail of luminous arrow-shaped lights stretches across the sky like a cosmic compass pointing toward the unknown. Wildflowers in violet and gold blanket the cliff edge. The air feels electric with possibility and adventure. |
| `{mood}` | Boundless optimism, the quest for meaning, the exhilaration of expanding one's horizons |
| `{detail_focus}` | the luminous arrow-shaped lights streaking across the sky toward the infinite horizon |
| `{detail_scene}` | Close-up of glowing arrow-shaped light trails arcing across a twilight sky, golden clouds layered in the distance, tiny wildflowers in violet and gold at the bottom edge reaching upward |
| 保存名 | `zodiac_sagittarius` |

### 10 — やぎ座 (Capricorn)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Capricorn |
| `{scene}` | An ancient mountain summit at the blue hour before dawn, where weathered stone steps spiral upward through layers of mist. Each step is worn smooth by countless journeys. At the peak, a crystalline structure catches the first pre-dawn light, glowing like a quiet crown of achievement. Pine trees and winter flowers cling to the rocky face with quiet tenacity. |
| `{mood}` | Patient determination, the dignity of earned wisdom, quiet mastery through perseverance |
| `{detail_focus}` | the worn stone steps spiraling upward through mist toward the crystalline peak |
| `{detail_scene}` | Close-up of ancient stone steps worn smooth by time, dusted with frost, spiraling upward into soft blue mist, tiny resilient winter flowers growing in the cracks, a faint glow from above |
| 保存名 | `zodiac_capricorn` |

### 11 — みずがめ座 (Aquarius)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Aquarius |
| `{scene}` | A surreal aerial landscape where streams of luminous water flow upward into the sky, defying gravity and convention. The water transforms into constellations as it rises. Floating geometric crystals refract rainbow light through the ascending streams. Below, a community of small glowing lanterns dots the landscape like earthbound stars, connected by threads of light. |
| `{mood}` | Visionary independence, humanitarian connection, the beauty of seeing beyond the ordinary |
| `{detail_focus}` | the streams of water flowing upward and transforming into constellations |
| `{detail_scene}` | Close-up of luminous water streams rising upward against gravity, individual droplets becoming glowing star-points as they ascend, rainbow refractions from a floating crystal nearby, the boundary between water and starlight dissolving |
| 保存名 | `zodiac_aquarius` |

### 12 — うお座 (Pisces)

| 変数 | 値 |
|------|-----|
| `{zodiac_name}` | Pisces |
| `{scene}` | A deep oceanic dreamscape where light particles drift like golden snow through translucent blue-violet water. Ethereal jellyfish trail luminous ribbons, and coral formations glow with inner light in soft pinks and lavenders. Two streams of bioluminescent current spiral around each other in an endless dance. The boundary between water and sky has dissolved into pure feeling. |
| `{mood}` | Boundless empathy, the dissolution of boundaries, dreaming the world into being |
| `{detail_focus}` | the two bioluminescent currents spiraling together among glowing coral |
| `{detail_scene}` | Close-up of two spiraling streams of bioluminescent blue-gold light intertwining through translucent water, delicate glowing coral in soft pink and lavender nearby, golden light particles suspended like underwater stars |
| 保存名 | `zodiac_pisces` |

---

## 生成手順

### Step 1: 全体図を生成

1. ベーステンプレートA をコピー
2. 対象星座の `{zodiac_name}`, `{scene}`, `{mood}` を差し替え
3. 画像生成AIに貼り付けて生成（800x1200px / 縦長 2:3）
4. 気に入った画像を `zodiac_{英語名}_full.png` で保存

### Step 2: クローズアップを生成

1. ベーステンプレートB をコピー
2. 対象星座の `{zodiac_name}`, `{detail_focus}`, `{detail_scene}`, `{mood}` を差し替え
3. 画像生成AIに貼り付けて生成（800x800px / 正方形 1:1）
4. 気に入った画像を `zodiac_{英語名}_detail.png` で保存

### Step 3: サムネイルテンプレート（別途作成）

サムネイルは星座画像 + テキストの合成。Pythonスクリプト（Pillow）で自動合成予定。

---

## デザインの統一ポイント（タロットカードと共通）

| 要素 | 統一ルール |
|------|----------|
| 画風 | 水彩画（soft watercolor） |
| 色調 | ラベンダー、ソフトローズ、クリーム、くすみゴールド、ダスティブルー |
| 雰囲気 | 温かい、夢想的、内省的（warm, dreamy, introspective） |
| 枠線 | 薄い金色のエレガントなボーダー（全体図のみ） |
| テキスト | 画像内にテキストなし（サムネイルで別途合成） |
| トーン | 怖くない。全星座を肯定的・内省的に表現 |
| 星座記号 | 星座の星の並びを金色のドットで背景にさりげなく配置 |

## 星座固有のデザイン指針

| エレメント | カラーアクセント | 質感 |
|-----------|----------------|------|
| 火（牡羊・獅子・射手） | コーラル、アンバー、ゴールドの温かみ | 光の軌跡、輝く粒子、温かい大気 |
| 地（牡牛・乙女・山羊） | セージ、アースブラウン、モスグリーンの落ち着き | 石、植物、露、自然のテクスチャ |
| 風（双子・天秤・水瓶） | ペリウィンクル、シルバー、ライトゴールドの軽やかさ | 空気感、透明感、浮遊感 |
| 水（蟹・蠍・魚） | ディープブルー、シルバー、バイオレットの深み | 水面反射、発光、透明度 |

## ファイル命名規則

```
creator/mitsuki/images/zodiac/
├── PROMPT_TEMPLATE.md
├── prompts/
│   ├── zodiac_aries.md
│   ├── zodiac_taurus.md
│   ├── zodiac_gemini.md
│   ├── zodiac_cancer.md
│   ├── zodiac_leo.md
│   ├── zodiac_virgo.md
│   ├── zodiac_libra.md
│   ├── zodiac_scorpio.md
│   ├── zodiac_sagittarius.md
│   ├── zodiac_capricorn.md
│   ├── zodiac_aquarius.md
│   ├── zodiac_pisces.md
├── zodiac_aries_full.png
├── zodiac_aries_detail.png
├── ...
├── zodiac_pisces_full.png
└── zodiac_pisces_detail.png
```
