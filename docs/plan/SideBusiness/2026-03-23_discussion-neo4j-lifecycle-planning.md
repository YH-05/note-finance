# 議論メモ: neo4j-lifecycle スキル plan-project 完了

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

2026-03-22 に neo4j-lifecycle スキルの設計プラン（`docs/plan/2026-03-22_neo4j-lifecycle-skill-plan.md`）が作成された。本日、`/plan-project` ワークフローを使用してこのプランを GitHub Project + Issue に具体化した。

前回の議論: `disc-2026-03-22-neo4j-lifecycle-skill`（設計プラン承認）

## 議論のサマリー

### Phase 0（HF0）: プロジェクト方向確認
- プロジェクトタイプ: **skill** に確定
- スコープ: **全フェーズ採用**（Phase 0-F の7フェーズ）
- 既存インスタンス YAML: **含める**（creator/research/note の3インスタンス）

### Phase 1（HF1）: リサーチ結果とギャップ解消
- ontology-template.yaml: **ゼロから設計**（creator v2 に依存しない汎用テンプレート）
- entity_linker.py: **スクリプト改修も含む**（--instance パラメータ追加）
- Phase D: **独立実装**（kg-quality-check に依存しない）
- registry.yaml スキーマ: **実装時に設計**

### Phase 2（HF2）: 実装計画承認
- 18ファイル構成（新規17 + 変更1）
- リスク評価: Phase C の不可逆操作（高）、entity_linker.py 後方互換性（中）等

### Phase 3（HF3）: タスク分解
- 6 Issue / 4 Wave 構成で確定
- GitHub Project #94 + Issue #219-#224 を作成

## 決定事項

1. **ontology-template.yaml ゼロ設計** (`dec-2026-03-23-ontology-zero-design`): creator v2 に依存せず汎用テンプレートを新規設計
2. **entity_linker.py --instance 対応** (`dec-2026-03-23-entity-linker-instance`): スクリプト改修をスコープに含む。後方互換性必須
3. **Phase D 独立実装** (`dec-2026-03-23-phase-d-independent`): kg-quality-check に依存しない品質検証
4. **4 Wave 構成** (`dec-2026-03-23-wave-structure`): GitHub Project #94 に 6 Issue を 4 Wave で配置

## アクションアイテム

- [ ] Wave1: #219 インスタンス設定 YAML と registry.yaml 作成 (優先度: 高)
- [ ] Wave1: #220 テンプレートファイル群作成 (優先度: 高)
- [ ] Wave2: #221 Phase A-F フェーズガイド作成 (優先度: 高)
- [ ] Wave3: #222 SKILL.md + コマンドファイル作成 (優先度: 高)
- [ ] Wave3: #223 entity_linker.py 改修 (優先度: 中)
- [ ] Wave4: #224 エンドツーエンド検証 (優先度: 中)

## 成果物

| 成果物 | パス |
|--------|------|
| 計画書 | `docs/project/project-22/project.md` |
| 元プラン | `docs/project/project-22/original-plan.md` |
| GitHub Project | [#94](https://github.com/users/YH-05/projects/94) |
| Worktree | `/Users/yukihata/Desktop/.worktrees/note-finance/feature-prj94` |
| セッションデータ | `.tmp/plan-project-20260323-100000/` |

## 次回の議論トピック

- Wave 1 実装完了後のレビュー
- ontology-template.yaml の具体的なプレースホルダー設計
- entity_linker.py の後方互換性テスト方針
