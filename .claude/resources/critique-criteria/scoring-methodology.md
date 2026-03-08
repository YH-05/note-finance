# 統一スコアリング方式

## 概要

全批評エージェントで統一されたスコアリング方法論。
各エージェント固有のスコア計算式は維持しつつ、重要度定義とグレードバンドを統一。

## 重要度定義

| 重要度 | 定義 | スコア影響 | 対応 |
|--------|------|----------|------|
| critical | 公開不可レベルの問題 | -30点 | 必須修正 |
| high | 品質に重大な影響 | -15点 | 強く推奨 |
| medium | 品質改善に寄与 | -5点 | 推奨 |
| low | 微細な改善点 | -2点 | 任意 |

## グレードバンド

| グレード | スコア範囲 | 意味 |
|---------|-----------|------|
| A | 90-100 | 優秀。修正不要または軽微な改善のみ |
| B | 75-89 | 良好。いくつかの改善推奨 |
| C | 60-74 | 可。重要な改善が必要 |
| D | 40-59 | 不十分。大幅な修正が必要 |
| F | 0-39 | 不可。全面的な書き直しを推奨 |

## エージェント別スコア計算式

### compliance
score = 100 - (critical x 30 + high x 15 + medium x 5 + low x 2)
※ critical がある場合、score は最大でも 70

### fact
score = 100 - (high_issues x 10 + medium_issues x 5 + low_issues x 2)

### data_accuracy
score = (correct / total) x 100 - (high_issues x 5)

### structure
score = 合計(カテゴリスコア x 重み)
カテゴリ: introduction(20%), flow(25%), sections(25%), conclusion(15%), readability(15%)

### readability
score = 合計(カテゴリスコア x 重み)
カテゴリ: hook(25%), density(20%), visual(20%), terminology(20%), specificity(15%)

## 総合判定

全批評の加重平均:

| 批評タイプ | 総合スコアへの重み |
|-----------|-----------------|
| compliance | 30%（最重要: 法的リスク） |
| fact | 25% |
| data_accuracy | 20% |
| structure | 15% |
| readability | 10% |

公開可否判定:
- compliance が fail → 公開不可
- 総合スコア < 60 → 公開非推奨
- 総合スコア >= 75 → 公開推奨
