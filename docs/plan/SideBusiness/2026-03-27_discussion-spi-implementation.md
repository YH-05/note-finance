# 議論メモ: スピ系アカウント実装完了記録

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

スピ系アカウント「みつき（美月）」の収益化戦略議論（占術選定・ペルソナ設計・収益構造）を経て、実装フェーズに移行。career_sister と同様のスキルコマンド制御型運用を構築した。

## 実装サマリー

### 作成ファイル一覧（11ファイル）

| カテゴリ | ファイル | 説明 |
|---------|---------|------|
| ペルソナ | `creator/mitsuki/persona.md` | みつきの完全なペルソナ定義 |
| アルゴリズム | `creator/mitsuki/posting_algorithm.md` | 10投稿サイクル・週4投稿・タロット×心理学マッピング |
| 状態管理 | `creator/mitsuki/posting_state.json` | 投稿サイクル・テーマ履歴の初期状態 |
| スキル | `.claude/skills/mitsuki-writer/SKILL.md` | 文体ルール・4投稿型・生成ワークフロー |
| コマンド | `.claude/commands/mitsuki-draft.md` | 週次ドラフト生成（5ステップ） |
| コマンド | `.claude/commands/mitsuki-publish.md` | 投稿フロー（7ステップ） |
| テンプレート | `creator/mitsuki/templates/numerology/README.md` | 数秘術テンプレートシステム概要 |
| テンプレート | `creator/mitsuki/templates/numerology/number_profiles.json` | 誕生数1-9のプロファイルデータ |
| テンプレート | `creator/mitsuki/templates/numerology/report_template.md` | 鑑定書テンプレート（5章構成） |
| テンプレート | `creator/mitsuki/templates/numerology/guidebook_template.md` | ガイドブック追加テンプレート（3章） |
| サンプル | `creator/mitsuki/templates/numerology/sample_number3.md` | サンプル出力（誕生数3） |

### 設計上の主要判断

1. **週4投稿（月水金日）**: career_sister の日3投稿とは異なり、週4投稿に最適化。10投稿サイクルは2.5週で1周。
2. **タロット×心理学マッピング**: 大アルカナ22枚×心理学概念の完全対応表を作成。テキストベースで画像不要。
3. **星座×心理学マッピング**: 12星座×心理学理論の対応表。エレメントローテーション（火→地→風→水）で均等分散。
4. **数秘術テンプレートシステム**: JSONプロファイル + テンプレートの分離設計。9種の誕生数記事をプログラマティックに生成可能。
5. **二段階収益構造**: 鑑定書（¥500-1,000）→ ガイドブック（¥2,000-3,000）のアップセル設計。

## 決定事項

1. みつきの投稿はcareer_sister同様、スキルコマンド（`/mitsuki-draft`, `/mitsuki-publish`）で制御する
2. 数秘術有料記事は `/mitsuki-numerology` コマンドで生成する（将来実装）
3. タロット・星座はテキストベース運用（画像生成不要）
4. note有料記事の無料/有料境界: 鑑定書は第1章前半まで無料、ガイドブックは第6章冒頭まで無料

## アクションアイテム

- [ ] creator-neo4j にみつき用素材を投入（タロットカード解説・星座×心理学テキスト） (優先度: 高)
- [ ] Threads アカウント開設・プロフィール設定 (優先度: 高)
- [ ] `/mitsuki-numerology` コマンド作成（数秘術鑑定書/ガイドブック生成） (優先度: 中)
- [ ] note アカウント開設・有料記事テスト投稿 (優先度: 中)
- [ ] 初回ドラフト生成テスト（`/mitsuki-draft` 実行） (優先度: 中)

## 次回の議論トピック

- creator-neo4j への素材投入フォーマット設計
- 初回投稿のタイミングとローンチ戦略
- 3アカウント（キャリアお姉さん・みつき・SPI）の相互導線設計

## 参考情報

- career_sister パターン: `creator/career_sister/` 配下の運用構造を踏襲
- Neo4j Discussion: `disc-2026-03-27-spi-implementation`
- 関連議論: `disc-2026-03-27-spi-persona-design`, `disc-2026-03-27-spi-divination-selection`, `disc-2026-03-27-spi-revenue-design`
