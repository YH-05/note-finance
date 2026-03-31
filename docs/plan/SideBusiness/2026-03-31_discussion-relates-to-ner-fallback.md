# 議論メモ: RELATES_TO 欠落防止 — NER 自動補完実装

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j 投入パイプライン整備の一環として、RELATES_TO 欠落問題に取り組んだ。
2026-03-31 時点で 537件の Fact が Entity 接続なし（web-research 438件・pdf-pipeline 14件等）。

## 議論のサマリー

### 現状確認

パイプラインの挙動を調査した結果、孤立 Fact の2つの根本原因を特定:

- **原因A**: LLM が `about_entities` を空で返した（`chunk.entities` フォールバックも空）
- **原因B**: `about_entities` に名前はあるが `entity_name_to_id` にマッチしない

`_resolve_entity_rels()` は `entity_name_to_id.get(name)` が None の場合にサイレントスキップ。
フォールバックロジック（base.py:503、helpers.py:683）は既に実装済みだが、
両方空の場合は RELATES_TO が作成されない。

### 設計選択

3つのオプションを比較検討し、NER 自動補完（オプション③）を選択:
1. ログ警告のみ → 可視化のみで根本解決なし
2. 投入後バリデーション → 検知できるが補完しない
3. **NER 自動補完** → Haiku で content から entity を抽出して about_entities に補完

### 実装設計

**挿入ポイント**: `entity_linker.py` の `resolve_all()` 前処理

```
entity_linker.py main()
  ↓  (--ner-fallback 有効時)
  _ner_fill_about_entities(data)
    ├─ sources[].chunks[].facts/claims[about_entities=[]] を収集
    ├─ Haiku バッチ NER（20件/バッチ）→ entity名リスト
    ├─ fact/claim.about_entities に設定
    └─ data.entities にも追加（重複排除）
  ↓
  resolve_all()  ← NER抽出分も entity_name_to_id で解決
```

## 決定事項

1. **NER 自動補完を entity_linker.py に実装**: `--ner-fallback` フラグで有効化
2. **save-to-research-graph スキルに --ner-fallback を追加**: 標準投入フローで自動補完が動作
3. **エラー時サイレントスキップ**: API エラーや NER 失敗時も投入を継続

## アクションアイテム

- [x] Issue #300 作成・PR #301 実装完了（2026-03-31）

## 次回の議論トピック

- 577件の真の孤立 Fact 修復（LLM NER バッチ: act-2026-03-31-kg-004）
- ABOUT/MENTIONS セマンティクス整理（act-2026-03-31-kg-005）
- neo4j-lifecycle Phase C 実行（act-2026-03-31-kg-006）

## 参考情報

- PR #301: entity_linker.py --ner-fallback 実装
- Issue #300: https://github.com/YH-05/note-finance/issues/300
- 孤立 Fact 件数（2026-03-31）: 537件（web-research 438件が主体）
