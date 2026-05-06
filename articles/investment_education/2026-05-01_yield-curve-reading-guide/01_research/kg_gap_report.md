# KGギャップ分析レポート
生成日: 2026-05-01

## 既存データサマリー

research-neo4j（イールドカーブ関連Topicタグ検索結果）

| 項目 | 件数 |
|------|------|
| 関連トピック（「イールドカーブ」） | 1件 |
| タグ付きソース | 10件（official: 4, analyst: 6） |
| タグ付きFact | 10件 |

### 既存ソース一覧
- FRED T10Y2Y（公式）
- Federal Reserve H.15（公式）
- NY Fed Yield Curve Leading Indicator（公式）
- Treasury Market Liquidity（NY Fed）
- Yield Curve Inversion History 1976-2026
- COT Bonds Data（InvestMacro 2件）
- T. Rowe Price Treasury Analysis
- Charles Schwab 2026 Outlook
- Why Trump paused tariffs（関税/国債市場）

## 特定ギャップ

| ギャップ種別 | 内容 | 優先度 |
|------------|------|--------|
| no_coverage | タームプレミアム（ACMモデル）の教育的解説データが不足 | HIGH |
| no_coverage | BEI（期待インフレ率）の計算方法・見方の解説データが不足 | HIGH |
| no_coverage | フィッシャー方程式・長期金利の3分解（期待短期金利＋期待インフレ＋TP）の説明が不足 | HIGH |
| missing_bull_case | 現在のベア・スティープ局面のみ。教育的な「各形状が示す意味」の体系解説が不足 | MEDIUM |

## ギャップ解消済み（本リサーチで収集）

- ✅ BEI計算方法（Wikipedia・IIMA・stock-marketdata.com）
- ✅ 実質金利フィッシャー方程式（複数ソース）
- ✅ イールドカーブ形状・ベア/ブルスティープ・フラット解説（Siiibo・OANDA）
- ✅ 逆イールドと景気後退の歴史（NY Fed・eco3min）
- ✅ T10Y2Y直近データ（Bloomberg・FRED）
- ✅ タームプレミアムの定義（Bloomberg 2024年10月記事）
