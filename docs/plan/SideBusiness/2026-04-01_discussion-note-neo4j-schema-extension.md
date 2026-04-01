# 議論メモ: note-neo4j スキーマ拡張 — CodeEntity/Document ノードの導入

**日付**: 2026-04-01
**参加**: ユーザー + AI

## 背景・コンテキスト

note-neo4j は Discussion(21件)/Decision(54件)/ActionItem(25件) の3ラベル構成で運用していたが、
各ノードのテキスト中にリポジトリ内パスへの参照が暗黙的に埋め込まれており構造化されていなかった。

例:
- Discussion.topics: `["entity_linker", "ontology.yaml"]`
- Decision.content: `"scripts/ontology_loader.py アダプターで..."`
- ActionItem.description: `"neo4j_loader.py を強化..."`

これらを構造化し、影響分析・ホットスポット検出・トレーサビリティを可能にするためにスキーマを拡張した。

## 議論のサマリー

### 1. CodeEntity vs Document の2ラベル構成

単一ラベル + type 属性 ではなく、明確に2ラベルに分離する方針を採用。

- **CodeEntity**: Claude Code が「実行・参照して動作を変える」もの（scripts, modules, skills, agents, commands, rules, configs, tests）
- **Document**: 人間やLLMが「読んで理解する」もの（plan docs, guidelines, articles, project defs）

境界の判断: `.claude/rules/` は Claude Code が自動ロードするため CodeEntity 側。

### 2. MERGEキーと rename 追従

3案を比較:
- **案A（採用）**: path をキー + git ls-files 定期突合 → archived 更新
- 案B（不採用）: name+type 複合キー — 同名ファイル衝突リスク
- 案C（不採用）: RENAMED_TO リレーション — 過剰な複雑さ

archived ノードはリレーションごと残るため、過去の Decision との紐付きが消えない。

### 3. 粒度

ファイル単位 + ディレクトリ単位の両方をノード化。CONTAINS リレーションで階層表現。
ディレクトリノードは参照されたファイルの親ディレクトリのみ自動生成（全ディレクトリを網羅はしない）。

### 4. PR/Issue番号のノード化

不要と判断。テキスト内の参照として十分。

### 5. Document間 REFERENCES リレーション

不要と判断。過剰な接続は避ける。

### 6. Discussion.doc_path の構造化

RECORDED_IN リレーションに昇格（doc_path プロパティも後方互換で残す）。

## 決定事項

1. **CodeEntity ラベル導入**: path(ユニーク制約), type, name, status プロパティ
2. **Document ラベル導入**: path(ユニーク制約), doc_type→type, name, status プロパティ
3. **MERGEキー = path**: git ls-files 突合で archived 更新
4. **ファイル+ディレクトリ両方ノード化**: CONTAINS で階層表現
5. **新規リレーション6種**: RECORDED_IN, MENTIONS, AFFECTS, TARGETS, CONTAINS (+既存 RESULTED_IN, PRODUCED)
6. **バッチスクリプト実装完了**: `scripts/populate_note_code_entities.py`

## 実装結果

投入後のグラフ:
- CodeEntity: 50ノード（script 6, module 5, skill 5, command 6, agent 5, config 1, directory 22）
- Document: 33ノード（plan 21, guideline 2, directory 10）
- CONTAINS: 75, MENTIONS: 26, AFFECTS: 22, RECORDED_IN: 21, TARGETS: 9

ホットスポット上位:
1. `.claude/skills/investment-research/` — 5件 MENTIONS
2. `snippets/disclaimer.md` — 5件（MENTIONS+AFFECTS+TARGETS 横断）
3. `scripts/emit_research_queue.py` — 3件

## アクションアイテム

- [ ] project-discuss スキルに CodeEntity/Document 自動抽出ロジックを追加（新規 Discussion 作成時）(優先度: 中)
- [ ] 定期 git ls-files 突合バッチの設計・実装（archived 更新用）(優先度: 低)
- [ ] populate スクリプトの増分実行テスト（新 Discussion 追加後の再実行検証）(優先度: 低)
