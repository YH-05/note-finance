# 議論メモ: みつきナレッジDB Wave2拡充 — 世代コンテキスト・占術・心理学データ大規模投入

**日付**: 2026-04-07
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-04-07-mitsuki-knowledge-db-expansion

## 背景・コンテキスト

みつきのB+C+D融合モデル（同日`disc-2026-04-07-mitsuki-acquisition-strategy`で決定）のうち、D型プロダクト（テーマ別パーソナル分析）の自動生成基盤として、creator-neo4jのナレッジグラフを大規模拡充した。

前提:
- **Wave1完了時点**: 8世代ブロック（1965-2005）、基本7カテゴリ × 各ブロック
- **拡充目標**: みつきのターゲット層（30-50代女性）の親世代〜子世代まで網羅、占術・心理学の生データも格納

## 実施内容

### Wave2: 世代ブロック拡充（8→13ブロック）

| 追加ブロック | 概称 | 追加タイミング |
|------------|------|--------------|
| 1947-1954 | 団塊世代 | gen-expander Wave2 |
| 1955-1959 | しらけ世代 | gen-expander Wave2 |
| 1960-1964 | 新人類世代前期 | gen-expander Wave2 |
| 2006-2009 | Z世代後期 | gen-expander Wave2 |
| 2010-2012 | α世代前期 | gen-expander Wave2 |

カバレッジ: **1947〜2012年（65年間）**、合計13世代ブロック

### 新ConceptCategory追加

| カテゴリ | layer | 内容 |
|---------|-------|------|
| SpiritualPattern | generation | 占い入口・好みの占術・購買心理・コンテンツ共鳴パターン（11ブロック × 7変数） |
| LoveAndAttachmentPattern | generation | 愛着スタイル分布・ラブランゲージ・恋愛トラウマ・タロットアーキタイプ（11ブロック × 多変数） |

### 占術フルデータ投入

| ファイル | 内容 | 規模 |
|---------|------|------|
| `divination_tarot_78cards.json` | 大アルカナ22枚+小アルカナ56枚、心理学マッピング、スプレッド設計、投稿テンプレ | 191KB |
| `divination_cross_reference_templates.json` | タロット×星座、数秘×タロット、144パターン（数秘×星座）、D型プロダクトテンプレート変数定義 | 170KB |
| `divination_numerology_complete.json` | LifePath 1-9+11+22+33、運命数/魂の数/誕生日数、48 LP×愛着パターン、108 LP×パーソナルイヤーパターン | 167KB |
| `divination_astrology_complete.json` | 12星座+10天体+12ハウス+5アスペクト+144相性パターン | 186KB |

### 心理学フルデータ投入

| ファイル | 内容 | 規模 |
|---------|------|------|
| `psychology_mbti_16types.json` | MBTI 16型（性格・強み・恋愛パターン・仕事スタイル） | 46KB |
| `psychology_jung_cbt_hsp.json` | ユング分析心理学（12元型）、CBT認知の歪み、HSP特性 | 140KB |
| `psychology_attachment_bigfive_enneagram.json` | 愛着理論4型、BigFive 5因子、エニアグラム9型 | 126KB |
| `psychology_developmental_positive_adler_ta.json` | 発達心理学、ポジティブ心理学（VIA強み）、アドラー心理学、交流分析 | 136KB |

### Wikipedia データ追加（Tavily経由）

| ファイル | 内容 | 件数 |
|---------|------|------|
| `generation_wiki_culture_facts.json` | 7世代グループ × 文化的事実（就職氷河期、バブル、ゆとり教育等） | 195 Facts |
| `generation_wiki_social_facts.json` | 少子化・バブル・就職氷河期の統計データ | 93統計 + 66 Facts |
| `generation_wiki_psychology_facts.json` | 愛着理論・MBTI・タロット・占い市場（997億円規模、90%女性、80%が30-50代） | 25記事 |

## 技術的課題と解決

### Wikipedia MCP 権限エラー
- **問題**: `mcp__wikipedia__*` がバックグラウンドエージェントから権限拒否
- **原因**: `.claude/settings.json` の `permissions.allow` に未登録。非インタラクティブエージェントはauto-deny
- **解決**: `"mcp__wikipedia__*"` をallowリストに追加。当日の3エージェントはTavilyにフォールバック

### 孤立ノード修復
Wave2投入時、先行フェーズで作成されたFact/TipのABOUTリレーションが未接続（concept_id_refプロパティに保留）。世代Conceptノード作成後に直接Cypherで一括修復:
- 個別concept_id_ref修復: 82ノード
- wikiデータの広域範囲マッピング（`gen-1965-1974`→個別ブロック）: 629リレーション作成

## 決定事項

1. **dec-2026-04-07-kg-wave2-13blocks**: creator-neo4j世代コンテキストを13ブロック(1947-2012)に拡充完了
2. **dec-2026-04-07-spiritual-love-categories**: SpiritualPattern + LoveAndAttachmentPatternカテゴリを新設
3. **dec-2026-04-07-divination-psychology-full**: 占術・心理学フルデータをcreator-neo4jに投入完了
4. **dec-2026-04-07-wikipedia-mcp-allowlist**: Wikipedia MCP許可設定を.claude/settings.jsonに追加

## アクションアイテム（更新）

- [in_progress] **act-2026-04-07-001** D型プロダクト設計: DB基盤（cross_reference_templates + 144パターン変数定義）は構築済み。次は実装コード作成 (優先度: 高)
- [ ] **act-2026-04-07-002** 悩みフック型投稿のOK/NGガイドライン策定 → `posting_algorithm.md` に追記 (優先度: 高)
- [ ] **act-2026-04-07-003** 悩みフック型投稿のA/Bテスト実験設計 (優先度: 中)
- [ ] **act-2026-04-07-004** ココナラ商品ページドラフト（恋愛パターン分析¥500サンプル作成） (優先度: 中)

## 次回の議論トピック

- D型プロダクト自動生成コードの実装（creator-neo4jクエリ → プロンプト生成 → コンテンツ出力）
- posting_algorithm.mdへの悩みフック型ガイドライン追記
- D型プロダクト第1弾（恋愛パターン分析）のユーザーテスト設計

## 参考情報

- B+C+D融合モデル議論: `docs/plan/SideBusiness/2026-04-07_discussion-mitsuki-acquisition-strategy.md`
- 導線設計: `docs/plan/SideBusiness/2026-04-06_discussion-mitsuki-funnel-design.md`
- creator-neo4j接続: `bolt://localhost:7687`, database="creator", password="gomasuke"
- 投入スクリプトパターン: `.tmp/ingest_generation_context.py`
- 占い市場規模: 997億円（Tavily調査 2026-04-07）、ユーザーの90%が女性、80%が30-50代
