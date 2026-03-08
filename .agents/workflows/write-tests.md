---
description: t-wada流TDDによるテスト作成。Red→Green→Refactorサイクルに基づく高品質なテストを作成します。
---

# TDDによるテスト作成ワークフロー

t-wada流TDDサイクル（Red→Green→Refactor）に基づく高品質なテストの作成ワークフローです。

## パラメータ（ユーザーに確認）

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| target | ○ | - | テスト対象（モジュール名、ファイルパス、機能説明） |
| test_types | - | all | テスト種類（unit / property / integration / all） |

## TDDの基本サイクル

1. **Red**: 失敗するテストを書く
2. **Green**: テストを通す最小限の実装
3. **Refactor**: リファクタリング

## 処理フロー

```
Phase 1: テスト設計
├── 対象コードの分析
├── テストTODOリスト作成
│   ├── 正常系: 基本的な機能の動作確認
│   ├── 異常系: エラーハンドリング
│   ├── エッジケース: 境界値、空入力
│   ├── プロパティ: 不変条件の検証
│   └── 統合: コンポーネント連携
└── テスト優先度の決定

Phase 2: テスト作成（並列可能）
├── 単体テスト
│   ├── 関数・クラスの基本動作
│   ├── 正常系・異常系・エッジケース
│   └── パラメトライズテストの活用
├── プロパティテスト
│   ├── Hypothesisによる自動テストケース生成
│   ├── 不変条件の検証
│   └── エッジケースの自動発見
└── 統合テスト
    ├── コンポーネント間の連携
    ├── ファイルI/Oやデータ処理パイプライン
    └── エラーのカスケード処理

Phase 3: 検証
├── make test 実行
└── カバレッジ確認
```

## テストファイルの配置

```
tests/{library}/
├── unit/                      # 単体テスト
│   └── test_{module}.py
├── property/                  # プロパティベーステスト
│   └── test_{module}_property.py
├── integration/               # 統合テスト
│   └── test_{module}_integration.py
└── conftest.py               # 共通フィクスチャ
```

## テストの命名規則

日本語で意図を明確に表現:

```python
def test_正常系_有効なデータで処理成功():
    """chunk_listが正しくチャンク化できることを確認。"""

def test_異常系_不正なサイズでValueError():
    """チャンクサイズが0以下の場合、ValueErrorが発生することを確認。"""

def test_エッジケース_空リストで空結果():
    """空のリストをチャンク化すると空の結果が返されることを確認。"""

# プロパティテスト
@given(st.lists(st.integers()))
def test_prop_不変条件_要素数の保存(items: list[int]):
    """処理後も要素の総数が変わらないことを確認。"""
```

## 三角測量の実践例

```python
# Step 1: 最初のテスト（仮実装で通す）
def test_add_正の数():
    assert add(2, 3) == 5

def add(a, b):
    return 5  # 仮実装

# Step 2: 2つ目のテスト（一般化を促す）
def test_add_別の正の数():
    assert add(10, 20) == 30  # これで仮実装では通らない

def add(a, b):
    return a + b  # 一般化

# Step 3: エッジケースを追加
def test_add_負の数():
    assert add(-1, -2) == -3
```

## TDD実践の注意点

### DO（推奨）

- 1テストで1つの振る舞いをテスト
- Red → Green でコミット
- 日本語テスト名で意図を明確に
- 不安な部分から着手
- テストリストを常に更新

### DON'T（非推奨）

- 一度に複数のテストを書く
- テストなしで実装を進める
- 複雑なテストを最初から書く
- テストの失敗を無視して進む

## 実行コマンド

```bash
make test              # 全テスト実行
make test-unit         # 単体テストのみ
make test-property     # プロパティベーステストのみ
make test-cov          # カバレッジ付きテスト

# 特定のテストを実行
uv run pytest tests/unit/test_example.py -v
uv run pytest tests/unit/test_example.py::TestClass::test_method -v
```

## 関連リソース

| リソース | パス |
|---------|------|
| TDDスキル | `.agents/skills/tdd-development/SKILL.md` |
| テンプレート（単体） | `template/tests/unit/test_example.py` |
| テンプレート（プロパティ） | `template/tests/property/test_helpers_property.py` |
| テンプレート（統合） | `template/tests/integration/test_example.py` |
| テンプレート（フィクスチャ） | `template/tests/conftest.py` |
