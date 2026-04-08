# 議論メモ: 米国マクロ経済 weekly シリーズ — 3コレクター実装

**日付**: 2026-04-08
**参加**: ユーザー + AI

## 背景・コンテキスト

本日確定した設計書 `docs/plan/2026-04-08_us-macro-weekly-article-design.md` に基づき、
週次記事の記事生成パイプラインに必要な3つのデータコレクターを実装した。

インフラ整備タスク5件のうち、今日は #3〜#5 の実装を実施。

## 議論のサマリー

### インフラ進捗（実装タスク）全5件

| # | タスク | リポジトリ | 状況 |
|---|---|---|---|
| 1 | `fred_series.json` に9系列追加 | quants | ❌ 未対応 |
| 2 | `rss-presets.json` に speeches.xml 追加 | note-finance | ⚠️ 部分済（press_all.xml のみ） |
| 3 | CFTC COTコレクター | note-finance | ✅ 完了 |
| 4 | Fed Funds先物コレクター | note-finance | ✅ 完了 |
| 5 | FRED releases/datesコレクター | note-finance | ✅ 完了 |

### 実装: scripts/collect_us_macro_data.py

3コレクターを1スクリプトに統合。実行コマンド：

```bash
uv run python scripts/collect_us_macro_data.py \
  --output articles/macro_economy/{slug}/data
```

### 技術的決定事項

**COT（CFTC）**:
- Socrata API (`data.cftc.gov`) は DNS 解決失敗 → CFTC 公式 ZIP 直接ダウンロード方式に変更
- URL: `https://www.cftc.gov/sites/default/files/files/dea/history/fut_fin_txt_{year}.zip`
- 市場名: `FED FUNDS`（`FEDERAL FUNDS` ではなく）
- 2026-03-31 分まで13件取得確認

**Fed Funds 先物**:
- Yahoo Finance は月別シンボル（ZQK26=F等）を提供しない
- `ZQ=F`（最前月）のみ取得: price=96.355 → implied FF rate = 3.645%
- 複数限月パスは CME DataMine（有償）が必要 → 今後の課題

**FRED カレンダー**:
- `/fred/releases/dates` は将来の発表予定日を事前登録しない（過去データのみ）
- 主要リリース11件のIDを固定: `/fred/release/dates?release_id=XX` で個別取得
- 過去の発表パターンから「today以降の最初の発表日」を推定
- 翌2週間で7件 in-window（CPI, PCE, PPI, Industal Production, Claims, Housing, ミシガン大）

### 動作確認済み出力

```
2026-04-09  Initial Claims（週次）
2026-04-10  CPI
2026-04-12  PCE
2026-04-15  Industrial Production
2026-04-17  PPI
2026-04-18  New Residential Construction
2026-04-21  ミシガン大消費者信頼感
```

## 決定事項

1. CFTC COT は Socrata API を使わず公式 ZIP/TXT 直接ダウンロード方式を採用
2. Fed Funds 先物は `ZQ=F`（最前月のみ）に限定する（Yahoo Finance の仕様上の制約）
3. FRED カレンダーは ID固定方式（11リリース）+ 過去パターン推定を採用
4. `scripts/collect_us_macro_data.py` が3コレクターの実装として確定

## アクションアイテム

- [ ] `fred_series.json` に9系列追加（quants側）（優先度: 高）
- [ ] `rss-presets.json` に `speeches.xml` 追加（note-finance側）（優先度: 中）
- [ ] vol.1 記事フォルダ作成（`2026-04-13_us-macro-weekly-vol01`）+ 初稿着手（優先度: 高）

## 次回の議論トピック

- vol.1 の執筆フロー（article-draft スキルとの統合）
- FRED historical data（NAS キャッシュ）の読み込み実装
- チャート生成（yield curve, main theme 5年チャート）の実装

## 参考情報

- CFTC TFF COT エンドポイント確認: `https://www.cftc.gov/sites/default/files/files/dea/history/fut_fin_txt_2026.zip` (200 OK)
- FRED `/release/dates` は過去データのみ。将来予定は pre-register されない。
- Yahoo Finance ZQ 月別シンボルは 404 Not Found。
