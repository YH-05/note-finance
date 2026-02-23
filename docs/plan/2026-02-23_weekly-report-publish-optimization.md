# 週次レポート note.com公開最適化フロー実装計画（ブラッシュアップ版）

## Context

`/generate-market-report --weekly` が生成する `articles/weekly_report/{YYYY-MM-DD}/02_edit/weekly_report.md` を note.com 公開用に最適化するコマンドとスキルを実装する。

元プランを以下の点でブラッシュアップ：
- **批評エージェントの実際の入出力仕様**に合わせた具体的なプロンプト設計
- **compliance fail 時の処理中断**（公開不可制約）を明示
- **critic.json 統合フロー**の追加（3ファイル → 1ファイル → reviser へ渡す）
- **finance-reviser の入出力マッピング**の明確化（sources.json 不要の指示など）
- **エラーハンドリング体系**（E001〜E005）の体系化

---

## 作成ファイル（3件）

### 1. `.claude/skills/weekly-report-publish-optimization/SKILL.md`

```yaml
---
name: weekly-report-publish-optimization
description: |
  週次レポート（02_edit/weekly_report.md）をnote.com公開用に最適化するスキル。
  批評→修正→スニペット挿入のフローを提供し、03_published/weekly_report.md を生成する。
  /publish-weekly-report コマンドで使用。週次レポートのnote.com投稿準備時にのみ使用。
allowed-tools: Read, Write, Edit, Glob, Grep, Task
---
```

標準セクション：目的、いつ使用するか、前提条件、プロセス（Phase A〜E 概要）、リソース（→ guide.md）、使用例（3個）、品質基準（MUST/SHOULD）、エラーハンドリング（E001〜E005）、完了条件、関連スキル

### 2. `.claude/skills/weekly-report-publish-optimization/guide.md`

| セクション | 内容 |
|-----------|------|
| note.com最適化ルール | 段落長、テーブル列数、見出し、太字ルール一覧 |
| スニペット挿入ガイド | 各スニペットの挿入位置・具体例 |
| 禁止表現と代替表現一覧 | compliance 禁止表現 → 代替表現マッピング |
| 批評エージェントへの追加指示パターン | 週次レポート固有の評価観点（各エージェント別） |
| 修正優先順位と判断基準 | compliance fail 時の中断ロジックを含む |
| 週次レポート構成と各セクションの評価基準 | 8セクション・各文字数・列数の基準 |
| 出力品質チェックリスト | Phase D の詳細項目 |

### 3. `.claude/commands/publish-weekly-report.md`

```yaml
---
description: 週次レポートをnote.com公開用に最適化します。批評→修正→スニペット挿入を自動実行し 03_published/weekly_report.md を生成。
argument-hint: [YYYY-MM-DD]
---
```

---

## 修正ファイル（2件）

### 4. `.claude/commands/generate-market-report.md`

Phase 8「次のアクション」に `/publish-weekly-report {REPORT_DATE}` への誘導を1〜3行追記。

### 5. `CLAUDE.md`

Slash Commands テーブルに 1 行追加：
```
| `/publish-weekly-report` | 週次レポートをnote.com公開用に最適化（批評→修正→スニペット挿入） |
```

---

## コマンドフロー詳細（`/publish-weekly-report`）

```
Phase A: 初期化
  └ Step A.1: 引数 YYYY-MM-DD から REPORT_DIR を特定。引数なし時は最新ディレクトリを自動検出
  └ Step A.2: 02_edit/weekly_report.md の存在確認（なければ E001 で中断）
  └ Step A.3: 03_published/ ディレクトリ作成（mkdir -p）
  └ Step A.4: 既存の 03_published/weekly_report.md がある場合は上書き確認

Phase B: 批評（3エージェント逐次実行）
  └ Step B.1: finance-critic-readability
       追加指示: 段落長（3-4行）、テーブル列数（4列以下）、ハイライトのフック確認
       出力先: 03_published/critic_readability.json
  └ Step B.2: finance-critic-structure
       追加指示: カテゴリ=market_report、最初の3行、セクション遷移、H4禁止確認
       出力先: 03_published/critic_structure.json
  └ Step B.3: finance-critic-compliance
       追加指示: 末尾簡易免責事項を正式スニペットに差し替えが必要と指摘、snippets 3種の挿入箇所確認
       出力先: 03_published/critic_compliance.json
  └ Step B.4: compliance ステータスチェック ⚠️重要
       "fail" の場合 → E002 で Phase C をスキップして処理中断（公開不可）
       "warning"/"pass" → 続行
  └ Step B.5: critic.json 統合
       3ファイルを読み込み { "critics": { readability, structure, compliance } } として統合
       出力先: 03_published/critic.json

Phase C: 修正（finance-reviser）
  └ Step C.1: finance-reviser 実行
       入力マッピング指示（重要）:
         - "first_draft.md" = 02_edit/weekly_report.md を読み込む
         - "critic.json" = 03_published/critic.json を使用
         - "sources.json" は不要（週次レポートには存在しない）
       修正指示:
         - スニペット挿入（not-advice.md → タイトル直後、investment-risk.md + data-source.md → 末尾の簡易免責事項と差し替え）
         - テーブルを最大4列に制限
         - 段落を3-4行に分割
         - 禁止表現を代替表現に置換
         - H4以下の見出しを H3 に変換
         - 文字数目標: 5,000〜8,000字（スニペット+200字込み）
       出力先: 03_published/weekly_report.md（"revised_draft.md" ではなく "weekly_report.md" として保存を明示）
  └ Step C.2: 出力ファイル存在確認（なければ E003）

Phase D: 最終検証
  └ Step D.1: スニペット挿入確認（3種）
       not-advice.md の冒頭文字列がヘッダー部に存在するか
       investment-risk.md の冒頭文字列がフッター部に存在するか
       data-source.md の冒頭文字列がフッター部に存在するか
       → 未挿入なら E004 警告（手動挿入で続行可能）
  └ Step D.2: テーブル列数チェック（5列以上を検出 → 警告）
  └ Step D.3: 禁止表現の最終スキャン（残存 → E005 警告）
  └ Step D.4: 文字数カウント（目標 5,000〜8,000字）

Phase E: 完了報告
  └ 処理サマリー・批評スコア（3種）・修正件数・最終検証結果をテーブル表示
  └ 次のアクション: 出力確認コマンド + note.com への手動投稿案内
```

---

## エラーハンドリング体系

| コード | 発生条件 | 対処 |
|--------|---------|------|
| E001 | `02_edit/weekly_report.md` 不在 | `/generate-market-report --weekly` の実行を案内して中断 |
| E002 | compliance ステータス = "fail" | critical 問題を列挙して Phase C をスキップ・中断。02_edit 修正後に再実行を促す |
| E003 | finance-reviser が出力を生成しなかった | reviser 再実行を促す。手動修正の指示を表示 |
| E004 | スニペット未挿入（1種以上） | 未挿入スニペットのパスと挿入位置を表示（警告のみ、続行可） |
| E005 | 禁止表現が残存 | 残存箇所と代替表現を表示（警告のみ、続行可） |

---

## 設計上の重要な決定事項

| 決定項目 | 決定内容 | 理由 |
|---------|---------|------|
| 批評実行順序 | 逐次（readability → structure → compliance） | compliance fail 判定後に後続処理を中断するため |
| compliance fail の扱い | 処理中断（公開禁止） | 金商法対応の最重要制約 |
| エージェント定義の変更 | しない | 週次固有の指示はコマンドプロンプトで渡す |
| finance-reviser の出力ファイル名 | `weekly_report.md`（`revised_draft.md` ではない） | ディレクトリ規約に従う。プロンプトで明示 |
| sources.json | 不要として明示 | 週次レポートには存在しないため reviser に明示する |

---

## 既存リソース再利用マッピング

| リソース | パス | Phase |
|---------|------|-------|
| 可読性批評 | `.claude/agents/finance-critic-readability.md` | B.1 |
| 構成批評 | `.claude/agents/finance-critic-structure.md` | B.2 |
| コンプラ批評 | `.claude/agents/finance-critic-compliance.md` | B.3 |
| 修正エージェント | `.claude/agents/finance-reviser.md` | C.1 |
| 免責事項 | `snippets/not-advice.md` | C.1 ヘッダー挿入 |
| リスク開示 | `snippets/investment-risk.md` | C.1 フッター挿入 |
| データソース | `snippets/data-source.md` | C.1 フッター挿入 |
| スキルテンプレート | `template/skill/SKILL.md` | SKILL.md の雛形 |

---

## 品質基準

### 必須（MUST）

- [ ] `snippets/not-advice.md` がタイトル直後に挿入されている
- [ ] `snippets/investment-risk.md` がフッターに挿入されている
- [ ] `snippets/data-source.md` がフッターに挿入されている
- [ ] compliance ステータスが "pass" または "warning"（"fail" は出力禁止）
- [ ] 禁止表現（「買うべき」等）が含まれていない
- [ ] テーブルが 4 列以下

### 推奨（SHOULD）

- 出力文字数が 5,000〜8,000 字
- 可読性スコア 75 以上
- 段落が 3〜4 行で適切に改行されている

---

## 検証方法

```bash
# 1. コマンド実行
/publish-weekly-report 2026-02-23

# 2. 生成ファイルの確認
ls articles/weekly_report/2026-02-23/03_published/
# 期待: weekly_report.md, critic.json, critic_readability.json, critic_structure.json, critic_compliance.json

# 3. スニペット挿入確認
grep "本記事は一般的な情報提供を目的としており" articles/weekly_report/2026-02-23/03_published/weekly_report.md
grep "投資には元本割れリスクがあります" articles/weekly_report/2026-02-23/03_published/weekly_report.md
grep "本記事で使用しているデータは" articles/weekly_report/2026-02-23/03_published/weekly_report.md

# 4. 禁止表現の不在確認（出力が空なら PASS）
grep -E "買うべき|売るべき|絶対に上がる|必ず儲かる|おすすめ銘柄|今が買い時" \
  articles/weekly_report/2026-02-23/03_published/weekly_report.md

# 5. 文字数確認（目標: 5,000〜8,000字）
wc -m articles/weekly_report/2026-02-23/03_published/weekly_report.md

# 6. 目視確認
cat articles/weekly_report/2026-02-23/03_published/weekly_report.md
```
