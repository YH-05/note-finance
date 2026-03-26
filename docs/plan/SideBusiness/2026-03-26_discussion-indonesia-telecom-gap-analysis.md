# 議論メモ: インドネシア telecom レポート着手前の research-neo4j ギャップ分析

**日付**: 2026-03-26
**参加**: ユーザー + AI
**関連**:
- `disc-2026-03-19-asean-telecom-research-gap`
- `disc-2026-03-19-indonesia-report-kg`
- `disc-2026-03-23-isat-report-gaps`

## 背景・コンテキスト

インドネシア telecom セクターのレポート作成に先立ち、research-neo4j 内の既存データを点検し、どの論点で情報が不足しているかを診断した。目的は「書けるかどうか」ではなく、「出典付きで比較可能なレポートを作れるか」を事前に判定すること。

今回の議論では、探索済みのグラフデータと既存 SideBusiness 文脈を踏まえ、レポート作成前の補強優先順位と検索方針を整理した。

## 議論のサマリー

### 1. 現状評価

- research-neo4j には `Telkom Indonesia`, `Telkomsel`, `Indosat Ooredoo Hutchison`, `XLSmart`, `Mitratel`, `Sarana Menara Nusantara`, `Tower Bersama Infrastructure` など主要ノードは存在する
- 一方で、`Protelindo` は `0 facts / 0 claims / 0 sources`、`Link Net` は `1 fact / 1 claim / 0 sources`、`Komdigi` は `3 facts / 1 source` と周辺領域の密度が薄い
- `Telkom Indonesia` と `Indosat` は件数自体は多いが、実 URL が少なく、`gemini-search-aggregated://` や `file:///...` 由来の synthetic な出典が多い
- `Fact.as_of_date` と `Source.published_at` の欠損が目立ち、時系列比較にそのまま使えない
- `FinancialDataPoint` は `Telkom Indonesia` と `Indosat` に偏り、tower 3 社や Smartfren の比較表材料が不足している
- Topic は `Indonesian Telecom` や `ASEAN Telecom` に集中し、`Tower Sharing`, `Telecom Network Economics`, `Telecom Sustainability`, `Telecom M&A` など論点別の粒度が粗い

### 2. 不足領域の整理

優先度は以下の通り。

#### P0: レポートの信頼性に直結

1. **出典の実在性・追跡可能性**
   - 主要企業で synthetic URL 依存が強い
   - 公式 IR / official release / real web URL への置換が必要

2. **時点情報**
   - `as_of_date`, `published_at`, `publisher` 欠損が多い
   - 四半期比較や「最新状況」の説明が弱い

3. **規制カバレッジ**
   - `Komdigi` とスペクトラム関連が薄い
   - 700MHz / 2.6GHz / network sharing / foreign ownership まわりの一次情報が不足

#### P1: 比較表・投資論点に重要

4. **TowerCo 比較データ**
   - `Mitratel / TOWR / TBIG / Protelindo` の構造化KPIが不足
   - tenancy ratio, tower count, EBITDA margin, capex, co-location が必要

5. **固定回線・B2B・DC**
   - IndiHome, enterprise, fiber, data center は Topic と Fact の接続が弱い
   - セクターレポートの差別化論点として補強余地が大きい

6. **競争構造の更新**
   - XLSmart 統合後の市場構造、price repair、outside Java 展開の裏付けが必要

#### P2: 書き味を上げる補助論点

7. **サステナビリティ・Tower sharing・Network economics**
   - ノードはあるがタグ密度が低い
   - 論点としては有効だが、優先度は上位より下

## 決定事項

1. **インドネシア telecom レポートは、research-neo4j の補強を先に行ってから着手する**
   - 主要企業の Source/Fact 件数だけでは十分とみなさない
   - 実 URL、日付、publisher、構造化指標の4点が揃ってからレポート化する

2. **このテーマではインドネシア語のリサーチは行わない**
   - 検索言語は英語中心とし、一次ソースは英語版 IR / investor relations / official release / regulator の英語ページを優先する
   - 日本語や英語で十分に届かない論点があっても、今回のレポート作成方針ではインドネシア語検索を追加しない

## アクションアイテム

- [ ] 主要事業者 (`Telkom Indonesia`, `Telkomsel`, `Indosat Ooredoo Hutchison`, `XLSmart`) の synthetic URL を公式 IR / official URL に差し替える (優先度: 高)
- [ ] `Komdigi` とスペクトラム論点 (`700MHz`, `2.6GHz`, `network sharing`, `foreign ownership`) の dated fact を補強する (優先度: 高)
- [ ] `Mitratel`, `Tower Bersama Infrastructure`, `Sarana Menara Nusantara`, `Protelindo` の比較KPIを構造化し、TowerCo 比較表を作れる状態にする (優先度: 中)

## 次回の議論トピック

- P0/P1 補強後に、インドネシア telecom レポートの章立てをどう切るか
- 事業者別レポートにするか、セクター比較レポートにするか
- note 記事向けにどこまで比較表を図版化するか

## 参考メモ

- 主要検索軸: operator KPIs, regulation, competition, fixed broadband, enterprise/DC, tower economics
- 使用クエリは英語のみで設計する
- Tavily 制限時は WebSearch / Gemini Search / fetch の英語ソースで代替する
