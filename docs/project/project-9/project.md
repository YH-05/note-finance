# Project 9: DATA_ROOT パス一元管理

| 項目 | 値 |
|------|-----|
| GitHub Project | [#77](https://github.com/users/YH-05/projects/77) |
| ステータス | Planning → In Progress |
| 作成日 | 2026-03-13 |

## 概要

`DATA_ROOT` 環境変数によるデータパス一元管理。`data_paths` パッケージを新規作成し、プロジェクト全体のハードコードされた `Path("data/...")` を `get_path()` に置き換える。

## 設計判断

- **フォールバック戦略A**: `DATA_ROOT` 設定時にパスが存在しなければ `DataPathError`（フォールバックなし、意図的な設計）
- **config/ ルーティング**: `config/` サブパスは `DATA_ROOT` 設定に関わらず常にプロジェクトローカル
- **既存環境変数**: `RSS_DATA_DIR` > `DATA_ROOT` > `{project}/data` の優先順位維持
- **Pydantic パターン**: `default=Path(...)` → `default_factory=lambda: get_path(...)`

## Wave 構成

### Wave 1（前提）
| Issue | タイトル |
|-------|---------|
| [#78](https://github.com/YH-05/note-finance/issues/78) | feat(data-paths): data_paths パッケージ新規作成 |

### Wave 2（並列実行可能）
| Issue | タイトル |
|-------|---------|
| [#79](https://github.com/YH-05/note-finance/issues/79) | feat(rss): data_paths への移行 |
| [#80](https://github.com/YH-05/note-finance/issues/80) | feat(pdf-pipeline): data_paths への移行 |
| [#81](https://github.com/YH-05/note-finance/issues/81) | feat(report-scraper): data_paths への移行 |
| [#82](https://github.com/YH-05/note-finance/issues/82) | feat(news): data_paths への移行 |
| [#83](https://github.com/YH-05/note-finance/issues/83) | feat(scripts): 一般スクリプトの移行 |
| [#84](https://github.com/YH-05/note-finance/issues/84) | fix(scripts): 旧リポジトリ絶対パス修正 |

## 関連ドキュメント

- [オリジナルプラン](./original-plan.md)
- [セッションデータ](../../.tmp/plan-project-data-root-1773355301/)
