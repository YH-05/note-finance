# 議論メモ: Obsidianでのプロジェクト管理統合

**日付**: 2026-03-09
**参加**: ユーザー + AI

## 背景・コンテキスト

プロジェクトの進捗管理や全体像・詳細管理をObsidianでも行いたいという要望。
現状はNeo4j + docs/plan/SideBusiness/ + GitHub Projectsで管理していたが、
Obsidianのリンク機能やダッシュボード表示で全体を俯瞰したいニーズ。

## 議論のサマリー

### 論点1: 管理場所
- 選択肢: note-finance Vault / prj-note Vault / ハイブリッド / 新規Vault
- **決定**: note-finance Vault内の `docs/obsidian/` に構築
- 理由: コードとドキュメントの一体管理、git履歴が残る

### 論点2: 管理内容の範囲
- **決定**: 全データソースを網羅
  - プロジェクト全体像（ダッシュボード + MOC）
  - タスク/TODO管理（Neo4j ActionItem同期）
  - 金融記事管理（執筆・公開状況）
  - Neo4jデータ可視化（統計・グラフ概要）
  - リサーチ情報（docs/plan/ + Neo4j + GitHub Issues + RSS）

### 論点3: Neo4jとの役割分担
- **決定**: Neo4j = Single Source of Truth、Obsidian = 閲覧ビュー
- 同期方向: Neo4j → Obsidian（一方向）
- 同期手段: `/sync-to-obsidian` コマンド（Phase 2で実装）

## 決定事項

1. **管理場所**: note-finance Vault内の `docs/obsidian/` に構築
2. **同期方針**: Neo4j→Obsidian一方向同期、`/sync-to-obsidian`コマンドで更新
3. **管理対象**: 全データソース（PJ全体像、TODO、金融記事、Neo4j、リサーチ情報全て）

## 作成したファイル（Phase 1完了）

```
docs/obsidian/
├── _dashboard.md                          # プロジェクト全体ダッシュボード
├── _MOC.md                                # Map of Content
├── sidebusiness/
│   ├── _dashboard.md                      # 副業PJダッシュボード
│   ├── _actionitems.md                    # TODO一覧（Neo4j同期）
│   ├── _decisions.md                      # 決定事項一覧（Neo4j同期）
│   ├── _discussions.md                    # 議論履歴（Neo4j同期）
│   └── research/_index.md                 # リサーチインデックス
├── finance/
│   ├── _dashboard.md                      # 金融記事ダッシュボード
│   └── news/_weekly-digest.md             # 週次ニュースダイジェスト
└── knowledge-graph/
    └── _overview.md                       # Neo4jグラフ概要
```

## アクションアイテム

- [ ] `/sync-to-obsidian` コマンド作成 (優先度: 中)
- [ ] 金融ニュース週次ダイジェスト自動生成 (優先度: 中)
- [ ] knowledge-graph/ 詳細エクスポート (優先度: 低)

## 次回の議論トピック

- `/sync-to-obsidian` コマンドの具体的な設計（何を同期するか、頻度、obsidian CLI活用）
- Obsidian Tasksプラグインとの連携可否
- デイリーノート連携の検討
