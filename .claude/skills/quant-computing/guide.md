# Quant Computing 詳細ガイド

## QC-01: 浮動小数点の == 比較禁止

### 問題

浮動小数点の等値比較は丸め誤差により予期しない結果をもたらす。

```python
# 問題のあるパターン
if value == 0.0:          # 浮動小数点の == 比較
    pass
assert result == expected  # テストでの == 比較
```

### 修正

```python
_EPSILON = 1e-10

# None/NaN チェックと組み合わせる
if abs(value) < _EPSILON:
    pass

# テストでは pytest.approx を使用
assert result == pytest.approx(expected, rel=1e-6)
assert result == pytest.approx(expected, abs=1e-8)
```

## QC-02: 単利年率化禁止（複利必須）

### 問題

単利年率化は長期リターンを誤って表現する。

```python
# 違反パターン
annualized = daily_return * 252 / n
annualized = monthly_return * 12
annualized = weekly_return * 52
```

### 修正

```python
# 日次リターンの年率化
annualized = (1 + total_return) ** (252 / n) - 1

# 月次リターンの年率化
annualized = (1 + monthly_return) ** 12 - 1

# 対数リターンの場合
annualized = np.exp(log_return * 252 / n) - 1
```

## QC-03: バックテストの前方参照（PoiT違反）

### 問題

シグナル計算日のデータでエントリーすると、実際には取引できない情報を使用している。

```python
# 違反: 当日シグナルで当日エントリー
signals = compute_signal(prices)
portfolio = prices * signals

# 違反: 当日の終値でシグナルを計算して当日エントリー
signal_today = prices['close'].rolling(20).mean()
position = signal_today > prices['close']
```

### 修正

```python
# 正しい: 翌日エントリー（PoiT遵守）
signals = compute_signal(prices)
portfolio = prices * signals.shift(1)

# 正しい: 前日シグナルで今日エントリー
signal_prev = prices['close'].rolling(20).mean().shift(1)
position = signal_prev > prices['close']
```

## QC-04: pandas/NumPy 集計での Python ループ禁止

### 問題

Python ループは C 実装のベクトル演算より桁違いに遅い。

```python
# 違反: O(n) の Python ループ
result = []
for i in range(len(df)):
    result.append(df.iloc[i]['price'] * df.iloc[i]['quantity'])

# 違反: apply() の乱用
df['total'] = df.apply(lambda row: row['price'] * row['quantity'], axis=1)
```

### 修正

```python
# 正しい: ベクトル演算
df['total'] = df['price'] * df['quantity']

# 条件付き集計
df['signal'] = np.where(df['return'] > 0, 1, -1)

# 複雑な集計
result = df.groupby('date')['return'].agg(['mean', 'std', 'count'])
```

## QC-05: 数値計算関数の Hypothesis テスト

### 必要なテストパターン

数値計算関数には以下の Hypothesis テストが必要:

```python
from hypothesis import given, assume
from hypothesis import strategies as st

@given(
    returns=st.lists(st.floats(min_value=-0.5, max_value=0.5), min_size=1),
)
def test_sharpe_ratio_properties(returns):
    """シャープレシオの不変条件テスト"""
    assume(not any(np.isnan(r) or np.isinf(r) for r in returns))
    result = compute_sharpe(returns)
    # 不変条件: スケール不変性
    scaled_result = compute_sharpe([r * 2 for r in returns])
    assert abs(result - scaled_result) < 1e-6
```

### テストすべき境界値

- 空リスト・単一要素
- ゼロリターン（ボラティリティ = 0）
- 全て正/全て負のリターン
- NaN・Inf を含む入力

## QC-06: リスク指標のゼロ除算防御

```python
_EPSILON = 1e-10

# シャープレシオ
sharpe = excess_return / max(volatility, _EPSILON)

# 情報比率
ir = alpha / max(tracking_error, _EPSILON)

# 最大ドローダウン比率
calmar = cagr / max(max_drawdown, _EPSILON)
```

## QC-07: スキーマ検証なしのデータ永続化

```python
import pandera as pa
from pandera import Column, DataFrameSchema

# スキーマ定義
schema = DataFrameSchema({
    "date": Column(pa.DateTime),
    "close": Column(float, pa.Check.ge(0)),
    "volume": Column(int, pa.Check.ge(0)),
})

# 保存前に検証
schema.validate(df)
df.to_parquet("data.parquet")
```

## QC-08: データ量・パターンに基づく DB 選択

| データ特性 | 推奨 DB | 理由 |
|-----------|--------|------|
| 行単位 CRUD、トランザクション | SQLite | ACID保証 |
| 列指向分析、大量データ集計 | DuckDB / Parquet | 列指向I/O |
| 時系列 OHLCV | Parquet + DuckDB | 圧縮効率・クエリ性能 |
| グラフ構造データ | Neo4j | 関係性クエリ |
