# Project 10: Claude Explorer Web App

## 概要

`.claude/` 配下の 195 コンポーネント（60 agents, 31 commands, 48 skills, 8 rules, 10 workflows, 38 mirror skills）をカードパネル型 UI + 依存グラフで一覧・探索できる TypeScript Web アプリ。

## GitHub Project

- **Project**: [Claude Explorer Web App (#81)](https://github.com/users/YH-05/projects/81)
- **リポジトリ**: YH-05/note-finance

## Tech Stack

| 技術 | 用途 |
|------|------|
| Vite + React 18 + TypeScript | アプリフレームワーク |
| @xyflow/react (React Flow v12) | 依存グラフ表示 |
| @dagrejs/dagre | 階層的自動レイアウト |
| Tailwind CSS v3 | スタイリング |
| gray-matter | YAML フロントマター解析（ビルド時のみ） |
| Fuse.js | ファジー検索 |
| react-markdown | Markdown レンダリング |

## 配置先

```
tools/claude-explorer/
```

## Issue 一覧

| Wave | Issue | タイトル | サイズ | 依存 |
|------|-------|---------|--------|------|
| 1 | [#117](https://github.com/YH-05/note-finance/issues/117) | プロジェクトスキャフォールド | M | - |
| 2 | [#118](https://github.com/YH-05/note-finance/issues/118) | 型定義 + データ抽出スクリプト | L | #117 |
| 3 | [#119](https://github.com/YH-05/note-finance/issues/119) | カードグリッドUI | L | #118 |
| 3 | [#120](https://github.com/YH-05/note-finance/issues/120) | DetailPanel | M | #119 |
| 4 | [#121](https://github.com/YH-05/note-finance/issues/121) | 依存グラフビュー | L | #120 |
| 4 | [#122](https://github.com/YH-05/note-finance/issues/122) | ファジー検索 + ディープリンク | M | #121 |

## クリティカルパス

```
#117 → #118 → #119 → #120 → #121 → #122
```

## 検証方法

| Step | 検証 |
|------|------|
| 1 | `npm install && npm run dev` でブラウザ表示 |
| 2 | `npm run extract` で graph-data.json 生成（195 コンポーネント） |
| 3 | 全カード表示 + フィルター動作 |
| 4 | カードクリックで DetailPanel 表示 |
| 5 | グラフビューでノード・エッジ表示 |
| 6 | 検索・ディープリンク・ビルド成功 |

## 関連ドキュメント

- [設計プラン](./original-plan.md)
