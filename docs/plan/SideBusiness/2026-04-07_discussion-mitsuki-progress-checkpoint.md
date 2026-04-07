# 議論メモ: みつきD型プロダクト 進捗確認チェックポイント

**日付**: 2026-04-07
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-04-07-mitsuki-progress-checkpoint

## 背景・コンテキスト

2026-04-07セッションでの一連の議論（D型プロダクト設計・占術戦略・B+C+D融合モデル等）の
進捗を確認するチェックポイント。本セッションでは新規の決定事項なし。

## 現在地（2026-04-07時点）

### 確定済み事項

| 領域 | 決定内容 |
|------|---------|
| モデル | B+C+D融合（D型=収益の核心） |
| D型商品 | AI生成パーソナル分析PDF、¥1,500/テーマ、4テーマ（恋愛/仕事/人間関係/ストレス） |
| D型構造 | 7セクション統一フレーム確定 |
| 占術エンジン | 数秘術(LP/Destiny/Soul) + 惑星星座(Sun/Venus/Mars/Mercury/Jupiter/Saturn) + MBTI(任意) |
| ブランドメッセージ | 「生年月日で、自分のパターンを読み解く」 |
| 占術名の扱い | D型表面には出さない。タロット/星座はThreads集客フック専用 |
| 四柱推命 | 見送り確定 |
| 価格ラダー | フロント¥1,500 / バックエンド¥5,000 |

### 未着手のActionItem（高優先度）

| ID | 内容 | 状態 |
|----|------|------|
| act-2026-04-07-001 | D型プロダクト設計（7セクションテンプレート・AI生成ロジック） | in_progress |
| act-2026-04-07-002 | 悩みフック型投稿のOK/NGガイドライン策定 | pending |
| act-2026-04-07-006 | 惑星星座計算エンジン実装（Python/swisseph） | pending |
| act-2026-04-07-007 | D型統合テンプレート設計「○○タイプ」命名体系 | pending |

### 未着手のActionItem（中優先度）

| ID | 内容 | 状態 |
|----|------|------|
| act-2026-04-07-003 | 悩みフック型投稿のA/Bテスト実験設計 | pending |
| act-2026-04-07-004 | ococonala商品ページドラフト（恋愛¥1,500サンプル） | pending |
| act-2026-04-07-005 | みつきオリジナルタロットカード画像生成（大アルカナ22枚） | pending |
| act-2026-04-07-008 | エニアグラム採用可否の検討 | pending |
| act-2026-04-07-009 | persona.md / posting_algorithm.md にブランド統合方針を反映 | pending |

## 次回の議論トピック（3軸）

### 軸1: 収益化
- 「○○タイプ」命名体系: 統一タイプ vs テーマ別タイプ、タイプ数（8〜30種）、命名の雰囲気（感情的/心理学的/詩的）
- アップセル設計（¥1,500×4 → ¥5,000総合版）の具体的UXフロー

### 軸2: 占術
- エニアグラム採用/見送りの最終判断（入力方式・ブランド適合性・追加価値）
- 惑星星座4テーマ対応（恋愛=Venus、仕事=Mars、人間関係=Mercury、ストレス=Saturn）の確認

### 軸3: ブランディング
- ococonara商品ページのタイトル・説明文（占術名を出さない表現）
- Threads集客フック → note → ococonara のファネル一貫メッセージ

## 参考情報

- D型プロダクト設計: `docs/plan/SideBusiness/2026-04-07_discussion-d-product-design.md`
- 占術戦略: `docs/plan/SideBusiness/2026-04-07_discussion-mitsuki-divination-strategy.md`
- B+C+D融合モデル: `docs/plan/SideBusiness/2026-04-07_discussion-mitsuki-acquisition-strategy.md`
- note収益化戦略: `docs/plan/SideBusiness/2026-04-07_discussion-note-content-redesign.md`
