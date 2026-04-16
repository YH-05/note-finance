# 議論メモ: こどもNISA記事執筆 + asset_managementトピック提案5本

**日付**: 2026-04-16
**参加**: ユーザー + AI
**関連Discussion**: `disc-2026-04-16-kodomo-nisa-article-workflow`
**Project**: 株投資ラボ収益化

## 背景・コンテキスト

asset_managementカテゴリ記事の新規発掘と実装を進めるため、`/topic-discovery asset_management --count 5` でトピック提案を行い、最高スコアから順に `/article-full` で記事化するワークフローを実行。1本目（こどもNISA）が投稿直前まで完了。

## トピック提案サマリー（2026-04-16 18:52）

| 順位 | トピック | スコア | KG Gap |
|------|---------|-------|--------|
| 1 | **こどもNISA完全ガイド — 2027年開始、年60万×累計600万円枠** | **48/50** | 8 |
| 2 | DINKS世帯の新NISA最適化 — 夫婦で3,600万円枠を3シナリオ | 46/50 | 8 |
| 3 | 4%ルールから3.9%へ — Morningstar 2026年改訂版で読む日本人取り崩し戦略 | 45/50 | 3 |
| 4 | 新NISA 1,800万円 最速5年 vs 15年分散 — 年収別最適ペース | 42/50 | 7 |
| 5 | 信託報酬0.05%時代の隠れコスト完全比較 — 2026年版ベストファンド | 40/50 | 6 |

## 議論のサマリー

### 1. 記事実装の優先順位

- ユーザー: 「5つ全部作成できる？」 → 技術的には可能だが2-4時間かかる旨をトレードオフ付きで提示
- 3プラン提示（A: 並列リサーチ+逐次執筆 / B: 全5本 skip-hf / C: 上位2本集中）
- ユーザー: 「じゃあまずは#1から実行して」 → 順次実行方針を採用（プランA寄り）

### 2. こどもNISA記事（#1）の実装

- Phase 1: `/article-init` — `articles/asset_management/2026-04-16_kodomo-nisa-2027-guide/` 作成
- Phase 2: `/article-research` — Web検索8クエリ + KG照会、15ソース収集
- Phase 3: `/article-draft` — 12,887字の初稿生成（beginner向け、10セクション）
- Phase 4: `/article-critique` — 総合スコア88/100、数値2箇所修正
- Phase 5: `/article-publish` — **ブロック中**（note.com セッション未作成）

### 3. 数値精度の問題発見と修正

批評プロセスで、月3万円・月5万円シナリオの18年後評価額がNISA上限600万円到達後のロジックを反映していなかったことを発見。

- 月3万円: 874万円 → **996万円**（16.67年で上限、残1.33年保有）
- 月5万円: 1,049万円 → **1,147万円**（10年で上限、残8年保有）
- 児童手当第1・2子運用: 395万円 → **390万円**（年齢別月額の複合積立）
- 児童手当第3子運用: 1,094万円 → **1,050万円**（NISA枠超過分は課税口座）

`uv run python` でmonthly FV公式を使い再計算して確定。

### 4. 表画像化の3列制約

`generate_table_image.py` がnote.com可読性のため列数上限を3列に強制。5列・4列の表はすべて3列に統合して再生成（全6テーブル＋1チャート、合計7枚完成）。

## 決定事項

1. **#1こどもNISAを最優先で先行実装** (`dec-2026-04-16-kodomo-nisa-first`)
   - 根拠: スコア48/50最高、2027-01開始の時事性、既存12記事ゼロカバー、KG 43ソース
2. **シミュレーション数値はNISA上限到達後の保有継続ロジックを反映** (`dec-2026-04-16-simulation-calc-precision`)
   - 今後のasset_management記事でも同じロジックを踏襲
3. **全表画像は3列以下に整形** (`dec-2026-04-16-table-3-column-constraint`)
   - note.com可読性 + `generate_table_image.py` の仕様制約
4. **残り4本は#1投稿完了後に順次article-fullで作成** (`dec-2026-04-16-remaining-4-articles-serial`)
   - 並列実行せず、note.com投稿も逐次のため順次が妥当

## アクションアイテム

- [ ] **note.com ログインセッション作成**（blocked: ユーザー手動）
      `! uv run python scripts/publish_to_note.py --login-only` をClaude Code入力欄で実行
- [ ] **こどもNISA記事 note.com 下書き投稿**（high / pending）
      ログイン完了後 `! uv run python scripts/publish_to_note.py articles/asset_management/2026-04-16_kodomo-nisa-2027-guide/`
- [ ] **#2 DINKS世帯記事作成**（high / pending）
- [ ] **#3 4%ルール記事作成**（medium / pending）
- [ ] **#4 1,800万円埋め方記事作成**（medium / pending）
- [ ] **#5 信託報酬記事作成**（low / pending）

## 現在のファイル状況

| パス | 状態 |
|------|------|
| `articles/asset_management/2026-04-16_kodomo-nisa-2027-guide/meta.yaml` | status=review, publish=pending |
| `01_research/research_notes.md` | 完成（12セクション） |
| `01_research/sources.json` | 完成（15ソース） |
| `02_draft/first_draft.md` | 完成（12,887字） |
| `02_draft/critic.json` + `critic.md` | 完成（スコア88） |
| `02_draft/revised_draft.md` | 完成（投稿用） |
| `images/*.png` | 7枚生成済み |

## 次回の議論トピック

- note.com ログインが完了したか確認
- #2 DINKS記事のリサーチ方針（「DINKS層向け」の具体シミュレーション設計）
- 残り4本の順序（スコア順 vs 時事性順）

## 参考情報

- Session file: `.tmp/topic-suggestions/2026-04-16_1852.json`
- JSONL: `data/topic-history/suggestions.jsonl`
- トピック提案の背景データ: research-neo4j KGから`NISA制度`(133 sources)、`DINKS`(109 sources)、`つみたて投資枠`(109 sources)等
