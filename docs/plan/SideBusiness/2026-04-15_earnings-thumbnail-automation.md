# 議論メモ: 決算記事サムネイル自動化スキル作成

**日付**: 2026-04-15
**参加**: ユーザー + AI

## 背景・コンテキスト

株投資ラボの earnings 記事（`category: earnings`）では毎回 note.com 用サムネイルを作成していたが手作業コストが高かった。企業ロゴ・ティッカー・Q/決算日・タイトル（preview/review）が毎回必要であり、統一デザインで自動生成する仕組みを構築する必要があった。

ユーザーはスキル + コマンドとして `article-earnings-thumbnail` を作成することを希望。Pencil テンプレート化、ロゴの自動取得、revised_draft 生成後の自動発動が要求事項。

## 議論のサマリー

要件確認で4点を固めた:

1. **サイズ**: note.com 推奨 1280×670px（OGP対応）で確定
2. **ロゴソース**:
   - Wikipedia MCP は本文取得のみでロゴURLを返さないことを確認
   - Wikidata P154（logo image）クレーム経由が最も堅牢と判明
   - Clearbit Logo API は DNS 廃止（`logo.clearbit.com` が 2025 年以降 resolve 不可）
   - SEC EDGAR `company_tickers.json` を二段目フォールバックに採用
3. **レイアウト**: 白背景 / 左半分ロゴ / 右半分テキスト（縦線セパレーター）/ 右下「株投資ラボ」バッジ
4. **発動タイミング**: 自動実行（`/article-revise` と `/article-critique` の revised_draft.md 生成後）

実装中に以下の技術課題を解決:

- 曖昧ティッカー問題: `UNH` は Wikipedia 直接検索で University of New Hampshire にヒットしてしまう。SEC EDGAR で公式名「UNITEDHEALTH GROUP INC」を解決し、Wikipedia 検索候補の先頭に配置することで解消。
- SEC EDGAR UA 要件: `YH-05 note-finance youxitiancore@gmail.com` 形式でないと 403 になるため、SEC専用セッションで個別 UA 指定。
- Pencil への画像挿入: フレームの `fill` プロパティに `file://` 絶対パス URL を指定することで動作確認。
- Pencil export_nodes は `scale=2` で Retina 対応（実解像度 2560×1340 PNG）。

## 決定事項

1. **Pencil テンプレ採用**: `/Users/yukihata/Desktop/new.pen` に「Thumbnail - 決算」フレーム（nodeId = `CAXCU`、1280×670、白背景）を新設。子ノード `f8jSq`/`ZByjU`/`CFBpG`/`VbtEH`/`mlUJ1`/`uGtyD` で構成。テキスト上書きと画像 fill 差し替えで再利用。
2. **Wikidata P154 + SEC EDGAR フォールバック**: ロゴ取得パイプラインは SEC 公式名解決 → Wikipedia summary（wikibase_item）→ Wikidata P154 → Commons Special:FilePath の順。Clearbit は廃止で不採用。
3. **自動発動**: `category == earnings` の場合、`.claude/skills/article-revise/SKILL.md` Step 3.5 と `.claude/commands/article-critique.md` Step 4.5 で `/article-earnings-thumbnail` を自動呼び出し。

## アクションアイテム

- [ ] 既存の他 earnings 記事（TSLA/UNH/IBM/GE/BLK）にも本コマンドを適用し `images/thumbnail.png` を生成（優先度: 中）
- [ ] P154 クレーム未設定の企業に備え、手動ロゴ指定オプション（`--logo-path`）の追加検討（優先度: 低）
- [ ] 次回の新規 earnings 記事で `/article-revise` 経由の自動発動が期待通り動作するか実運用検証（優先度: 高）

## 次回の議論トピック

- サムネ生成時のロゴ背景処理（Netflix のような赤背景 SVG は許容するか、透過化処理を加えるか）
- earnings 以外のカテゴリ（stock_analysis、macro_economy 等）向けのサムネテンプレ展開

## 参考情報

- Wikidata P154: https://www.wikidata.org/wiki/Property:P154 （logo image）
- SEC EDGAR tickers: https://www.sec.gov/files/company_tickers.json （UA 必須）
- Pencil MCP: frame / text / rectangle / image fill + export_nodes (scale=2)
- 成果物: `articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/images/thumbnail.png`（2560×1340 PNG）
