# 議論メモ: 決算サムネイル v2 — テンプレ拡張と全記事バックフィル

**日付**: 2026-04-15
**参加**: ユーザー + AI

## 背景・コンテキスト

2026-04-15 早朝に `article-earnings-thumbnail` スキル・コマンド v1 を構築（ロゴ取得 + Pencilテンプレ `CAXCU`）。同日午後、ユーザーからのフィードバックを受けて v2 に拡張した。

改修要件:
1. サムネイルに企業名を追加（v1 ではティッカーのみ）
2. 企業名を主役（大見出し）、ティッカーを脇役（小見出し）に入れ替え
3. 決算レビュー用の専用テンプレを新設（プレビュー版と並列）
4. これまでの全 earnings 記事（9件）にバックフィル適用

## 議論のサマリー

### テンプレ構造の再設計

プレビュー版 `CAXCU` の子ノードレイアウトを再構成:
- y=150 にあった `CFBpG` Ticker (88px) を **小見出し** に縮小（32px Medium, y=260）
- 新規追加した `6g00c` CompanyName を **大見出し** に昇格（64px Bold, y=150）
- 「Netflix, Inc.」「BlackRock, Inc.」のような企業名が紙面の顔になる構成に変更

### レビュー版テンプレの新設

Pencil `.pen` 内に新フレーム `har1R`（「Thumbnail - 決算レビュー」）を作成:
- 10個の子ノード（Logo Container / LOGO Placeholder / Separator / CompanyName / Ticker / Subtitle / EarningsDate / Brand Badge / Badge text）
- 構造はプレビュー版と同一
- **ブランドバッジ色のみ差別化**: プレビュー `#111827`（ネイビー）vs レビュー `#059669`（グリーン）
- サブタイトル既定値: `Q1 YYYY 決算レビュー`
- `type: earnings_review` のときにスキルが自動選択

### 全 earnings 記事への適用

9記事に一括バックフィル:

| # | ティッカー | 企業名 | 種別 |
|---|-----------|--------|------|
| 1 | BLK | BlackRock, Inc. | プレビュー |
| 2 | JPM | JPMorgan Chase | プレビュー |
| 3 | TSM | TSMC | レビュー |
| 4 | BLK | BlackRock, Inc. | レビュー |
| 5 | GE | GE Aerospace | プレビュー |
| 6 | NFLX | Netflix, Inc. | プレビュー |
| 7 | TSLA | Tesla, Inc. | プレビュー |
| 8 | UNH | UnitedHealth Group | プレビュー |
| 9 | IBM | IBM | プレビュー |

JPM と TSM のロゴは Wikidata P154 経由で新規取得（キャッシュ追加）。TSM は企業名「Taiwan Semiconductor」が 560px 枠を超過したため「TSMC」に短縮。

### 運用上の判明事項

- Pencil の `fill.url` が URL 単位でキャッシュされるため、同じ `file://` パスで内容差し替えは効かない。実行ごとに `/tmp/{TICKER}_{timestamp}.png` へコピーして一意URLを渡す必要がある（SKILL.md に明記済み）
- 64px Bold で約15文字まで収まる。「UnitedHealth Group」（18文字）でギリギリ、「Taiwan Semiconductor Manufacturing」のような長い名前は通称（TSMC等）へ要短縮
- 企業名解決は SEC EDGAR 正規化より手動の DISPLAY_NAME マップが実用的（SECの "JPMORGAN CHASE & CO" → 手動で "JPMorgan Chase"）

## 決定事項

1. **企業名を主役、ティッカーを脇役に配置**: Pencilテンプレ `CAXCU` / `har1R` とも大見出し（64px Bold）を企業名、小見出し（32px Medium）をティッカーに統一。
2. **レビュー版テンプレを独立ノードで管理**: プレビュー `CAXCU` とレビュー `har1R` を別フレームで保持し、`type` フィールドでスキル側が振り分ける。視覚差別化はバッジ色（ネイビー vs グリーン）のみ。
3. **企業表示名は手動メンテ**: `DISPLAY_NAME` マップで各ティッカーの表示名を固定。SEC EDGAR 正規化アルゴリズムは副作用が大きい（例: "Jpmorgan Chase &"）ため、実用的な通称を明示的に定義する。

## アクションアイテム

- [ ] 新規 earnings 記事（Q2 2026 以降）での自動発動を実運用検証（優先度: 高 — 既存の `act-2026-04-15-thumbnail-auto-trigger-verify` を継続）
- [ ] 企業名が 64px Bold で枠を超える銘柄（Taiwan Semiconductor, International Business Machines 等）を想定した `DISPLAY_NAME` マップ整備（優先度: 中）
- [ ] `P154` クレーム未設定の企業に備えた `--logo-path` 手動指定オプション（優先度: 低 — 継続）

## 次回の議論トピック

- earnings 以外のカテゴリ（stock_analysis、macro_economy、asset_management 等）向けサムネテンプレの展開
- ロゴ取得パイプラインの汎用化（earnings 以外でも使えるよう `category` 非依存に）

## 参考情報

- Pencilテンプレ保存先: `/Users/yukihata/Desktop/new.pen`
- プレビュー版: frame `CAXCU` 内に `6g00c` (CompanyName 大) / `CFBpG` (Ticker 小) / `VbtEH` (Subtitle) / `mlUJ1` (Date) / `uGtyD` (Badge ネイビー)
- レビュー版: frame `har1R` 内に `psqPo` (CompanyName 大) / `8Zjbx` (Ticker 小) / `xUTDJ` (Subtitle) / `9z5hB` (Date) / `D4lnA` (Badge グリーン)
- バッチ処理中間ファイル: `.tmp/earnings_thumb_batch.json`（9記事分のパラメータ）
