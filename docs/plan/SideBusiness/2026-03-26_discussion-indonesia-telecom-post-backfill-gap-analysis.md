# 議論メモ: インドネシア telecom セクターの post-backfill ギャップ再診断

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

同日に以下を実施済み。

- `2026-03-26_discussion-indonesia-telecom-gap-analysis.md`
- `2026-03-26_discussion-indonesia-telecom-deterministic-backfill.md`

決定論的バックフィルによって `research-neo4j` の `domains / facts / claims` は大きく改善したため、その状態を前提にインドネシア telecom セクターのデータ状況を再評価した。

## 議論のサマリー

### 改善した点

- `Claim -> Entity` の `ABOUT` が大幅に補完され、対象企業の接続性は以前より改善
- `Fact.source_url` と `Fact.as_of_date` のうち、既存グラフから一意に導けるものは補完済み
- レポート前の「何について書いてあるか分からない」状態はかなり解消

### 依然として足りない点

#### 1. 出典品質が弱い

主要4社の Source は依然として synthetic URL が多い。

- `Telkom Indonesia`: 66 source のうち http は 4
- `Indosat Ooredoo Hutchison`: 82 source のうち http は 1
- `Telkomsel`: 19 source のうち http は 4
- `XLSmart`: 18 source のうち http は 5

`gemini-search-aggregated://...` が多く、脚注や検証可能性の観点ではまだ弱い。

#### 2. Fact の日付欠損が大きい

- `Telkom Indonesia`: 30 / 30 facts が `as_of_date` 欠損
- `Telkomsel`: 43 / 44 facts が `as_of_date` 欠損
- `XLSmart`: 21 / 21 facts が `as_of_date` 欠損
- `Indosat`: 29 / 51 facts が `as_of_date` 欠損

比較レポートで「直近」「四半期推移」を書くにはまだ不足。

#### 3. TowerCo 比較材料が不足

`FinancialDataPoint` の偏りが大きい。

- `Telkom Indonesia`: 71
- `Indosat`: 66
- `Telkomsel`: 41
- `XL Axiata`: 5
- `XLSmart`: 4
- `Mitratel / Tower Bersama Infrastructure / Sarana Menara Nusantara / Protelindo`: 0

TowerCo 比較表を作れる状態ではない。

#### 4. 規制ノードの独立性が弱い

`Komdigi` は `claims=40` あるが、`facts=1`, `insights=0`, `about_sources=1` に留まる。サンプルを見ると ISAT 側レポート文脈からの派生が多く、規制専用クラスタとしては弱い。

#### 5. Topic / Insight の論点粒度が粗い

Topic の接続数は以下。

- `ASEAN Telecom`: 529
- `Indonesian Telecom`: 394
- `Telecom M&A`: 96
- `Tower Sharing`: 0
- `Telecom Network Economics`: 0
- `Telecom Sustainability`: 0

論点別の章立てを組むには、Topic と Insight の独立性が不足している。

#### 6. 一部に意味的な誤接続の疑いがある

`Mitratel` には `claims=27` あるが、サンプルは Telkomsel の 5G・FMC 文脈が多く、Mitratel 固有の主張としては不自然。件数増加とデータ品質は別問題であることが確認された。

## 決定事項

1. 決定論的バックフィル後の現状では、インドネシア telecom の「企業比較レポート」にはまだ直行しない
2. 次の重点補強対象は `公式 source 置換 / as_of_date 補完 / TowerCo KPI / Komdigi 規制論点 / Topic 粒度改善 / 誤接続点検` とする

## アクションアイテム

- [ ] `Telkom Indonesia / Telkomsel / Indosat Ooredoo Hutchison / XLSmart` の synthetic source を公式 IR・公式 release に置換する (優先度: 高)
- [ ] `Mitratel / Tower Bersama Infrastructure / Sarana Menara Nusantara / Protelindo / Komdigi` を対象に、KPI・規制ファクト・独立 Insight を追加する (優先度: 高)
- [ ] `Mitratel` など TowerCo 周辺の Claim 接続を点検し、意味的な誤接続を修正する (優先度: 中)

## 次回の議論トピック

- P0 を先に全部埋めるか、Telkom / Indosat の2社比較だけ先に書くか
- TowerCo をレポート本体に含めるか、別章または別レポートに切り出すか
- Komdigi を規制章として独立させるか、各企業章のリスク節に分散させるか

## 参考情報

- `disc-2026-03-26-indonesia-telecom-gap-analysis`
- `disc-2026-03-26-indonesia-telecom-deterministic-backfill`
- `research-neo4j` 再診断クエリ結果（2026-03-26）
