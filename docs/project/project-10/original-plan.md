# Claude Explorer - `.claude/` ビジュアライザー Web アプリ設計

## Context

`.claude/` 配下に 60 エージェント・31 コマンド・48 スキル・10 ワークフロー・9 ルール（計 158 コンポーネント）が存在し、全体像と相互依存の把握が困難になっている。カードパネル型 UI + 依存グラフで一覧・探索できる TypeScript Web アプリを新規作成する。

## Tech Stack

| 技術 | 選定理由 |
|------|----------|
| **Vite + React 18 + TypeScript** | 軽量・高速 HMR。Next.js は SSR/ルーティングが不要で過剰 |
| **@xyflow/react (React Flow v12)** | React ネイティブのノードグラフ。d3 より宣言的、cytoscape より軽量 |
| **dagre** | 階層的自動レイアウト（依存グラフの整列） |
| **Tailwind CSS v3** | ユーティリティ CSS。カード・レイアウトを高速実装 |
| **gray-matter** | YAML フロントマター解析（ビルド時スクリプトのみ） |
| **Fuse.js** | クライアント側ファジー検索 |
| **react-markdown** | 詳細パネルの Markdown レンダリング |

## プロジェクト配置

```
tools/claude-explorer/
```

既存 Python コードベースから独立。`Makefile` にショートカットを追加。

## ディレクトリ構造

```
tools/claude-explorer/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── index.html
│
├── scripts/
│   ├── extract-data.ts       # .claude/ → JSON 変換スクリプト
│   └── types.ts              # 抽出・アプリ共有の型定義
│
└── src/
    ├── main.tsx
    ├── App.tsx                # タブ切替（カードグリッド / グラフ）
    │
    ├── types/
    │   └── index.ts
    │
    ├── data/
    │   └── graph-data.json   # extract-data.ts の出力（gitignore）
    │
    ├── components/
    │   ├── layout/
    │   │   ├── Header.tsx     # 検索バー・統計・ビュー切替
    │   │   └── Sidebar.tsx    # フィルター（型・カテゴリ）
    │   │
    │   ├── cards/
    │   │   ├── ComponentCard.tsx  # 汎用カード
    │   │   ├── AgentCard.tsx      # model/color/skills バッジ
    │   │   ├── CommandCard.tsx    # argument-hint 表示
    │   │   ├── SkillCard.tsx      # allowed-tools/サブファイル
    │   │   └── WorkflowCard.tsx   # ワークフロー用
    │   │
    │   ├── grid/
    │   │   ├── CardGrid.tsx       # レスポンシブグリッド
    │   │   └── FilterBar.tsx      # 型トグル + カテゴリタグ
    │   │
    │   ├── graph/
    │   │   ├── DependencyGraph.tsx # React Flow ラッパー
    │   │   ├── CustomNode.tsx      # 型別ノード描画
    │   │   └── GraphControls.tsx   # レイアウト切替・ズーム
    │   │
    │   └── detail/
    │       ├── DetailPanel.tsx     # スライドイン詳細パネル
    │       ├── DependencyList.tsx  # 入出力依存リスト
    │       └── MarkdownPreview.tsx # MD レンダリング
    │
    ├── hooks/
    │   ├── useGraphData.ts    # JSON ロード + メモ化
    │   ├── useSearch.ts       # Fuse.js 検索
    │   └── useFilter.ts      # フィルター状態管理
    │
    └── lib/
        ├── graph-layout.ts    # dagre レイアウト計算
        ├── colors.ts          # 型別カラーパレット
        └── search.ts          # Fuse.js インデックス構築
```

## データモデル

```typescript
type ComponentType = 'agent' | 'command' | 'skill' | 'rule' | 'workflow';

interface BaseComponent {
  id: string;              // "agent:code-simplifier"
  type: ComponentType;
  name: string;
  slug: string;            // ファイル名 (拡張子なし)
  description: string;
  filePath: string;        // プロジェクトルートからの相対パス
  source: '.claude' | '.agents';
  content: string;         // Markdown 本文
}

interface AgentComponent extends BaseComponent {
  type: 'agent';
  model: string;           // "inherit" | "sonnet" | etc.
  color: string;           // "blue" | "green" | "purple" | etc.
  skills: string[];        // frontmatter skills 配列
  tools: string[];         // frontmatter tools 配列
  category: string;        // 名前プレフィックスから推定
}

interface CommandComponent extends BaseComponent {
  type: 'command';
  argumentHint?: string;
}

interface SkillComponent extends BaseComponent {
  type: 'skill';
  allowedTools: string[];
  skills: string[];
  subFiles: string[];      // guide.md, templates/, examples/ 等
}

interface DependencyEdge {
  source: string;          // コンポーネント ID
  target: string;
  type: 'skills' | 'subagent_type' | 'path_ref' | 'inline_ref';
}

interface GraphData {
  components: BaseComponent[];
  edges: DependencyEdge[];
  stats: Record<ComponentType, number>;
  generatedAt: string;
}
```

## データ抽出スクリプト (`scripts/extract-data.ts`)

`npx tsx scripts/extract-data.ts` で実行。`src/data/graph-data.json` を出力。

### Phase 1: ファイル収集 + フロントマター解析

| ソース | glob パターン | パーサー |
|--------|--------------|----------|
| エージェント | `.claude/agents/*.md` | gray-matter → AgentComponent |
| コマンド | `.claude/commands/*.md` (`_shared/` 除外) | gray-matter → CommandComponent |
| スキル | `.claude/skills/*/SKILL.md` | gray-matter → SkillComponent |
| ルール | `.claude/rules/*.md` (`README.md` 除外) | gray-matter → RuleComponent |
| ワークフロー | `.agents/workflows/*.md` | gray-matter → WorkflowComponent |
| ミラースキル | `.agents/skills/*/SKILL.md` | 同上 (source='.agents') |

### Phase 2: 依存エッジ抽出（6 つの正規表現戦略）

| 戦略 | 正規表現 | エッジ type |
|------|----------|-----------|
| 1. frontmatter `skills:` | (解析済み配列) | `skills` |
| 2. `subagent_type=` | `/subagent_type\s*=\s*["']([^"']+)["']/g` | `subagent_type` |
| 3. パス参照 | `/\.claude\/(skills|agents|commands|rules)\/([^\/\s)]+)/g` | `path_ref` |
| 4. `.agents/` パス | `/\.agents\/(skills|workflows)\/([^\/\s)]+)/g` | `path_ref` |
| 5. エージェント名参照 | `/([a-z][-a-z0-9]+)\s+エージェント/g` | `inline_ref` |
| 6. スキル名参照 | `/([a-z][-a-z0-9]+)\s+スキル/g` | `inline_ref` |

### Phase 3: バリデーション

- エッジの target が既知コンポーネントに存在するか検証
- 存在しない target は `broken: true` フラグ付与（UI で警告表示）
- 重複エッジの除去

### Phase 4: エージェントカテゴリ推定

名前プレフィックスからカテゴリを自動推定:

| プレフィックス | カテゴリ |
|---------------|---------|
| `pr-` | PR Review |
| `wr-` | Weekly Report |
| `finance-` | Finance |
| `test-` | Testing |
| `exp-` / `experience-` | Experience DB |
| `csa-` | Case Study |
| `weekly-comment-` | Weekly Comment |
| その他 | General |

## UI 設計

### カードグリッドビュー（デフォルト）

```
┌─────────────────────────────────────────────────┐
│  [検索バー]  │ Agents:60 Commands:31 Skills:48  │  [Grid|Graph]
├─────────┬───────────────────────────────────────┤
│ Filters │  ┌────────┐ ┌────────┐ ┌────────┐    │
│         │  │Agent   │ │Agent   │ │Command │    │
│ □Agent  │  │name    │ │name    │ │name    │    │
│ □Command│  │desc... │ │desc... │ │desc... │    │
│ □Skill  │  │🔗3 deps│ │🔗5 deps│ │🔗2 deps│    │
│ □Rule   │  └────────┘ └────────┘ └────────┘    │
│ □Workflow│  ┌────────┐ ┌────────┐ ┌────────┐    │
│         │  │Skill   │ │Skill   │ │Rule    │    │
│ Category│  │name    │ │name    │ │name    │    │
│ ─────── │  │tools.. │ │tools.. │ │desc... │    │
│ □Finance│  │🔗1 dep │ │🔗0 deps│ │        │    │
│ □PR Rev │  └────────┘ └────────┘ └────────┘    │
│ □Test   │                                       │
│ ...     │                                       │
└─────────┴───────────────────────────────────────┘
```

- 各カードは型別の色帯（上部ボーダー）で視覚区別
- 依存数バッジをクリックで依存先をハイライト
- カードクリックで右から DetailPanel がスライドイン

### 依存グラフビュー

```
┌─────────────────────────────────────────────────┐
│  [検索]  │ Stats │  [Grid|Graph]                │
├─────────┬───────────────────────────────────────┤
│ Filters │  React Flow キャンバス                 │
│         │                                       │
│ □Agent  │  [Agent] ──→ [Skill]                  │
│ □Command│       └──→ [Skill]                    │
│ □Skill  │  [Command] ──→ [Agent]                │
│         │  [Skill] ──→ [Skill]                  │
│ Edge    │                                       │
│ ─────── │  ┌─────────┐                          │
│ □skills │  │ Minimap │                          │
│ □subagt │  └─────────┘                          │
│ □path   │                                       │
│ □inline │                                       │
└─────────┴───────────────────────────────────────┘
```

- ノードは型別に色分け: Agent=blue, Command=green, Skill=purple, Rule=gray, Workflow=orange
- エッジスタイル: skills=実線, subagent_type=破線, path_ref=点線, inline_ref=薄い点線
- dagre で階層レイアウト（左→右）
- ノードクリックで DetailPanel 表示 + 接続ノードをハイライト

### DetailPanel

```
┌─────────────────┐
│ ← [Agent] badge │
│ code-simplifier │
│ ────────────── │
│ desc: コードの  │
│ 複雑性を削減... │
│                 │
│ model: inherit  │
│ color: green    │
│                 │
│ ■ Depends On    │
│  → error-handling│
│  → coding-stds  │
│                 │
│ ■ Used By       │
│  ← commit-and-pr│
│                 │
│ ■ Content       │
│ [Markdown...]   │
│                 │
│ 📋 .claude/agents│
│ /code-simplif...│
└─────────────────┘
```

## 色分けパレット

| 型 | メインカラー | Tailwind クラス |
|----|-------------|----------------|
| Agent | Blue | `bg-blue-50 border-blue-500` |
| Command | Green | `bg-green-50 border-green-500` |
| Skill | Purple | `bg-purple-50 border-purple-500` |
| Rule | Gray | `bg-gray-50 border-gray-500` |
| Workflow | Orange | `bg-orange-50 border-orange-500` |

## 実装ステップ

### Step 1: プロジェクトスキャフォールド

- `tools/claude-explorer/` に Vite + React + TS プロジェクト作成
- 依存パッケージインストール
- Tailwind CSS 設定
- `.gitignore` に `node_modules/`, `dist/`, `src/data/graph-data.json` 追加

**修正ファイル:**
- `tools/claude-explorer/package.json` (新規)
- `tools/claude-explorer/tsconfig.json` (新規)
- `tools/claude-explorer/vite.config.ts` (新規)
- `tools/claude-explorer/tailwind.config.ts` (新規)
- `tools/claude-explorer/index.html` (新規)

### Step 2: 型定義 + データ抽出スクリプト

- `scripts/types.ts` - 共有型定義
- `scripts/extract-data.ts` - フルパイプライン実装
  - glob でファイル収集
  - gray-matter でフロントマター解析
  - 6 つの正規表現で依存エッジ抽出
  - バリデーション + 重複除去
  - `src/data/graph-data.json` 出力

**修正ファイル:**
- `tools/claude-explorer/scripts/types.ts` (新規)
- `tools/claude-explorer/scripts/extract-data.ts` (新規)

### Step 3: カードグリッド UI

- `App.tsx` - 2カラムレイアウト + ビュー切替
- `Header.tsx` - 検索 + 統計
- `FilterBar.tsx` - 型トグル + カテゴリフィルター
- `ComponentCard.tsx` + 型別カードバリアント
- `CardGrid.tsx` - レスポンシブグリッド

**修正ファイル:**
- `tools/claude-explorer/src/App.tsx` (新規)
- `tools/claude-explorer/src/components/layout/Header.tsx` (新規)
- `tools/claude-explorer/src/components/grid/CardGrid.tsx` (新規)
- `tools/claude-explorer/src/components/grid/FilterBar.tsx` (新規)
- `tools/claude-explorer/src/components/cards/ComponentCard.tsx` (新規)
- `tools/claude-explorer/src/components/cards/AgentCard.tsx` (新規)
- `tools/claude-explorer/src/components/cards/CommandCard.tsx` (新規)
- `tools/claude-explorer/src/components/cards/SkillCard.tsx` (新規)

### Step 4: DetailPanel

- スライドイン詳細パネル
- 依存の入出力リスト
- Markdown レンダリング

**修正ファイル:**
- `tools/claude-explorer/src/components/detail/DetailPanel.tsx` (新規)
- `tools/claude-explorer/src/components/detail/DependencyList.tsx` (新規)
- `tools/claude-explorer/src/components/detail/MarkdownPreview.tsx` (新規)

### Step 5: 依存グラフビュー

- React Flow キャンバス
- dagre 自動レイアウト
- カスタムノード（型別色分け）
- エッジスタイル（依存種別ごと）
- ミニマップ

**修正ファイル:**
- `tools/claude-explorer/src/components/graph/DependencyGraph.tsx` (新規)
- `tools/claude-explorer/src/components/graph/CustomNode.tsx` (新規)
- `tools/claude-explorer/src/components/graph/GraphControls.tsx` (新規)
- `tools/claude-explorer/src/lib/graph-layout.ts` (新規)

### Step 6: 検索 + 仕上げ

- Fuse.js ファジー検索
- hooks 実装
- URL ハッシュによるディープリンク

**修正ファイル:**
- `tools/claude-explorer/src/hooks/useGraphData.ts` (新規)
- `tools/claude-explorer/src/hooks/useSearch.ts` (新規)
- `tools/claude-explorer/src/hooks/useFilter.ts` (新規)
- `tools/claude-explorer/src/lib/search.ts` (新規)
- `tools/claude-explorer/src/lib/colors.ts` (新規)

## ビルド・開発ワークフロー

```json
{
  "scripts": {
    "extract": "tsx scripts/extract-data.ts",
    "dev": "npm run extract && vite",
    "build": "npm run extract && vite build",
    "preview": "vite preview"
  }
}
```

```bash
# 開発
cd tools/claude-explorer && npm install && npm run dev

# ビルド（静的ファイル出力）
npm run build    # → dist/ に出力
```

Makefile 統合（任意）:
```makefile
explorer:
	cd tools/claude-explorer && npm run dev
explorer-build:
	cd tools/claude-explorer && npm run build
```

## 検証方法

1. **抽出スクリプト**: `npm run extract` → `graph-data.json` の stats が期待値（agents:60, commands:31, skills:48 前後）と一致
2. **カードグリッド**: `npm run dev` → 全コンポーネントがカード表示される、型フィルター・検索が動作
3. **依存グラフ**: グラフビューでノード・エッジが表示、クリックで DetailPanel 連動
4. **DetailPanel**: カードクリックで正しいメタデータ・依存リスト・Markdown が表示
5. **ビルド**: `npm run build` → `dist/` の静的ファイルが `npx serve dist` で正常動作

## 既知の課題と対策

| 課題 | 対策 |
|------|------|
| インライン参照の誤検出 | 抽出した名前を既知コンポーネント一覧と照合し、存在するものだけエッジ化 |
| 158 ノードのグラフが密集 | デフォルトは孤立ノード非表示 + 型/カテゴリフィルターで絞り込み |
| `.agents/` と `.claude/` の重複 | source フィールドで区別、UI にバッジ表示 |
| `agents.md` のバーチャルエージェント | ファイルなしのエージェントは `virtual: true` として別扱い |
