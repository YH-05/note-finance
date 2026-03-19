# 議論メモ: AI画像プロンプト生成スキルの設計

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

note記事を公開する際、noteサムネイルやX投稿用サムネイルなどの画像が必要だが、現状は手動で作成する必要がある。既存スキル（generate-chart-image, generate-table-image）はデータ可視化専用で、イラスト・写真系の画像には非対応。AI画像生成ツール（Nano Banana）を活用してサムネイル画像を効率的に作成するため、プロンプト生成スキルを新設する。

## 議論のサマリー

### 論点1: スキルの範囲
- **選択肢**: プロンプト生成のみ / API自動生成 / 段階的拡張
- **決定**: プロンプト生成のみ。ユーザーがNano Bananaで手動実行。

### 論点2: ターゲットツール
- **選択肢**: ChatGPT (DALL-E) / Midjourney / 複数ツール対応
- **決定**: Nano Banana。英語の自然言語プロンプトで動作するAI画像生成・編集プラットフォーム。

### 論点3: 画像スタイル
- **選択肢**: フォトリアリスティック / フラットイラスト / コンセプチュアル / カテゴリ別使い分け
- **決定**: カテゴリ別に使い分け。

### 論点4: 画像の種類
- **決定**: noteサムネイル (1280x670) + X投稿用サムネイル (1200x675)。記事本文中画像は対象外。

### 論点5: ワークフロー統合タイミング
- **決定**: revised_draft完成後（article-publish前）

## 決定事項

1. **`generate-image-prompt`スキル新設**: Nano Banana向け英語プロンプト生成。プロンプトのみ、API連携なし。
2. **カテゴリ別スタイル定義**:
   - macro_economy / market_report → フォトリアリスティック
   - asset_management / side_business / investment_education → フラットイラスト
   - stock_analysis → コンセプチュアル + チャート要素
   - quant_analysis → テクニカル / アブストラクト
3. **タイミング**: revised_draft完成後、article-publish前
4. **出力先**: `{article_dir}/02_draft/image_prompts.md`

## アクションアイテム

- [x] generate-image-promptスキルを作成（skill-creatorエージェント使用）(優先度: 高) → **完了**

## 作成されたファイル

| ファイル | パス |
|---------|------|
| SKILL.md | `.claude/skills/generate-image-prompt/SKILL.md` |
| guide.md | `.claude/skills/generate-image-prompt/guide.md` |
| コマンド | `.claude/commands/generate-image-prompt.md` |

## 使い方

```
/generate-image-prompt @articles/macro_economy/2026-03-19_boj-rate-hike-yen-structural-analysis/
```

## 次回の議論トピック

- 実際にプロンプトを生成して品質を評価・チューニング
- 将来的なAPI連携（Nano Banana API or OpenAI DALL-E API）の検討

## 参考情報

- Nano Banana: https://nanobanana.io/ - テキストから画像を生成するAIプラットフォーム
- noteサムネイル推奨サイズ: 1280x670px
- X投稿用画像推奨サイズ: 1200x675px (16:9)
