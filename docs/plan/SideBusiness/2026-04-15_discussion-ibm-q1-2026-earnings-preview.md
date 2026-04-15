# 議論メモ: IBM Q1 2026 決算プレビュー — article-full 全工程完了

**日付**: 2026-04-15  
**参加**: ユーザー + AI

## 背景・コンテキスト

株投資ラボの earnings カテゴリで、IBM Q1 2026 決算（2026-04-22 AMC）のプレビュー記事を `/article-full` コマンドで作成。今セッションでは BLK・NFLX・UNH に続く4本目の earnings 記事となった。

Neo4j 起動に際し、NeoData SSD（/Volumes/NeoData/）の物理接続が必要だった（未マウント時は docker start が失敗）。

## 議論のサマリー

### リサーチ段階の発見

- **IBM は AlphaVantage DB に未登録**: `av_earnings` / `av_company_overview` にデータなし。yfinance カスタムスクリプト（analyze_ibm_returns.py）+ Tavily 検索（Benzinga）+ SEC EDGAR 8-K の3点セットで補完
- **EPS ビート ≠ 翌日株価上昇**: 過去8四半期で顕著な乖離パターンを確認。Q1・Q2 2025 は EPS +14%/+6% のビートにもかかわらず翌日 -6.6%/-7.6% の下落
- **AI Book of Business $7.5B**: 今回の最重要 KPI。$8B 超え達成かどうかが市場反応の鍵
- **Consulting 懸念**: 成長鈍化への警戒が株価反応を左右するドライバー

### 表フォーマット

BLK 形式（table_overview + table_eps_surprise + table_stock_reaction の3分割）を踏襲。8列統合表を3列2表に分割するワークアラウンドを継続適用。

### 批評スコア: 79/100

| 項目 | スコア |
|------|--------|
| コンプライアンス | 83/100 |
| 事実正確性 | 91/100 |
| 構成 | 74/100 |
| 読みやすさ | 68/100 |

## 決定事項

1. **IBM は AV DB 未登録 → yfinance + Tavily 補完**: IBM 関連記事では AlphaVantage が使えないため、yfinance（株価・反応）+ Tavily/Benzinga（EPS 履歴）+ SEC EDGAR（8-K）の3点セットで代替する
2. **「押し目」等の特定売買表現は中立化必須**: §4 株価パフォーマンスで「押し目」→「この水準をどのように評価するかは、今回の決算内容と経営陣のガイダンスを踏まえてご自身でご判断ください。」に置換。全 earnings/stock_analysis カテゴリに適用
3. **Docker + NeoData SSD が Neo4j 起動の前提**: セッション開始時に SSD マウント確認を習慣化

## アクションアイテム

- [ ] IBM 記事を note.com で公開: カバー画像設定 + ハッシュタグ(#IBM #決算 #エンタープライズAI #WatsonX #クラウド) + 公開ボタン（優先度: 高）
- [ ] 2026-04-22 AMC 発表後に IBM Q1 2026 **決算レビュー**記事を作成（優先度: 高、due: 2026-04-22）

## 注目ポイント（2026-04-22 決算当日）

| KPI | 注目ライン |
|-----|-----------|
| AI Book of Business | $8B 超えか（前回 $7.5B） |
| Software セグメント成長率 | +10% 軌道に乗れているか |
| Consulting セグメント | バックログ前年比がマイナスか否か |
| Infrastructure | 「ひと桁台前半の減少」通りか否か |
| Q2 ガイダンス | $16.56B を上回るか否か |

## 参考情報

- note.com 下書き URL: https://editor.note.com/notes/nce8febe2eb50/edit/
- 記事フォルダ: `articles/earnings/2026-04-22_ibm-q1-2026-earnings-preview/`
- 批評: `02_draft/critic.json`（スコア 79/100）
- 最終稿: `03_published/article.md`
