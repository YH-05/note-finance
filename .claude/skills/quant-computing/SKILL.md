---
name: quant-computing
description: クオンツ計算コード品質のナレッジベース。数値精度・ベクトル化・バックテスト・リスク指標の実装ルールを提供。pr-quant エージェントが参照する。
allowed-tools: Read
---

# Quant Computing

クオンツ計算コードの品質基準と実装パターンを提供するナレッジベーススキルです。

## 目的

このスキルは以下を提供します：

- **数値精度**: 浮動小数点比較・年率化計算の正しいパターン
- **ベクトル化**: pandas/NumPy の効率的な集計パターン
- **バックテスト**: ポイントインタイム（PoiT）遵守・前方参照防止
- **リスク指標**: ゼロ除算防御・スキーマ検証パターン

## リソース

| ファイル | 内容 |
|---------|------|
| `guide.md` | 各ルールの詳細実装パターンと違反例 |

## クイックリファレンス

### QC-01: 浮動小数点比較

```python
# 違反
if value == 0.0: ...
assert result == expected

# 正しい
_EPSILON = 1e-10
if abs(value) < _EPSILON: ...
assert result == pytest.approx(expected, rel=1e-6)
```

### QC-02: 年率化計算（複利必須）

```python
# 違反（単利）
annualized = daily_return * 252 / n

# 正しい（複利）
annualized = (1 + total_return) ** (252 / n) - 1
```

### QC-03: バックテスト前方参照防止

```python
# 違反（当日シグナルで当日エントリー）
portfolio = prices * signals

# 正しい（翌日エントリー、PoiT遵守）
portfolio = prices * signals.shift(1)
```

### QC-04: ベクトル化

```python
# 違反（Pythonループ）
result = []
for i in range(len(df)):
    result.append(df.iloc[i]['col'] * 2)

# 正しい（ベクトル演算）
result = df['col'] * 2
```

### QC-06: ゼロ除算防御

```python
# 違反
sharpe = excess_return / volatility

# 正しい
_EPSILON = 1e-10
sharpe = excess_return / max(volatility, _EPSILON)
```

## 重大度

| ルール | 重大度 | 減点 |
|-------|--------|------|
| QC-02 単利年率化 | CRITICAL | -20 |
| QC-03 前方参照 | CRITICAL | -20 |
| QC-01 浮動小数点 | HIGH | -10 |
| QC-06 ゼロ除算 | HIGH | -10 |
| QC-07 スキーマ検証なし | HIGH | -10 |
| QC-04 Pythonループ | MEDIUM | -5 |
| QC-05 Hypothesisテスト不足 | MEDIUM | -5 |
| QC-08 DB選択 | LOW | -2 |
