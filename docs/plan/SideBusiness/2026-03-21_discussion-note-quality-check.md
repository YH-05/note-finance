# 議論メモ: note-neo4j 品質チェックスキル作成と初回実行・データ修正

**日付**: 2026-03-21
**参加**: ユーザー + AI

## 背景・コンテキスト

既存の `kg-quality-check` スキルは research-neo4j（port 7688）専用で KG v2 スキーマを前提としている。note-neo4j（port 7687）は Discussion/Decision/ActionItem/Research の異なるスキーマを持つため、専用の品質チェックスキルが必要だった。

## 議論のサマリー

### 1. スキル作成可否の判断

ユーザーが `/kg-quality-check` を note-neo4j に使えるか質問。回答: No（MCP ツールとスキーマの不一致）。note-neo4j 用の専用スキル作成を提案し、承認を得て実装。

### 2. スキル構成

skill-creator エージェントで `.claude/skills/note-quality-check/SKILL.md` と `.claude/commands/note-quality-check.md` を作成。7カテゴリ（6定量+LLM-as-Judge）で100点満点評価。

### 3. 初回実行結果

総合スコア: **80.4/100（Rating B）**

| カテゴリ | スコア | 加重スコア |
|---------|--------|-----------|
| Completeness | 78% | 19.5 |
| Consistency | 72% | 14.4 |
| Orphan | 100% | 15.0 |
| Staleness | 100% | 10.0 |
| Structural | 90% | 9.0 |
| DocSync | 3% | 0.2 |
| LLM-as-Judge | 82% | 12.3 |

### 4. データ修正の必要性と方法

ユーザーが「データ投入パイプラインの修正は必要か？」と質問。回答: No。note-neo4j にはパイプラインが存在せず、project-discuss スキルのプロンプトが投入ロジックそのもの。A（Cypher 直接修正）+ B（スキルプロンプト更新）で対応。

### 5. 修正実行

**A. 一回限りのデータ修正:**
- Decision status: `implemented`→`active`(6件), `completed`→`superseded`(1件)
- ActionItem status: `deferred`→`blocked`(1件), `pending`→`completed`(2件), `pending`→`blocked`(1件)
- 異常リレーション: RESULTED_IN(Discussion→Discussion) → FOLLOWED_BY(1件)
- Decision created_at 補完: 31件（decided_at から自動設定）

**B. project-discuss スキル更新:**
- Discussion テンプレートに topics/doc_path 必須化
- Decision テンプレートに created_at/context 必須化、status 許可値明記
- ActionItem テンプレートに status 許可値明記、completed→completed_at/blocked→blocked_reason 必須化
- Decision ID にスラッグ形式も許可する規約拡張
- MUST セクションに7項目のバリデーションルール追加

### 6. 修正後検証

全検証パス: 不正 status 0件、異常リレーション 0件、created_at 欠損 0件。

## 決定事項

1. **note-quality-check スキルを新規作成**: 6カテゴリ定量計測 + LLM-as-Judge の7カテゴリ、100点満点評価
2. **品質チェック結果に基づくデータ修正を実行**: status 正規化、created_at 補完、異常リレーション修正（合計42件修正）
3. **project-discuss スキルにバリデーションルールを追加**: status 許可値、必須フィールド、ActionItem 状態遷移ルール
4. **Decision ID にスラッグ形式も許可する規約拡張**: 連番・スラッグ併用、Discussion 内では統一

## アクションアイテム

- [ ] Discussion の topics を一括設定（34件未設定、優先度: 低）
- [ ] Discussion の doc_path を一括設定（34件未設定、優先度: 低）

## 次回の議論トピック

- note-quality-check の定期実行体制（頻度、アラート閾値）
- DocSync スコア改善（doc_path 一括設定後の再計測）
- LiteParse + note-quality-check の結果を踏まえた PDF パイプライン全体の見直し

## 参考情報

- note-quality-check スキル: `.claude/skills/note-quality-check/SKILL.md`
- note-quality-check コマンド: `.claude/commands/note-quality-check.md`
- project-discuss スキル（更新後）: `.claude/skills/project-discuss/SKILL.md`
- LiteParse 調査メモ: `docs/plan/SideBusiness/2026-03-21_discussion-liteparse-evaluation.md`
