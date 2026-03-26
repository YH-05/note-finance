# 議論メモ: creator-neo4j 収益化障壁の実DB分析

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j を実データで再分析し、AI が SNS 投稿、note 執筆、SNS アカウント運用を通じて収益を上げるうえで、どこが構造的ボトルネックになっているかを整理した。
初回分析時は Docker 未起動でライブ確認できなかったが、その後 creator-neo4j 起動後に実クエリで再評価した。

## 議論のサマリー

creator-neo4j は素材ナレッジグラフとしてはかなり育っており、Fact 944、Tip 805、Story 405、Entity 734、Concept 4,177、Source 1,708 を持つ。
一方で、収益化オペレーションに必要な「投稿結果の学習」「鮮度管理」「運用導線の最適化」は未実装のまま残っていた。

実DBから見えた主要な障壁は以下のとおり。

1. **運用レイヤ不在**
   `Post=0 / Account=0 / Service=0` で、どの素材を使って何を投稿し、その結果どう伸びたかを creator-neo4j に戻せていない。
   現状は revenue-learning graph ではなく material graph に留まる。

2. **Source freshness 欠損**
   Source 1,708件に対して `published_at` 欠損が 1,708件、title 欠損が 185件。
   note.com Source 61件も `published_at` は全欠損。
   新しい運用知見を優先する仕組みがない。

3. **Concept 層の接続密度不足**
   Concept 4,177件のうち `ABOUT` 未接続 2,217件、singleton 1,223件、平均接続数 1.22。
   特に How 層は薄く、EmotionalHook 0.37、CopyFramework 0.53、PersuasionTechnique 0.56 contents/concept だった。
   「刺さる構成」「感情フック」「説得技法」を安定取得しづらい。

4. **Entity の役割付け不足**
   Entity 734件のうち MENTIONS なし 229件、SERVES_AS なし 578件、完全孤立 169件。
   プラットフォームやサービス名はあるが、役割文脈に十分つながっていない。

5. **Story 比率と実戦プラットフォーム知識の不足**
   Story 比率は career 19.6%、beauty-romance 15.7%、spiritual 18.4%、self-development 22.1%。
   note.com Source は 61件あるが、そこから得られているのは Story 30 / Tip 24 / Fact 4 で、定量裏付けは弱い。
   platform mentions も Threads 42、Instagram 19、note.com 12 に留まり、媒体別の勝ち筋学習にはまだ薄い。

## 決定事項

1. **creator-neo4j は現状 material graph と位置づける**
   Fact / Tip / Story / Concept / Entity / Source を使った素材検索には利用するが、
   投稿成果や収益導線の学習基盤と見なしてはいけない。

2. **次の優先投資は enrichment 拡大量ではなく運用学習レイヤ**
   追加収集より先に、Post / Account / Engagement / Conversion と freshness を graph に取り込む設計を優先する。

## アクションアイテム

- [ ] creator-neo4j に Post / Account / Engagement / Conversion レイヤを追加する設計を作成し、投稿結果を graph に還流できるようにする (優先度: 高)
- [ ] Source.published_at の backfill 方針を作成し、特に note.com / Reddit / Web source の freshness を判定できる状態にする (優先度: 高)
- [ ] no_content Concept と SERVES_AS / ABOUT 未接続の圧縮・再接続方針を作成し、How 層の実用密度を上げる (優先度: 高)

## 次回の議論トピック

- Post / Account / Engagement / Conversion を creator-neo4j にどう入れるか
- note.com / Threads / Instagram の成果指標をどの単位で保存するか
- creator-neo4j を material graph から revenue-learning graph に進化させる最短実装順

## 参考情報

- ライブDB主要件数: Concept 4,177 / Source 1,708 / Fact 944 / Tip 805 / Domain 797 / Entity 734 / Story 405
- リレーション主要件数: ABOUT 5,955 / IS_A 4,450 / IN_GENRE 2,154 / FROM_SOURCE 2,042 / MENTIONS 1,175 / SERVES_AS 199
- Concept 未接続: 2,217件、singleton: 1,223件、平均 1.22 contents/concept
- Entity 孤立: fully orphan 169件
- Source 欠損: published_at 1,708件、title 185件
