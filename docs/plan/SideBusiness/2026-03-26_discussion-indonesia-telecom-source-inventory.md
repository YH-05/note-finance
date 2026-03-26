# 議論メモ: インドネシア telecom の Indosat/XLSmart synthetic source 棚卸し

**日付**: 2026-03-26
**参加**: ユーザー + AI
**関連**:
- `disc-2026-03-26-indonesia-telecom-gap-analysis`
- `disc-2026-03-26-indonesia-telecom-deterministic-backfill`
- `disc-2026-03-26-indonesia-telecom-post-backfill-gap-analysis`

## 背景・コンテキスト

post-backfill 再診断で、インドネシア telecom 比較レポートの P0 として `Telkom Indonesia / Telkomsel / Indosat Ooredoo Hutchison / XLSmart` の synthetic source を公式 source に置換する方針を整理した。

その後、Telkom/Telkomsel 側では一次ソースが明確な 5 `Source` を公式 URL に置換し、対応する `Fact.source_url` / `Fact.as_of_date` を補完した。加えて `Mitratel` に誤接続していた non-null claim を 13 件削除した。

今回の議論では、残る `Indosat Ooredoo Hutchison` と `XLSmart / XL Axiata` の未置換 synthetic source について、単純な上書き置換が可能かを棚卸しした。

## 議論のサマリー

### 1. 棚卸し対象

`ABOUT`, `STATES_FACT`, `MAKES_CLAIM` を通じて `Indosat Ooredoo Hutchison`, `XLSmart`, `XL Axiata` に接続される synthetic source を点検した。

主な対象は以下。

- `src-bca-xlsmart`
- `src-rhb-excl`
- `src-xlsmart-5g`
- `d0ba35ac-de2e-5835-b83e-daf7fbcadaae` (`file:///equity_research/ISAT_IJ/research_memo`)
- 比較・セクター横断の `src-idn-*`, `src-sector-*`, `src-spectrum-auction`, `src-starlink-threat`

### 2. 分類結果

#### shared-sector: 11件

1社の公式 URL に置換すると provenance を壊すため、今回は非置換とした。

- `src-idn-arpu-comp`
- `src-idn-b2b-mkt`
- `src-idn-dc-mkt`
- `src-idn-fbb-share`
- `src-idn-mkt-repair`
- `src-idn-telecom-esg`
- `src-idn-tower-share`
- `src-sector-outlook`
- `src-sector-risks`
- `src-spectrum-auction`
- `src-starlink-threat`

#### hold-secondary: 2件

セルサイドの評価・目標株価・アップサイド前提を含み、一次ソースでそのまま代替できないため、secondary として保持する。

- `src-bca-xlsmart`
- `src-rhb-excl`

#### split-replace: 2件

company-specific だが、1本の公式 URL では中身を回収できない。fact/claim 単位で複数 official source に分割して付け替える必要がある。

- `src-xlsmart-5g`
- `d0ba35ac-de2e-5835-b83e-daf7fbcadaae`

#### exclude-noisy: 5件

接続先エンティティに見えても、実体は他社または sector 文脈であり、Indosat/XLSmart の source 置換対象から外す。

- `src-neutradc-valuation`
- `src-samuel-tlkm`
- `src-tlkm-danantara`
- `src-tsel-risk`
- `tlkm-research-memo-20260316`

### 3. 重要な判断

#### XLSmart

`src-xlsmart-5g` は company-specific に見えるが、実際には以下が混在している。

- merger 後の combined spectrum (`152 MHz`, `37 MHz sub-1GHz`)
- 5G/DSS (`1800/2100 MHz`)
- 2025年末時点の `2.3 GHz 40 MHz`

このため、単一 source の上書きは不適切であり、merger investor material、5G official page、追加開示資料へ分割する方針が妥当と判断した。

#### Indosat

`d0ba35ac-de2e-5835-b83e-daf7fbcadaae` は `ISAT_IJ Research Memo` であり、内容は以下を横断している。

- AI Native TechCo / GPU Merdeka / Sahabat-AI
- 経営陣 (`Vikram Sinha`, `Nicky Lee`)
- ARPU / app monetization
- Link Net 関連

これも単一の一次ソースで置換できず、AI、management、ARPU、Link Net などの論点別に split-replace が必要。

### 4. 既存 P0 タスクとの関係

- `Telkom/Telkomsel` 側では一次ソースが明確な 5 source は置換済み
- `Fact.source_url` / `Fact.as_of_date` は対応する 8 fact で補完済み
- `Mitratel` の明白な誤接続 claim 13件は削除済み

したがって、P0 の残りは「Indosat/XLSmart 側の overwrite ではなく split-replace 設計と実行」が中心課題となった。

## 決定事項

1. **Indosat/XLSmart の未置換 synthetic source は、company-specific でも単純な上書き置換を原則しない**
   - 1つの source に複数論点が混在している場合は `split-replace` を優先する

2. **shared-sector source は 1社の公式 URL に置換せず、BCA/RHB のようなセルサイド source は secondary として保持する**
   - 公式一次ソースで裏取りできる fact がある場合のみ、別 source に切り出して追加する

## アクションアイテム

- [ ] `src-xlsmart-5g` を `merger/spectrum`, `5G/DSS`, `追加開示` の複数 official source に分割し、fact/claim を付け替える (優先度: 高)
- [ ] `d0ba35ac-de2e-5835-b83e-daf7fbcadaae` を `AI`, `management`, `ARPU`, `Link Net` の論点別 official source に分割し、Indosat fact/claim を付け替える (優先度: 高)
- [ ] `src-bca-xlsmart` / `src-rhb-excl` のうち一次ソースで裏取り可能な fact だけを別 source として切り出し、secondary source への依存を減らす (優先度: 中)

## 次回の議論トピック

- `split-replace` を先に `XLSmart` から着手するか、`Indosat` から着手するか
- secondary source の保持ルールを `research-neo4j` 側でどこまで明示的に表現するか
- TowerCo / Komdigi の P1 補強に入る前に、P0 の split-replace をどこまで完了させるか

## 参考情報

- 公式候補 source:
  - `XLSmart / XL Axiata` merger investor materials
  - XL Axiata / XLSmart の 5G official page
  - IOH investor document portal
  - IOH AI / Sahabat-AI related official pages
- 点検結果:
  - `shared-sector`: 11件
  - `hold-secondary`: 2件
  - `split-replace`: 2件
  - `exclude-noisy`: 5件
