# 議論メモ: ライフプランニング・資金計画カテゴリ新設（CFP相当品質）

**日付**: 2026-04-30
**参加**: ユーザー + AI
**プロジェクト**: 株投資ラボ収益化
**前段**: [disc-2026-04-27-kabu-lab-monetization-strategy](2026-04-27_discussion-kabu-lab-monetization-strategy.md)

## 背景・コンテキスト

株投資ラボ収益化戦略において asset_management カテゴリに幅を持たせる必要がある。
ユーザーの将来計画として **IFA（Independent Financial Advisor）として独立し、その顧客獲得につなげる** ことが視野にあり、CFP（Certified Financial Planner）レベル相当のクオリティを持つ資産形成記事の制作基盤を整備する判断に至った。

現状の asset_management カテゴリは CFP6分野のうち「金融資産運用」のみをカバーしており、残5分野（ライフプランニング・リスク管理・タックスプランニング・不動産・相続）は未対応。本議論ではまず「ライフプランニングと資金計画」分野を新カテゴリ life_planning として独立実装した。

## 議論のサマリー

### 検討した拡張範囲

CFP6分野とのギャップを整理した結果、life_planning が最初の拡張対象として選定された:

| CFP分野 | 現状 | 今回対応 |
|---------|------|---------|
| ライフプランニング・資金計画 | △（NISAのみ） | **新カテゴリ life_planning として新設** |
| リスク管理（保険） | ✗ | life_planning 内 insurance_basics として暫定吸収 |
| 金融資産運用 | ○（asset_management） | 既存維持 |
| タックスプランニング | △（iDeCoのみ） | retirement_design に部分含む（独立カテゴリは将来） |
| 不動産 | ✗ | housing_loan として部分対応 |
| 相続・事業承継 | ✗ | 未対応（将来カテゴリ） |

### IFA独立を見据えた品質基準

IFA登録前の現時点で「IFAとして」表記は不可（金商法上の業務独占違反になりうる）。よって以下を遵守:

- 肩書き表記は「FP」「資産形成リサーチャー」に留める
- 業際規制4法（社労士法・税理士法・保険業法・金商法）への抵触を厳格チェック
- 個別計算は「モデルケース」表記、特定商品推奨は禁止

### CFP級品質階層の設計

文字数・深さで二層化する meta.yaml フィールド `quality_tier` を導入:

| tier | 文字数 | ペルソナ | 一次出典 | 計算式 |
|------|--------|----------|----------|--------|
| cfp_grade（既定） | 12000-15000字 | 3-4ケース必須 | ランクS 50%以上 | 必須 |
| standard | 8000-10000字 | 任意 | A+B 60%以上 | 任意 |

### テーマ設計（7テーマ）

| キー | 内容 |
|------|------|
| pension | 公的年金（国民年金/厚生年金/受給/繰上繰下/在職老齢） |
| social_insurance | 社会保険（健保/介護/雇用/労災/標準報酬月額） |
| housing_loan | 住宅ローン（変動固定/借換/団信/控除/フラット35） |
| education_fund | 教育資金（学資保険/こどもNISA/奨学金/教育資金贈与） |
| retirement_design | リタイアメント設計（退職金/取崩し/4%ルール/年金繰下げ） |
| life_event_planning | ライフイベント設計（CF表/結婚/出産/介護/育休） |
| insurance_basics | 保険基礎（公的保障/医療/がん/就業不能） |

## 決定事項

1. **life_planning カテゴリを新設**し、CFP6分野のうち「ライフプランニングと資金計画」を扱う7テーマを定義
2. **品質階層 quality_tier の導入**: cfp_grade（既定）と standard の二層化を meta.yaml に反映
3. **業際規制4法のコンプライアンスチェックを finance-critic-compliance に統合**し、life-planning-reviser で違反パターンを自動修正
4. **信頼性ランク S（一次出典）を新設**し、life_planning 記事では 50%以上の使用を必須化
5. **IFA 登録前は「IFAとして」表記を全面禁止**。FPまたは資産形成リサーチャー表記に統一

## 実装成果

### 新規作成

- `data/config/life-planning-themes.json` — 7テーマ + regulatory_framework
- `.claude/skills/finance-article-writer/references/cfp-grade-rules.md` — CFP級共通ルール
- `.claude/skills/finance-article-writer/references/life-planning.md` — カテゴリ固有ルール
- `.claude/agents/life-planning-reviser.md` — 業際規制対応リバイザー
- `scripts/prepare_life_planning_session.py` — 一次出典RSSセッション生成
- `.claude/commands/life-planning.md` — `/life-planning` コマンド
- `articles/life_planning/` — 記事格納ディレクトリ

### 更新

- `data/config/rss-presets-jp.json` — 一次出典9フィード追加（厚労省/年金機構/国税庁/文科省/JHF/協会けんぽ/生保協会/損保協会/JASSO）
- `.claude/skills/finance-article-writer/SKILL.md` — life_planning 対応
- `.claude/agents/finance-critic-compliance.md` — 業際規制4法チェック section 追加
- `.claude/commands/new-finance-article.md` / `.claude/commands/article-init.md` — カテゴリ選択肢追加

## アクションアイテム

- [ ] 試行記事1本目を執筆（pension or retirement_design テーマで CFP-grade 品質を検証）（優先度: 高）
- [ ] 試行結果に基づき cfp-grade-rules.md と life-planning.md の調整（優先度: 高）
- [ ] RSS フィードURL の動作確認（厚労省・年金機構・国税庁等で実取得テスト）（優先度: 中）
- [ ] emit_research_queue.py の life_planning 対応確認（research-neo4j 投入経路）（優先度: 中）
- [ ] 残CFP分野の段階的展開計画（四半期に1分野ペース）（優先度: 低）

## 次回の議論トピック

- 試行記事1本目のレビューと品質ルール微調整
- タックスプランニング独立カテゴリの設計（retirement_design からの分離検討）
- 相続・事業承継カテゴリの設計
- IFA登録に向けたコンテンツポートフォリオ要件の整理（実績記事数・テーマ網羅性）

## 参考情報

- CFP6分野: 日本FP協会の公式分類に準拠
- 業際規制根拠: 社労士法第27条、税理士法第52条、保険業法第275条、金商法第28・29条
- 既存類似実装: asset_management カテゴリ（参照基盤として流用）

## 保存先

- Discussion: `disc-2026-04-30-life-planning-category-creation`
- Project: 株投資ラボ収益化
- 前段ディスカッション: `disc-2026-04-27-kabu-lab-monetization-strategy`（FOLLOWED_BY 関係）
