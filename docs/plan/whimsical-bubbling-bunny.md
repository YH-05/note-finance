# article-critique に finance-article-writer ルールチェックを追加

## Context

`/article-critique` コマンドは5つの批評エージェント（fact, compliance, structure, data, readability）で記事を評価するが、
これらは `.claude/resources/critique-criteria/` の汎用基準で動作しており、
`finance-article-writer` スキル（`.claude/skills/finance-article-writer/references/`）が定義するルールを直接チェックしていない。

初稿生成時に守られたルールが批評時に検証されないため、修正版で崩れても検出できないリスクがある。

### 現在チェックされていないルール

**common-rules.md:**
- 信頼度別表現パターン（verified→断定形, unverified→伝聞形 等）
- 参考データソースセクションの存在・形式（`## 参考データソース`）

**カテゴリ別ルール:**
- 文字数要件（stock: 4000-6000字, macro: 3000-5000字, asset: 2000-4000字 等）
- 必須セクション構成（各カテゴリのテンプレート順序）
- カテゴリ固有制約（macro→シナリオ分析, education→FAQ, quant→バックテスト透明性, asset→冒頭免責）
- カテゴリ別チェックリスト（各10-14項目）
- フロントマター必須項目（symbol, indicators, topic, strategy, theme 等）

## 実装方針

新規批評エージェント `finance-critic-writer-rules` を追加し、既存5エージェントと並列実行する。

## 変更ファイル一覧

| ファイル | 種別 | 内容 |
|---------|------|------|
| `.claude/agents/finance-critic-writer-rules.md` | **新規** | 批評エージェント定義 |
| `.claude/resources/critique-criteria/writer-rules-evaluation.md` | **新規** | 評価基準リファレンス |
| `.claude/commands/article-critique.md` | 修正 | Step 2/3 に新エージェント追加 |
| `.claude/resources/critique-criteria/scoring-methodology.md` | 修正 | 重み再配分（6エージェント化） |
| `.claude/agents/finance-reviser.md` | 修正 | 修正優先順位に writer_rules 追加 |

---

## Step 1: `finance-critic-writer-rules.md` 新規作成

**パス**: `.claude/agents/finance-critic-writer-rules.md`

既存エージェント（`.claude/agents/finance-critic-fact.md`）と同じフロントマター構造に従う。

### チェック対象（6サブエリア）

| サブエリア | ID接頭辞 | 内容 | quick | full |
|-----------|---------|------|-------|------|
| word_count | WR-WC | 総文字数 vs カテゴリ範囲 | o | o |
| sections | WR-SC | 必須セクションの存在・順序 | o | o |
| frontmatter | WR-FM | カテゴリ別必須フロントマター項目 | o | o |
| confidence_expression | WR-CE | 信頼度→表現パターンの対応 | - | o |
| category_constraints | WR-CC | カテゴリ固有制約 | - | o |
| checklist | WR-CL | カテゴリ別チェックリスト（他エージェント未カバー分） | - | o |

quick モードに word_count/sections/frontmatter を含める理由:
機械的に判定可能で、違反時のインパクトが大きい（文字数不足 = 記事として不成立）。

### 入力ファイル

```
- {article_dir}/02_draft/first_draft.md
- {article_dir}/meta.yaml（category, target_audience）
- {article_dir}/01_research/claims.json（信頼度表現チェック用, full のみ）
- .claude/skills/finance-article-writer/references/common-rules.md
- .claude/skills/finance-article-writer/references/{category}.md
```

### 出力 JSON スキーマ

```json
{
    "critic_type": "writer_rules",
    "score": 78,
    "category": "stock_analysis",
    "target_audience": "intermediate",
    "issues": [
        {
            "issue_id": "WR-WC001",
            "severity": "high | medium | low",
            "sub_area": "word_count | sections | frontmatter | confidence_expression | category_constraints | checklist",
            "location": { "section": "...", "line": "..." },
            "issue": "問題の説明",
            "rule_reference": "common-rules.md#section-7",
            "suggestion": "修正提案"
        }
    ],
    "word_count_check": {
        "actual": 3200, "min": 4000, "max": 6000,
        "status": "under | ok | over"
    },
    "section_check": {
        "required_sections": [...],
        "found_sections": [...],
        "missing_sections": [...],
        "order_correct": true
    },
    "frontmatter_check": {
        "required_fields": [...],
        "present_fields": [...],
        "missing_fields": [...]
    },
    "confidence_expression_check": {
        "total_claims_referenced": 12,
        "correct_expression": 10,
        "incorrect_expression": 2
    },
    "category_constraints_check": {
        "constraints_checked": 3, "passed": 2, "failed": 1
    },
    "checklist_results": {
        "total": 7, "passed": 5, "failed": 2
    }
}
```

### スコア計算式

```
score = 100 - (high x 15 + medium x 5 + low x 2)
```

severity マッピング:
- **high**: 文字数範囲外、必須セクション欠落、フロントマター必須項目欠落
- **medium**: セクション順序不正、カテゴリ制約未達、チェックリスト不合格
- **low**: セクション内文字数が推奨範囲外、表現パターンの軽微なずれ

### 既存エージェントとの重複回避

チェックリスト項目のうち、以下は他エージェントがカバー済みのためスキップ:
- 「禁止表現が含まれていない」→ compliance
- 「財務データに出典URLが埋め込まれている」→ fact
- 「ディスクレーマーが記事末尾に1箇所」→ compliance
- 「マークダウン表が画像化されている」→ article-quality-standards チェック

---

## Step 2: `writer-rules-evaluation.md` 新規作成

**パス**: `.claude/resources/critique-criteria/writer-rules-evaluation.md`

各カテゴリの具体的なチェック仕様を定義:

- カテゴリ別文字数範囲テーブル
- カテゴリ別必須セクションリスト（テンプレート順序）
- カテゴリ別フロントマター必須項目
- 信頼度→表現パターン対応表（common-rules.md セクション1から転記）
- カテゴリ別固有制約リスト
- カテゴリ別チェックリスト（他エージェント未カバー項目のみ抽出）

finance-article-writer/references/ のルールを「何をチェックするか」の視点で再構成したファイル。

---

## Step 3: `article-critique.md` 修正

**パス**: `.claude/commands/article-critique.md`

### Step 2 修正（95行目付近）

quick モードに Task 3 追加、full モードに Task 6 追加:

```
**quick モード**:
Task 1: finance-critic-fact
Task 2: finance-critic-compliance
Task 3: finance-critic-writer-rules（word_count, sections, frontmatter のみ）  ← 追加

**full モード**:
Task 1: finance-critic-fact
Task 2: finance-critic-compliance
Task 3: finance-critic-structure
Task 4: finance-critic-data
Task 5: finance-critic-readability
Task 6: finance-critic-writer-rules（全項目）  ← 追加
```

### Step 3 修正（137行目付近）

critic.json スキーマに `writer_rules` キー追加:

```json
"critics": {
    ...,
    "writer_rules": { ... }
}
```

critic.md テンプレートに新セクション追加:

```markdown
## ライター規約準拠: {score}/100
- 文字数: {actual}字 ({status}) — 範囲: {min}-{max}字
- 必須セクション: {found}/{total}
- フロントマター: {present}/{required}
- 信頼度別表現: {correct}/{total} (full時)
- カテゴリ制約: {passed}/{checked} (full時)
- チェックリスト: {passed}/{total} (full時)
```

### 完了報告テーブル修正（288行目付近）

```markdown
| ライター規約 | {writer_rules}/100 |
```

---

## Step 4: `scoring-methodology.md` 修正

**パス**: `.claude/resources/critique-criteria/scoring-methodology.md`

### エージェント別スコア計算式に追加（41行目付近）

```markdown
### writer_rules
score = 100 - (high x 15 + medium x 5 + low x 2)
```

### 総合判定の重み再配分（49行目付近）

| 批評タイプ | 変更前 | 変更後 | 差分 |
|-----------|--------|--------|------|
| compliance | 30% | 25% | -5 |
| fact | 25% | 22% | -3 |
| data_accuracy | 20% | 17% | -3 |
| structure | 15% | 12% | -3 |
| readability | 10% | 9% | -1 |
| **writer_rules** | - | **15%** | **+15** |

writer_rules 15% の根拠:
- 仕様準拠の違反（文字数不足、セクション欠落）は他エージェントが検出できない構造的問題
- compliance（法的リスク）より低いが、structure/readability より高い位置づけ

### quick モード重み

| 批評タイプ | quick重み |
|-----------|----------|
| compliance | 45% |
| fact | 35% |
| writer_rules | 20% |

---

## Step 5: `finance-reviser.md` 修正

**パス**: `.claude/agents/finance-reviser.md`

### 修正優先順位に追加（22行目付近）

```markdown
1. **最優先**: compliance の critical/high
2. **高優先**: fact の high
3. **高優先**: data_accuracy の high
4. **高優先**: writer_rules の high（文字数不足、セクション欠落、フロントマター欠落）  ← 追加
5. **中優先**: structure の high/medium
6. **中優先**: readability の high/medium
7. **中優先**: writer_rules の medium（カテゴリ制約、チェックリスト）  ← 追加
8. **低優先**: その他の low
```

### writer_rules 修正方針セクション追加（readability 修正方針の後）

```markdown
## writer_rules 問題の修正方針

### 文字数不足/超過
- 不足: 分析の深掘り、具体例追加、データ解釈の追加
- 超過: 冗長表現の削除、重複ポイントの統合

### セクション欠落
- カテゴリルールのテンプレートに従いセクション追加
- sources.json / claims.json から内容を補完

### フロントマター欠落
- meta.yaml と記事内容から推定して追加

### 信頼度別表現の修正
- claims.json の confidence に応じて表現パターンを修正
  - high/>=0.8 → 断定形
  - medium/0.5-0.79 → 引用形
  - low/<0.5 → 可能性形

### カテゴリ制約の修正
- カテゴリ別ルールファイルの制約に従い内容を追加
```

### 修正履歴テンプレートに追加（113行目付近）

```markdown
- writer_rules 修正: {count}
```

---

## 検証方法

既存記事でテスト実行:

```bash
# 1. full モードで実行（全チェック）
/article-critique @articles/stock_analysis/2026-03-28_us-telecom-sector/ --mode full

# 2. critic.json に writer_rules セクションが含まれるか確認
cat articles/stock_analysis/2026-03-28_us-telecom-sector/02_draft/critic.json | jq '.critics.writer_rules'

# 3. critic.md にライター規約準拠セクションがあるか確認
grep "ライター規約準拠" articles/stock_analysis/2026-03-28_us-telecom-sector/02_draft/critic.md

# 4. revised_draft.md の修正履歴に writer_rules 修正が含まれるか確認
grep "writer_rules" articles/stock_analysis/2026-03-28_us-telecom-sector/02_draft/revised_draft.md

# 5. quick モードでも word_count/sections/frontmatter がチェックされるか確認
/article-critique @articles/stock_analysis/2026-03-28_us-telecom-sector/ --mode quick
```

## 実装順序

1. `writer-rules-evaluation.md` 作成（評価基準定義）
2. `finance-critic-writer-rules.md` 作成（エージェント定義）
3. `scoring-methodology.md` 修正（重み再配分）
4. `article-critique.md` 修正（Step 2/3 にエージェント追加）
5. `finance-reviser.md` 修正（優先順位・修正方針追加）
6. 既存記事でテスト実行
