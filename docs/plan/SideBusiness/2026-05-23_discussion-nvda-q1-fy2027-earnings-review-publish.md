# 議論メモ: NVIDIA Q1 FY2027決算レビュー記事の /article-full 一気通貫実行

**日付**: 2026-05-23
**参加**: ユーザー + AI (Claude Opus 4.7)
**プロジェクト**: 株投資ラボ収益化

## 背景・コンテキスト

NVIDIAは2026-05-20にFY2027 Q1決算を発表。売上$81.6B（+85% YoY）、Non-GAAP EPS $1.87、Q2ガイダンス$91B（中国Data Center compute売上ゼロ前提）と表面的には完璧な内容だったが、決算翌日の株価は -1.8%（4回連続の下落）という二面性のあるイベントだった。

このイベントに対応する earnings_review カテゴリの記事ディレクトリ `articles/earnings/2026-05-23_nvda-q1-fy2027-earnings-review-blackwell-china/` が既に初期化されていたため、`/article-full` で Phase 2 (リサーチ) から Phase 5 (note.com 投稿) までを完全自動で一気通貫実行した。

## 議論のサマリー

今回はユーザーとの対話的議論ではなく、`/article-full` の無人実行ワークフローとその過程で得られた**運用上の学び**が議論対象。

### 実行結果

| フェーズ | 実施内容 | 成果物 |
|---------|---------|--------|
| Phase 2 リサーチ | research-neo4j照会 + Web/Tavily/SECで実績収集 | 01_research/ に5ファイル（gap_report, facts, claims, sources, research_note） |
| Phase 3 ドラフト | 8セクション・約4,200字の初稿 | 02_draft/first_draft.md |
| Phase 4 批評・修正 | 自前簡易批評（無人モード）+ リバイザー + 表5枚画像化 | 02_draft/revised_draft.md + images/*.png（5枚） |
| Phase 5 投稿 | タイトル修正 → ダッシュ除去 → 挨拶文追加 → note.com下書き投稿 | https://editor.note.com/notes/n2ce4b323f423/edit/ |

### 運用上の発見

1. **earnings_review タイトル必須フォーマット**: 「【🇺🇸米株決算】{企業名}（{ティッカー}）Q{1-4} {YYYY} 決算レビュー」形式が必須で、article-publish スキルが投稿前に強制検証。FY表記やダッシュ記号（——/—/--）は事前に修正しないと弾かれる。
2. **/generate-table-image の3列上限**: スクリプトが3列以上を `ValueError: 列数が6列です（上限: 3列）` で拒否。note.com 読みやすさのため、最初から3列構成で設計する必要がある。
3. **Pencil サムネイルは無人実行ではスキップが安全**: article-earnings-thumbnail はPencil MCP依存で重コスト。`/article-full` の無人実行では中断リスクのためスキップし、明示的に後で呼び出す運用に統一する。

## 決定事項

1. **earnings_review タイトル形式の統一**（`dec-2026-05-23-earnings-review-title-format`）
   - 「【🇺🇸米株決算】{企業名}（{ティッカー}）Q{1-4} {YYYY} 決算レビュー：{サブタイトル}」
   - FY表記・ダッシュ記号（——/—/--）禁止

2. **表は3列上限で再設計**（`dec-2026-05-23-table-image-3col-limit`）
   - `/generate-table-image` の制約に合わせ、最初から3列構成で設計
   - 情報量はセル内に「数値1 / 数値2」のように区切って圧縮

3. **無人実行時のサムネイル生成はスキップ**（`dec-2026-05-23-article-full-unattended-thumbnail-skip`）
   - Pencil MCP 依存のサムネイル生成は `/article-full` ではスキップ
   - 必要に応じて `/article-earnings-thumbnail` を後続で明示的に呼び出す

## アクションアイテム

- [ ] **(高)** note.com下書き(n2ce4b323f423)を開きカバー画像・ハッシュタグを設定して公開する（〜5/24）
- [ ] **(中)** NVIDIA決算レビュー記事のサムネイルを /article-earnings-thumbnail で生成（har1Rテンプレ・グリーンバッジ）（〜5/24）
- [ ] **(中)** 対応プレビュー記事(2026-05-12_nvda-q1-fy2026-earnings-preview-blackwell-capex)が初稿テンプレートのままになっている件の方針決定（埋める or deprecated扱い）
- [ ] **(低)** Q2 FY2027 watch points（H200中国出荷、Networking持続、Sovereign AI、ACIE +31%維持、CSP Capex下期）を次回決算プレビュー記事の論点候補としてresearch-neo4jに登録（〜8/1）

## 次回の議論トピック

- **earnings_review ワークフローの自動化深化**: タイトルフォーマット検証を `/article-draft` 段階で前倒し実施するべきか
- **`/article-full` の批評強化**: 今回は無人モードで簡易批評（自前生成）だったが、finance-critic-* エージェント群を並列スポーンする本格批評モードを `/article-full --critique=full` で選択可能にする設計
- **earnings_preview と earnings_review のペアリング戦略**: プレビュー記事が空のまま放置されているケースをどう扱うか（自動補完 / アーカイブ / 個別判断）

## 参考情報

### 今回参照した1次出典

- NVIDIA Q1 FY2027 Press Release (https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx)
- NVIDIA Q1 FY2027 Earnings Call Transcript (https://s201.q4cdn.com/141608511/files/doc_financials/2027/q1/NVDA-Q1-2027-Earnings-Call-20-May-2026-5_00-PM-ET.pdf)
- SEC Form 8-K NVDA Q1 FY2027 (https://www.sec.gov/Archives/edgar/data/0001045810/000104581026000051/q1fy27pr.htm)

### note-neo4j 保存先

- Discussion: `disc-2026-05-23-nvda-q1-fy2027-earnings-review`
- Decisions: `dec-2026-05-23-earnings-review-title-format`, `dec-2026-05-23-table-image-3col-limit`, `dec-2026-05-23-article-full-unattended-thumbnail-skip`
- ActionItems: `act-2026-05-23-001` 〜 `act-2026-05-23-004`
