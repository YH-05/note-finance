# 議論メモ: /topic-discovery コマンド・スキルの非推奨化

**日付**: 2026-04-27
**参加**: ユーザー + AI

## 背景・コンテキスト

- `topic-suggest`（軽量スキル）と `/topic-discovery`（KGファーストのオーケストレーター）が並存しており、機能の重複と運用の複雑化が発生していた。
- ユーザーから「`/topic-suggest` と `/topic-discovery` の違いは？」と質問があり、機能比較を実施。
- 議論の結果、`/topic-discovery` を非推奨化し、`topic-suggest` スキルに一本化する方針で合意。

## 議論のサマリー

- `/topic-discovery` は KG ファースト（research-neo4j）+ Web 検索 + topic-suggester による高機能オーケストレーターだったが、`topic-suggest` スキル（旧シンプル版）と機能領域が重複していた。
- ユーザーの判断で `/topic-discovery` を trash 移動・非推奨化することを決定。
- 関連参照のメンテナンスとして、CLAUDE.md と他スキル/エージェントから壊れたパス参照を除去。

## 決定事項

1. `/topic-discovery` コマンドおよび `topic-discovery` スキルを非推奨化し、`trash/2026-04-27_topic-discovery-deprecated/` 配下に退避する。
2. `CLAUDE.md` のスラッシュコマンド表から `/topic-discovery` の行を削除する。
3. 残存する参照（壊れたパス）は `topic-suggest` スキルに置き換えるか除去する。
4. `save-to-article-graph` スキルの `--command topic-discovery` オプション値はCLI互換のため残置する（過去出力JSONとの互換維持）。

## アクションアイテム

- [x] `topic-discovery.md`（command）と `topic-discovery/`（skill）を `trash/2026-04-27_topic-discovery-deprecated/` に移動
- [x] `CLAUDE.md` から `/topic-discovery` の記載を削除
- [x] `kg-summary.md`、`ask-research-neo4j/SKILL.md` の関連リンクを `topic-suggest` スキル参照に置換
- [x] `topic-suggester.md` エージェントから壊れたパス参照（`topic-discovery/references/`）を除去
- [x] `web-search/SKILL.md` のパターン3名称変更と壊れたリンクを削除
- [ ] 中期: `topic-suggest` スキルに KG 照会フェーズを段階的に取り込むか、専用コマンド化を検討（優先度: 中）
- [ ] 中期: `save-to-article-graph` の `--command topic-discovery` オプション値の扱い（リネーム or 残置）を決定（優先度: 低）

## 次回の議論トピック

- `topic-suggest` スキルへの KG マイニング機能の統合可否
- `save-to-article-graph` のコマンド名体系の整理

## 影響を受けたファイル

- `CLAUDE.md`
- `.claude/commands/kg-summary.md`
- `.claude/skills/ask-research-neo4j/SKILL.md`
- `.claude/agents/topic-suggester.md`
- `.claude/skills/web-search/SKILL.md`

## 退避先

- `trash/2026-04-27_topic-discovery-deprecated/topic-discovery.command.md`
- `trash/2026-04-27_topic-discovery-deprecated/topic-discovery.skill/`
