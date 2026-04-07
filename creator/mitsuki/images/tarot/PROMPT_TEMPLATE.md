# みつきオリジナルタロット — Google Flow 画像生成プロンプトテンプレート

## 使い方

1. **ベーステンプレート**をコピー
2. `{card_name}`, `{scene}`, `{mood}` 等の変数を各カードの定義で差し替え
3. Google Flow に貼り付けて生成
4. 各カードにつき**2回生成**（全体図 + 別アングル）
5. 保存: `creator/mitsuki/images/tarot/major_{番号}_{英語名}_{variant}.png`

---

## ベーステンプレート

### バリエーション A: 全体図（冒頭ヒーロー用）

```
A tarot card illustration.
Style: soft watercolor with gentle pastel tones. Warm, dreamy, introspective atmosphere. Muted gold accents. The overall mood is contemplative and healing, never dark or frightening.
Color palette: lavender, soft rose, cream, muted gold, dusty blue.
Composition: vertical tarot card format with a thin elegant gold border. The card number "{number}" is subtly placed at the top. No text or card title on the image.

Subject: {scene}

Mood: {mood}. The image should feel like a quiet moment of self-reflection, as if the viewer is looking into a mirror of their inner world.
```

### バリエーション B: 別アングル / クローズアップ（解説内用）

```
A close-up detail from a tarot card illustration.
Style: soft watercolor with gentle pastel tones. Warm, dreamy, introspective atmosphere. Muted gold accents.
Color palette: lavender, soft rose, cream, muted gold, dusty blue.
Composition: a cropped, intimate view focusing on {detail_focus}. No card border. No text.

Subject: {detail_scene}

Mood: {mood}. Quiet intimacy, as if examining a meaningful detail up close.
```

---

## 全22枚 カード別変数定義

### 00 — 愚者 (The Fool)

| 変数 | 値 |
|------|-----|
| `{number}` | 0 |
| `{scene}` | A young person standing at the edge of a cliff, looking up at the sky with a small white dog at their feet. They carry a small bundle on a stick. Wildflowers bloom at the cliff edge. The sky is vast and open with soft clouds. |
| `{mood}` | Innocent wonder, the beginning of a journey, trust in the unknown |
| `{detail_focus}` | the person's face and upward gaze, with the open sky behind them |
| `{detail_scene}` | A close-up of a young person's face gazing upward with wonder, wildflowers framing the edges, a hint of open sky |
| 保存名 | `major_00_fool` |

### 01 — 魔術師 (The Magician)

| 変数 | 値 |
|------|-----|
| `{number}` | I |
| `{scene}` | A figure standing at a table with four symbolic objects: a cup, a pentacle, a sword, and a wand. One hand points upward, the other downward. An infinity symbol glows faintly above their head. Roses and lilies surround the table. |
| `{mood}` | Focused potential, the power of intention, creative energy about to manifest |
| `{detail_focus}` | the four symbolic objects on the table — cup, coin, small sword, and wooden wand |
| `{detail_scene}` | Four symbolic objects arranged on a wooden table — a delicate cup, a golden coin, a small ornate sword, and a wooden wand — surrounded by rose petals |
| 保存名 | `major_01_magician` |

### 02 — 女教皇 (The High Priestess)

| 変数 | 値 |
|------|-----|
| `{number}` | II |
| `{scene}` | A serene woman seated between two pillars (one light, one dark), holding a scroll or book in her lap. A crescent moon at her feet. A veil with pomegranates hangs behind her. Water flows gently in the background. |
| `{mood}` | Deep intuition, hidden knowledge, the wisdom of stillness and silence |
| `{detail_focus}` | the scroll or book in her lap, partially unrolled, with the crescent moon nearby |
| `{detail_scene}` | A partially unrolled ancient scroll resting on soft fabric, with a crescent moon shape glowing softly beside it |
| 保存名 | `major_02_high_priestess` |

### 03 — 女帝 (The Empress)

| 変数 | 値 |
|------|-----|
| `{number}` | III |
| `{scene}` | A graceful woman seated in a lush garden filled with wheat, flowers, and flowing water. She wears a crown of stars and holds a heart-shaped shield. The garden is abundant and alive with soft light filtering through trees. |
| `{mood}` | Nurturing abundance, self-compassion, the beauty of caring for oneself and others |
| `{detail_focus}` | the lush garden — wheat stalks, blooming flowers, and soft light |
| `{detail_scene}` | A dreamy garden scene: golden wheat stalks bending gently, pink and white flowers in full bloom, soft sunlight filtering through leaves |
| 保存名 | `major_03_empress` |

### 04 — 皇帝 (The Emperor)

| 変数 | 値 |
|------|-----|
| `{number}` | IV |
| `{scene}` | A composed figure seated on a stone throne with ram heads carved into the armrests. Mountains rise in the background. The figure holds an orb and a scepter, but their expression is thoughtful rather than stern. Warm light touches the mountain peaks. |
| `{mood}` | Quiet authority, inner structure, the strength of knowing one's own foundation |
| `{detail_focus}` | the stone throne with ram head carvings, warm light on the armrest |
| `{detail_scene}` | A carved stone armrest with a gentle ram head design, warm golden light touching the surface, mountains softly blurred in the background |
| 保存名 | `major_04_emperor` |

### 05 — 教皇 (The Hierophant)

| 変数 | 値 |
|------|-----|
| `{number}` | V |
| `{scene}` | A wise figure seated between two pillars, wearing a triple crown. Two students or seekers kneel before them. Crossed keys lie at the figure's feet. The setting is a quiet temple with soft candlelight. |
| `{mood}` | Gentle guidance, the comfort of tradition and shared wisdom, learning from those who walked before |
| `{detail_focus}` | the crossed keys at the figure's feet, with candlelight reflected on them |
| `{detail_scene}` | Two ornate crossed keys lying on stone floor, soft candlelight casting warm shadows, a hint of temple columns in the background |
| 保存名 | `major_05_hierophant` |

### 06 — 恋人 (The Lovers)

| 変数 | 値 |
|------|-----|
| `{number}` | VI |
| `{scene}` | Two figures facing each other in a garden, with an angel or winged figure above them in the clouds, arms outstretched in blessing. A tree with fruit behind one figure, a tree with flames behind the other. Soft light connects all three figures. |
| `{mood}` | The vulnerability of choosing connection, the beauty and risk of opening one's heart |
| `{detail_focus}` | the two figures' hands reaching toward each other, not quite touching |
| `{detail_scene}` | Two hands reaching toward each other with a small gap between them, soft light glowing in the space between, flower petals drifting in the air |
| 保存名 | `major_06_lovers` |

### 07 — 戦車 (The Chariot)

| 変数 | 値 |
|------|-----|
| `{number}` | VII |
| `{scene}` | A determined figure riding a chariot pulled by two sphinxes (one light, one dark). A canopy of stars above. The city walls are behind them. The figure wears a crescent moon breastplate and holds no reins — they guide by will alone. |
| `{mood}` | Moving forward despite inner conflict, the courage of holding opposites together |
| `{detail_focus}` | the two sphinxes — one light and one dark — side by side |
| `{detail_scene}` | Two sphinx figures, one in soft white and one in gentle dark tones, sitting peacefully side by side, starlight falling on them |
| 保存名 | `major_07_chariot` |

### 08 — 力 (Strength)

| 変数 | 値 |
|------|-----|
| `{number}` | VIII |
| `{scene}` | A gentle figure calmly opening or closing the mouth of a lion. An infinity symbol glows faintly above their head. The figure uses no force — only gentle touch. Flowers and greenery surround them. The lion appears calm and trusting. |
| `{mood}` | Quiet power, gentleness as strength, befriending one's own wild emotions |
| `{detail_focus}` | the gentle hands on the lion's face, the trust between them |
| `{detail_scene}` | Gentle hands resting softly on a calm lion's mane, the lion's eyes half-closed in trust, wildflowers framing the scene |
| 保存名 | `major_08_strength` |

### 09 — 隠者 (The Hermit)

| 変数 | 値 |
|------|-----|
| `{number}` | IX |
| `{scene}` | A solitary figure standing on a mountain peak, holding a lantern with a six-pointed star inside. They lean on a staff. The landscape below is misty and vast. Stars are visible in the twilight sky. |
| `{mood}` | The value of solitude, searching within, the light one carries for oneself |
| `{detail_focus}` | the lantern with the glowing star inside, held against the twilight sky |
| `{detail_scene}` | A delicate lantern with a softly glowing six-pointed star inside, held up against a misty twilight sky with faint stars |
| 保存名 | `major_09_hermit` |

### 10 — 運命の輪 (Wheel of Fortune)

| 変数 | 値 |
|------|-----|
| `{number}` | X |
| `{scene}` | A great wheel floating in the sky, with symbols and creatures at its four corners (angel, eagle, lion, bull). Figures rise and fall on the wheel's edge. Clouds surround the wheel. The overall feeling is of gentle cosmic motion rather than chaos. |
| `{mood}` | Cycles and change, trusting the rhythm of life, nothing stays the same and that is okay |
| `{detail_focus}` | the center of the wheel with its symbolic markings |
| `{detail_scene}` | The ornate center of a cosmic wheel with gentle symbolic markings, soft golden light emanating from its hub, misty clouds swirling slowly around it |
| 保存名 | `major_10_wheel` |

### 11 — 正義 (Justice)

| 変数 | 値 |
|------|-----|
| `{number}` | XI |
| `{scene}` | A balanced figure seated on a throne, holding a sword in one hand (pointing upward) and balanced scales in the other. A veil hangs behind them. The figure's expression is calm and discerning, not harsh. |
| `{mood}` | Inner balance, the clarity that comes from honest self-examination, fairness toward oneself |
| `{detail_focus}` | the balanced scales, perfectly level, with soft light on both sides |
| `{detail_scene}` | A pair of delicate golden scales in perfect balance, soft light illuminating both pans equally, a subtle veil texture in the background |
| 保存名 | `major_11_justice` |

### 12 — 吊るされた男 (The Hanged Man)

| 変数 | 値 |
|------|-----|
| `{number}` | XII |
| `{scene}` | A figure hanging upside down from a living tree by one foot, the other leg crossed behind. Their expression is peaceful, not suffering. A soft halo or glow surrounds their head. Leaves grow from the tree. |
| `{mood}` | Seeing the world from a new angle, the gift of surrender, wisdom in letting go |
| `{detail_focus}` | the figure's peaceful upside-down face with the soft glow around their head |
| `{detail_scene}` | A peaceful face seen upside down, eyes gently closed, a soft warm glow around the head like a quiet halo, green leaves framing the scene |
| 保存名 | `major_12_hanged_man` |

### 13 — 死神 (Death)

| 変数 | 値 |
|------|-----|
| `{number}` | XIII |
| `{scene}` | A skeletal figure in armor rides a white horse across a field. Before them, flowers wilt, but behind them, new shoots emerge from the earth. A rising sun glows on the horizon. A white rose banner flies. The scene is transformative, not frightening. |
| `{mood}` | Transformation and renewal, the beauty of endings that make space for beginnings |
| `{detail_focus}` | the contrast of wilting flowers and new green shoots emerging from the earth |
| `{detail_scene}` | Wilting flowers on one side transitioning into fresh green shoots and tiny buds on the other, with soft morning light touching the new growth |
| 保存名 | `major_13_death` |

### 14 — 節制 (Temperance)

| 変数 | 値 |
|------|-----|
| `{number}` | XIV |
| `{scene}` | A winged figure standing with one foot on land and one in water, pouring liquid between two cups in a continuous flow. Irises bloom nearby. A path leads to distant mountains where a golden crown of light shines. |
| `{mood}` | Harmony and integration, finding balance between heart and mind, patience with the process |
| `{detail_focus}` | the flowing liquid between the two cups, catching the light |
| `{detail_scene}` | Luminous liquid flowing in a graceful arc between two golden cups, catching soft light, with iris flowers blooming nearby |
| 保存名 | `major_14_temperance` |

### 15 — 悪魔 (The Devil)

| 変数 | 値 |
|------|-----|
| `{number}` | XV |
| `{scene}` | A horned figure perched on a pedestal. Two smaller figures stand before it with loose chains around their necks — chains they could easily remove. A dim flame burns. The scene is more melancholic than scary, showing attachment patterns rather than evil. |
| `{mood}` | Recognizing one's own patterns of attachment, the chains we choose to keep, shadow work |
| `{detail_focus}` | the loose chains around one figure's neck — clearly removable |
| `{detail_scene}` | A loose chain draped around a figure's neck, clearly oversized and easy to remove, with the figure's hand almost reaching to lift it off — a moment of near-awareness |
| 保存名 | `major_15_devil` |

### 16 — 塔 (The Tower)

| 変数 | 値 |
|------|-----|
| `{number}` | XVI |
| `{scene}` | A tall tower struck by lightning, with its crown blown off. Two figures fall from the tower. But the lightning also reveals a hidden structure within — something beautiful and true beneath the facade. Dawn light emerges behind the storm. |
| `{mood}` | Sudden revelation, the liberation in structures breaking down, finding truth beneath the surface |
| `{detail_focus}` | the crack in the tower revealing something luminous inside |
| `{detail_scene}` | A crack in a stone wall revealing soft golden light pouring through from within, fragments falling away to show something beautiful underneath |
| 保存名 | `major_16_tower` |

### 17 — 星 (The Star)

| 変数 | 値 |
|------|-----|
| `{number}` | XVII |
| `{scene}` | A kneeling figure pours water from two vessels — one into a pool, one onto the earth. They are unclothed and vulnerable. Eight stars shine above, one larger than the rest. A bird perches in a distant tree. The landscape is open and peaceful. |
| `{mood}` | Hope after darkness, vulnerability as courage, the quiet return of faith in oneself |
| `{detail_focus}` | the water being poured — one stream into the pool creating ripples, one onto the earth nourishing the ground |
| `{detail_scene}` | Water flowing gently from a vessel into a still pool, creating soft ripples that catch starlight, with small plants growing where the water touches earth |
| 保存名 | `major_17_star` |

### 18 — 月 (The Moon)

| 変数 | 値 |
|------|-----|
| `{number}` | XVIII |
| `{scene}` | A full moon with a face hangs in the night sky, shining between two towers. A winding path leads from a pool of water into distant hills. A crayfish emerges from the pool. A dog and a wolf howl at the moon on either side of the path. |
| `{mood}` | The beauty of uncertainty, navigating through confusion, trusting the path even when you cannot see clearly |
| `{detail_focus}` | the winding moonlit path leading into the misty distance between the two towers |
| `{detail_scene}` | A winding path bathed in soft moonlight, disappearing into gentle mist between two distant silhouetted towers, small luminous flowers lining the path edges |
| 保存名 | `major_18_moon` |

### 19 — 太陽 (The Sun)

| 変数 | 値 |
|------|-----|
| `{number}` | XIX |
| `{scene}` | A joyful child rides a white horse under a brilliant sun with a face. Sunflowers bloom in a garden behind a low wall. The child's arms are open wide. Everything is bathed in warm, golden light. A red banner waves. |
| `{mood}` | Pure joy and vitality, the warmth of being fully yourself, inner child radiance |
| `{detail_focus}` | the sunflowers turning toward the warm light |
| `{detail_scene}` | Large sunflowers in full bloom, turning their faces toward warm golden light, petals glowing at the edges, a low garden wall softly blurred behind them |
| 保存名 | `major_19_sun` |

### 20 — 審判 (Judgement)

| 変数 | 値 |
|------|-----|
| `{number}` | XX |
| `{scene}` | An angel blows a trumpet from the clouds. Below, figures rise from open coffins or the earth, arms outstretched toward the sky. Mountains and water surround them. The rising figures look upward with expressions of awakening, not fear. |
| `{mood}` | Awakening to one's calling, the moment of knowing what truly matters, answering the inner voice |
| `{detail_focus}` | a figure rising with arms outstretched, looking upward with wonder |
| `{detail_scene}` | A figure emerging upward with arms open wide, face turned to the sky with an expression of gentle awakening, soft light pouring down from above |
| 保存名 | `major_20_judgement` |

### 21 — 世界 (The World)

| 変数 | 値 |
|------|-----|
| `{number}` | XXI |
| `{scene}` | A dancing figure surrounded by a large oval wreath of laurel leaves. Four creatures at the corners: angel, eagle, lion, bull. The figure holds two wands and dances freely within the wreath. The background is a cosmic starfield. |
| `{mood}` | Wholeness and completion, the joy of integration, dancing freely as one's complete self |
| `{detail_focus}` | the dancing figure within the wreath, in a moment of free movement |
| `{detail_scene}` | A graceful figure in mid-dance within a wreath of laurel leaves, fabric flowing with the movement, starlight sparkling around them, a sense of joyful completion |
| 保存名 | `major_21_world` |

---

## 生成手順

### Step 1: 全体図を生成

1. ベーステンプレートA をコピー
2. 対象カードの `{number}`, `{scene}`, `{mood}` を差し替え
3. Google Flow に貼り付けて生成
4. 気に入った画像を `major_{番号}_{英語名}_full.png` で保存

### Step 2: 別アングルを生成

1. ベーステンプレートB をコピー
2. 対象カードの `{detail_focus}`, `{detail_scene}`, `{mood}` を差し替え
3. Google Flow に貼り付けて生成
4. 気に入った画像を `major_{番号}_{英語名}_detail.png` で保存

### Step 3: サムネイルテンプレート（別途作成）

サムネイルはカード画像 + テキストの合成。Pythonスクリプト（Pillow）で自動合成。
→ `scripts/generate_tarot_thumbnail.py` として実装予定

---

## デザインの統一ポイント

| 要素 | 統一ルール |
|------|----------|
| 画風 | 水彩画（soft watercolor） |
| 色調 | ラベンダー、ソフトローズ、クリーム、くすみゴールド、ダスティブルー |
| 雰囲気 | 温かい、夢想的、内省的（warm, dreamy, introspective） |
| 枠線 | 薄い金色のエレガントなボーダー（全体図のみ） |
| テキスト | 画像内にテキストなし（サムネイルで別途合成） |
| トーン | 怖くない。暗いテーマ（死神、悪魔、塔）も変容・気づきとして表現 |
| 人物 | 性別を特定しない表現を推奨（みつきの読者層=女性中心だが限定しない） |

## ファイル命名規則

```
creator/mitsuki/images/tarot/
├── major_00_fool_full.png
├── major_00_fool_detail.png
├── major_01_magician_full.png
├── major_01_magician_detail.png
├── ...
├── major_21_world_full.png
└── major_21_world_detail.png
```
