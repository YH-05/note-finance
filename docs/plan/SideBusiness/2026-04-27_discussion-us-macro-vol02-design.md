# 議論メモ: 米国マクロ経済 weekly vol.2 — テーマ・構成確定（PCE/CPI乗離）+ 戦略整合

**日付**: 2026-04-27
**参加**: ユーザー + AI
**前提議論**:
- `2026-04-08_discussion-us-macro-weekly-collectors.md`（インフラ実装）
- `2026-04-11_discussion-us-macro-vol01-design.md`（vol.1 設計、本日アーカイブ判断）
- `2026-04-27_discussion-kabu-lab-monetization-strategy.md`（同日朝の戦略議論）
**設計書**: `docs/plan/2026-04-08_us-macro-weekly-article-design.md`
**Neo4j Discussion ID**: disc-2026-04-27-us-macro-vol02-design

## 背景・コンテキスト

2026-04-11 に確定した米国マクロ経済 weekly vol.1（メインテーマ「インフレの現在地（CPI主軸）」、サブタイトル「コア vs 住居費 ─ 3月CPI で見えたインフレの二層化」）は、3月CPI（4/10発表）を主軸にした設計だったが、**初稿執筆未着手のまま16日が経過**し、CPI発表からのタイムリー性が失われた。

加えて、同日朝の議論（disc-2026-04-27-kabu-lab-monetization-strategy）では asset_management 特化方針が決定されたが、これは「macro_economy/stock_analysis/earnings の新規執筆休止」ではなく、「**主力カテゴリの選択（asset_management 優先）**」が正しい意図であることを再確認した。マクロ記事執筆は引き続き継続対象である。

これらを踏まえ、本セッションでは vol.1 をアーカイブし、**vol.2 にスキップ**して今日（2026-04-27）時点で取得可能なデータをベースにテーマ・構成・サブタイトルを確定。

## 議論のサマリー

### 今日時点で取得可能な主要指標

| 指標 | 公表日 | 状況 | vol.2 での役割 |
|---|---|---|---|
| **3月PCE（個人所得・支出）** | **4/26（土）** | ✅ 公表済 | **主軸** |
| 4月ミシガン大消費者信頼感（確報） | 4/25（金） | ✅ 公表済 | 補助 |
| 3月耐久財受注 | 4/24（木） | ✅ 公表済 | 補助 |
| 3月新築住宅販売 | 4/23（水） | ✅ 公表済 | 補助 |
| 3月CPI / PPI | 4/10 / 4/17 | ✅ 公表済 | 文脈・対比 |
| 4月CB消費者信頼感 | 4/29（水） | ⏳ 2日後 | 公開時に追加 |
| Q1 GDP速報 | **4/30（木）** | ⏳ 3日後 | **共軸** |
| 4月ISM製造業 / 雇用統計 | 5/1 / 5/2 | ❌ 公開後 | — |
| FOMC | 5/6-7 | ❌ 公開後 | — |

### 設計の確定プロセス

1. **メインテーマ**: 設計書ローテ表の第4週「PCE・GDP & 消費者心理」に忠実
2. **深掘り中心論点**: 4候補から「**PCE と CPI の乗離（Fedが見る物価の実貌）**」を採用
   - PCEとCPIはウエイト付け・住居費扱い・医療費扱いで乗離し、最近そのギャップが拡大
   - 「CPI見てFedを語るメディア」との差別化に効く角度
3. **サブタイトル**: b案「**PCEとCPIの乗離 ─ Fedの目に映る物価の実貌**」を採用（vol.1と同じくb案系統）
4. **公開タイミング**: 4/30夜（GDP速報リリース後）

### 戦略整合の確認

- **asset_management 集中方針 ≠ macro 執筆休止** であることをユーザーから明確化
- 4/27 朝の Decision/ActionItem に「新規執筆休止」と読める文言があったため、本セッションで訂正

## 決定事項

### dec-2026-04-27-us-macro-vol02-skip-from-vol01（vol.1アーカイブ）
vol.1（3月CPI主軸）はタイムリー性失効により未執筆のままアーカイブし、vol.2 にスキップする。

**Why**: 3月CPI発表（4/10）から17日経過し、すでに3月PCE（4/26）が公表されたため、CPIを主軸にする鮮度上のメリットが消失。vol.1 設計資産（スーパーコア論点等）は vol.2 深掘りに部分転用される（PCEとCPIの乗離分析の文脈で活用可能）。

**How to apply**: `articles/macro_economy/2026-04-13_us-macro-weekly-vol01/` フォルダは作成しない。設計書ローテ表は今後も「第2週=インフレの現在地」を維持し、5月第2週（CPI再発表時）に新たな vol.X として書き起こす。

### dec-2026-04-27-us-macro-vol02-main-theme（メインテーマ）
vol.2 のメインテーマは設計書ローテ第4週通り「**PCE・GDP & 消費者心理**」で確定。

**Why**: 4月最終週は PCE（4/26）、GDP速報（4/30）、CB消費者信頼感（4/29）が連続する第4週ど真ん中。設計書ローテに忠実に従うことでシリーズの一貫性が保たれる。

**How to apply**: 主軸データは 3月PCE + Q1 GDP速報。補助は 4月ミシガン大確報・4月CB消費者信頼感。

### dec-2026-04-27-us-macro-vol02-deepdive（深掘り中心論点）
vol.2 メインテーマ深掘り（2,500-3,000字）の中心論点は「**PCE と CPI の乗離 ─ Fedが見る物価の実貌**」に絞る。

**Why**: Fedの今期目標はPCEだが、メディアはCPIをヘッドラインで使う。両者はウエイト付け・住居費扱い・医療費扱いで乗離し、最近そのギャップが拡大。「CPI見てFedを語る」型との差別化に効く。vol.1 で深掘り候補だった「スーパーコア論点」もこの文脈に取り込める。

**How to apply**: PCE/CPI 両指標の系列・サブカテゴリ別データを取得。重み比較・寄与度分解・時系列乗離をチャート化。

### dec-2026-04-27-us-macro-vol02-subtitle（サブタイトル）
vol.2 のサブタイトルは「**PCEとCPIの乗離 ─ Fedの目に映る物価の実貌**」に確定。
フルタイトル: **「米国マクロ経済 vol.2 ─ PCEとCPIの乗離 ─ Fedの目に映る物価の実貌」**

**Why**: フック（深掘り論点）と中身（乗離分析）の連携が強く、vol.1 と同じくb案系統で読み手の選別コツが早く立つタイトル力。

**How to apply**: meta.yaml の topic フィールドに反映。シリーズ趣旨ブロック（vol.1 用に設計）はそのまま冒頭に再利用。

### dec-2026-04-27-asset-mgmt-priority-rephrase（4/27 朝の方針の文言訂正）
4/27 朝の `dec-2026-04-27-asset-mgmt-focus` で「macro_economy/stock_analysis/earningsの新規執筆を当面休止」と読める文言があったが、ユーザー意図は「**主力カテゴリの選択（asset_management 優先）**」であり、他カテゴリの新規執筆を完全停止するものではない。旧Decision/旧ActionItem を superseded/blocked に変更し、新たに優先順位ベースの方針を確定する。

**Why**: 「休止」と「優先順位の傾斜」では実務行動が大きく異なる。今後のマクロ・個別株・決算記事の判断基準を明確化する必要がある。

**How to apply**: asset_management を主力（時間配分の過半）とし、macro_economy/stock_analysis/earnings は **継続執筆対象**。ただし新規企画の優先順位は asset_management に対して低い位置づけ。

### dec-2026-04-27-vol02-publish-target（公開タイミング）
vol.2 の公開予定は **2026-04-30夜（Q1 GDP速報リリース後）**。

**Why**: GDP速報を含めることで設計書ローテ第4週の「PCE・GDP & 消費者心理」に完全準拠でき、シリーズの一貫性を担保。同時に4月最終週の主要指標を全て織り込んだ「月末まとめ」的価値も持たせられる。

**How to apply**: 4/30 朝にGDP速報用のデータ取得スクリプトを再実行 → 速報リリース後にチャート再生成 → 同日夜にドラフト→批評→修正→公開。

## アクションアイテム

- [ ] **[高/2026-04-27]** 記事フォルダ作成: `articles/macro_economy/2026-04-30_us-macro-weekly-vol02/`
- [ ] **[高/2026-04-27]** `scripts/collect_us_macro_data.py` を走らせて3コレクター動作確認＋出力データを vol.2 フォルダに配置
- [ ] **[高/2026-04-27]** quants `fred_series.json` に9系列追加（GDPNOW, RSAFS, HOUST, PERMIT, DGORDER, HSN1F, PCEPILFE, A191RL1Q225SBEA, ADPMNUSNERSA）
- [ ] **[高/2026-04-27]** PCE-CPI 乗離分析に必要な追加データ系列のリストアップ（PCEPI, PCEPILFE, CPIAUCSL, CPILFESL のサブカテゴリ別データ等）+ メモ化
- [ ] **[高/2026-04-30]** vol.2 初稿執筆（GDP速報リリース後、当日夜公開を目標）
- [ ] **[中/2026-04-30]** チャート生成: PCE-CPI 乗離（過去5年）、PCE/CPI寄与度分解、消費者心理2指標比較
- [ ] **[中/2026-04-29]** スーパーコア定義の最終確定（FRBは "services less energy services and shelter"、CPI なら CUSR0000SASLE。PCE 版もどの系列を使うか確定）

## 戦略整合の訂正アクション（4/27 朝の議論結果の修正）

- [ ] **[高/即時]** Neo4j上で `dec-2026-04-27-asset-mgmt-focus` を `status='superseded'` に変更
- [ ] **[高/即時]** Neo4j上で `act-2026-04-27-kabu-stop-non-asset` を `status='blocked'`、`blocked_reason` を「ユーザー意図と乖離。新規執筆休止ではなく『主力カテゴリ選択（asset_management 優先）』が正しい意図」に変更
- [ ] **[高/即時]** 新規 Decision `dec-2026-04-27-asset-mgmt-priority-rephrase` を Neo4j に追加（上記方針）

## 次回の議論トピック

- vol.2 初稿の品質チェック観点（critique フェーズで何を見るか）
- vol.3 のテーマ確定（5月第1週=「雇用 & 景気の体力」、NFP 5/2 + ISM 5/1 + FOMC 5/6-7 結果を踏まえた角度）
- スーパーコア定義（FRBの "supercore" = "services less energy services and shelter"、CPI なら CUSR0000SASLE）の最終決定
- 設計書のメインテーマローテ表に第5週・FOMC週の取り扱いルールを追加するか

## 参考情報

- vol.1 設計（アーカイブ）: `docs/plan/SideBusiness/2026-04-11_discussion-us-macro-vol01-design.md`
- インフラ実装議論: `docs/plan/SideBusiness/2026-04-08_discussion-us-macro-weekly-collectors.md`
- 設計書本体: `docs/plan/2026-04-08_us-macro-weekly-article-design.md`
- 同日朝の戦略議論: `docs/plan/SideBusiness/2026-04-27_discussion-kabu-lab-monetization-strategy.md`
- データコレクター: `scripts/collect_us_macro_data.py`

---

## 実行結果（2026-04-27 セッション末追記）

### Phase 4 フル検証完了

本セッション内で4つの実行タスクを完了。Neo4j 上で対応 ActionItem は `completed` に更新済み。

| タスク | 結果 | 成果物 |
|---|---|---|
| 記事フォルダ作成 | ✅ | `articles/macro_economy/2026-04-30_us-macro-weekly-vol02/`（meta.yaml + サブディレクトリ） |
| collect_us_macro_data.py 実行 | ✅ | `data/cot_fed_funds.json`、`data/fed_futures.json`、`data/fred_calendar.json` |
| quants fred_series.json に9系列追加 | ✅ | `/users/yukihata/desktop/quants/data/config/fred_series.json`（63→72系列、JSON valid 確認済み） |
| PCE-CPI 乗離分析データ系列リストアップ | ✅ | `articles/macro_economy/2026-04-30_us-macro-weekly-vol02/data_requirements.md`（Tier 1〜5 + チャート要件 + スケジュール） |

### 🔍 重要な事実訂正

`collect_us_macro_data.py` の FRED Calendar 出力（`data/fred_calendar.json`）から判明：

| 指標 | 当初認識 | 実際 |
|---|---|---|
| Personal Income and Outlays（PCE含む） | 「3月PCE は 4/26 公表済」 | **latest=2026-04-09（2月PCE）**。3月PCE は未公表で、BEA慣例から **4/30 GDP速報と同時リリース見込み** |

vol.2 公開予定 4/30夜 は変わらず有効。ただし「今日（4/27）時点で取得可能なデータで vol.2 を進める」という前提は崩れたため、4/30 朝のリリース後にデータ取得・チャート生成・初稿執筆を一気通貫で行う必要がある。

### 残 pending ActionItem（3件）

| ID | 期日 | 優先度 | 内容 |
|---|---|---|---|
| `act-2026-04-29-supercore-definition` | 2026-04-29 | 中 | スーパーコア定義の最終確定（PCE版該当系列特定） |
| `act-2026-04-30-vol02-draft` | 2026-04-30 | 高 | vol.2 初稿執筆（GDP速報リリース後、当日夜公開を目標） |
| `act-2026-04-30-vol02-charts` | 2026-04-30 | 中 | チャート5枚生成（PCE-CPI 乗離、寄与度分解、消費者心理、スーパーコア、GDP寄与度） |

### Neo4j 保存サマリー（最終）

- Discussion: 1 (`disc-2026-04-27-us-macro-vol02-design`)
- Decision: 6 (新規 active 6件)
- ActionItem: 7 (completed 4件 + pending 3件)
- リレーション: RESULTED_IN×6, PRODUCED×7, SUPERSEDES×1
- 訂正: `dec-2026-04-27-asset-mgmt-focus` → superseded、`act-2026-04-27-kabu-stop-non-asset` → blocked

### 次回セッション開始時のチェックリスト

1. `data/fred_calendar.json` を再取得して 3月PCE が公表済みかを確認（4/30 朝）
2. `act-2026-04-29-supercore-definition` の確定（CPIなら CUSR0000SASLE、PCEは要調査）
3. Tier 1-2 の追加データ系列を取得するスクリプト/ノートブックの用意
4. vol.2 初稿執筆 → 批評 → 修正 → 公開の一気通貫実行
