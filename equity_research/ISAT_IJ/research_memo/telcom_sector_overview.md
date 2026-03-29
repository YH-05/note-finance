---
date created: 2026-03-29 14:03
date modified: 2026-03-29 17:03
---
# テレコムセクター概論

> **用途**: `ISAT-IJ_調査.md` §1「Telcomセクター概況」の詳細参照ドキュメント。
> **データソース**: research-neo4j KG（2026年3月時点）

---

## 1. 市場構造と経済原理

### 1-1. 業界の分類

電気通信事業は提供するサービスのレイヤーによって大きく4つに分類される。

| レイヤー | 事業者タイプ | 例 |
|---|---|---|
| **物理インフラ** | タワー会社・光ファイバー会社 | Mitratel（インドネシア）、American Tower、Crown Castle |
| **通信キャリア** | MNO（移動体）・FNO（固定）・MVNO | Telkomsel、IOH、PLDT、Singtel |
| **プラットフォーム** | SNS・OTT・クラウド | Meta、Google、Microsoft Azure |
| **端末・デバイス** | スマートフォン・IoT機器 | Samsung、Apple、Qualcomm |

テレコムキャリアは「物理インフラ」と「プラットフォーム」の間に挟まれた構造にあり、物理インフラの分離（TowerCo / FiberCo化）とプラットフォームへのアップサイド享受の両方を追求する動きが2022年以降に加速している。

**衛星通信の台頭（NTN: Non-Terrestrial Network）**

Starlink（SpaceX）が既存の地上基地局の補完ではなく競合として機能し始めている。ASEANでの展開状況：
- インドネシア: 2024年5月ライセンス取得。農村・島嶼向け。2025年7月には容量完売
- マレーシア: 2023年7月完全ライセンス
- フィリピン: Globe TelecomがDirect-to-Cell（D2C）契約を締結（2025–2026年）。衛星からLTEテキスト/音声/データを直接提供
- タイ: 完全外資モデルを国家安全保障上の理由で否認
- インドネシア17,000+島嶼、フィリピン7,000+島嶼という地理条件はD2Cの経済合理性を高める [(2025年衛星通信トレンド)](https://www.telecoms.com/satellite/key-non-terrestrial-network-developments-in-2025)

---

### 1-2. コスト構造：固定費優位のビジネスモデル

テレコムの本質的な特徴は**極端な固定費比率の高さ**にある。

| コスト区分 | 内容 | 特性 |
|---|---|---|
| **資本的支出（CapEx）** | 基地局・光ファイバー・スペクトラム | 先行一括投資。償却期間7–20年 |
| **ネットワーク運用コスト（OpEx）** | 電力費・保守・NW管理 | 加入者数とほぼ無関係に発生 |
| **スペクトラムコスト** | オークション落札額・年次免許料 | インドネシアではMNO収益の~11%（政府目標は~5%）[(World Bank PDF)](https://documents1.worldbank.org/curated/en/099121525010013017/pdf/P513006-5a39c38f-b7cb-425f-966b-655852db27e7.pdf) |
| **SG&A** | 代理店手数料・マーケティング | 競争強度に連動。プリペイド市場で特に高い |
| **変動費** | 接続料・ローミング精算 | 収益の5–15%程度 |

**CapEx intensity（CapEx/収益）の国際比較**

| 企業/市場           | CapEx intensity                | 備考                                                                                                                    |
| --------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| TLKM IJ（インドネシア） | 22.8%（FY2024）→ 17–19%目標（2028年） | TLKM30戦略で圧縮                                                                                                           |
| IOH（インドネシア）     | ~22%（FY2024–25）                | 5G展開フェーズで増加余地                                                                                                         |
| AT&T（米国）        | ~17%（FY2025）                   | ファイバー展開で高水準 [(AT&T FY2025)](https://about.att.com/story/2026/4q-earnings-2025.html)                                   |
| ASEAN平均（2026F）  | ~15.9%                         | Maybank予測（CapEx intensity低下傾向） [(Maybank ASEAN Equity Strategy)](https://mkefactsettd.maybank-ke.com/PDFS/506668.pdf) |

---

### 1-3. 規模の経済（Economies of Scale）

サービス開始に必要な大規模設備（基地局・光ファイバー・コアネットワーク）は「固定費」として計上される。加入者1人あたりの平均費用は加入者数が増えるほど逓減する。

**定量的な実証例**

IOH合併（2022年1月）の統計：
- 合併後3年間で累積シナジー$610M（OPEX+CAPEX）達成
- 当初目標$300–400Mに対して$462M/年を実現（50%超過）
- 重複基地局46,000+局を統合（計画より12か月前倒し）
- 重複店舗296店を統合

→ **合併1件で数百億円規模のコスト削減**が実現できる。規模の経済の効果は特にネットワーク資産の重複除去において大きい。

---

### 1-4. 範囲の経済（Economies of Scope）

同一のネットワーク設備から複数サービスを提供することで、各サービスの単位コストが下がる。FMC（Fixed-Mobile Convergence）戦略はその典型的な実装形態。

**Telkomsel FMC（IndiHome統合）の成果**

- IndiHome（固定BB）を2023年7月にTelkomselに移管
- FMC（固定＋モバイル両方を利用する顧客）比率: 37%（2023年7月）→ **57%（2024年末）**
- TelkomselのSKU数: 6,000→400に削減
- CapEx/line 30%削減、O&M cost/line 15%削減

FMC顧客は解約率（チャーン）が低く、ARPUも高い傾向がある。AT&Tの事例では「ファイバー世帯の42%がAT&Tワイヤレスも選択（収束率42%）」と報告されている。[(AT&T FY2025)](https://about.att.com/story/2026/4q-earnings-2025.html)

---

### 1-5. 自然独占と市場集中

通信事業の経済的特性（高固定費・ネットワーク効果・スペクトラム希少性）が「3プレイヤー寡占」という均衡状態を生み出す。

**世界の主要市場の集中度**

| 市場 | プレイヤー数 | 上位3社シェア | 備考 |
|---|---|---|---|
| 米国 | 3（実質） | 93.8%（モバイル加入者） | Verizon/AT&T/T-Mobile |
| シンガポール | 3+1 | ~93%（Singtel/StarHub/M1） | Simba（格安）が第4のプレイヤー |
| インドネシア | 3 | 90%超（Telkomsel/IOH/XLSmart） | XL-Smartfren統合2025年4月 |
| タイ | 3 | 90%超（AIS/True/DTAC統合後） | True-DTAC統合2023年3月 |
| フィリピン | 2→3 | 85%（Globe/PLDT-Smart） | DITOが第3プレイヤーとして参入中 |
| ベトナム | 3（国営） | ~92%（Viettel/VNPT/MobiFone） | 全社100%国有 |

**ASEAN統合の波（2022–2024年）**

すべての主要ASEAN市場がほぼ同時期に4→3プレイヤーへ収束した：

| 統合 | 完了 | 推定規模 |
|---|---|---|
| Indonesia: Indosat＋Hutchison 3 | 2022年1月 | ~$6B |
| Malaysia: Celcom＋Digi | 2022年11月 | — |
| Thailand: True＋DTAC | 2023年3月 | — |
| Indonesia: XL Axiata＋Smartfren | 2025年4月 | — |

統合後の市場健全性については議論がある。True-DTAC統合から1,000日後の分析では「競争なし、規制執行なし」という批判も出ている [(Yozzo.com)](https://www.yozzo.com/mvno-news/1000-days-true-dtac-merger-no-competition-no-enforcement/)。インドネシアではプリペイドSIM価格フロア設定（2025年10月）による「官製ARPU修復」が導入された。

---

### 1-6. ネットワーク効果（Demand-side Economies of Scale）

**直接ネットワーク効果**: 同じネットワークの加入者数が増えるほど、各加入者にとっての効用が高まる（つながる相手が増える）。

**間接ネットワーク効果**: 加入者規模が大きいほど、補完的サービス（アプリ、IoT、企業向け専用線）の供給者が参入しやすくなり、さらに加入者を引き付ける。

**フィンテックへの波及**: ASEANのモバイルウォレットはまさにこのネットワーク効果で成長した。東南アジアモバイル決済市場は$215B（2024年、CAGR 25%/2019–2024年）に達している。

テレコム企業が直接関与する主要ウォレット：

| 国 | ウォレット | 運営 | 規模 |
|---|---|---|---|
| フィリピン | GCash | Globe Telecom系 | 9,400万ウォレット |
| タイ | TrueMoney | True Corporation系 | 2,000万+ユーザー |
| ベトナム | ViettelPay | Viettel系 | Viettelが直接運営 |
| インドネシア | LinkAja（テレコム系）/GoPay/Dana/OVO | Telkomsel等 | QRIS取引27億件/2024年（+66% YoY） |

インドネシアは人口の49%が未銀行口座（unbanked）であり、モバイルウォレットが事実上の金融インフラとなっている。

---

## 2. 規制環境

### 2-1. 規制の目的と3つの手段

テレコム規制は自然独占が消費者に害を与えないよう3つの手段で介入する：

1. **料金規制**: 独占利潤を抑制するための価格上限（プライスキャップ）や最低価格フロア設定
2. **参入規制**: スペクトラム免許・外資規制で参入者を制限し、投資インセンティブを維持
3. **構造規制**: ネットワーク共有義務・卸売アクセス義務でインフラの独占的利用を制限

**価格フロアと価格上限の二重規制**

通常、規制は価格上限（独占価格の抑制）を設定するが、インドネシアでは2025年に逆の「**価格フロア（最低価格）**」が設定された。プリペイドSIMスターターパックの下限をIDR 35,000に設定し、過度な価格競争（→データ価格の下落→キャリアの設備投資能力の低下）を抑制した。

---

### 2-2. スペクトラム管理：テレコム規制の核心

#### なぜスペクトラムは国家が管理するのか

スペクトラム（電波）は**非枯渇性だが有限の天然資源**であり、あらゆる国と宇宙空間に存在する。同一周波数帯を複数の発信局が使用すると**有害干渉（harmful interference）が発生するため、排他的利用権の付与が不可欠となる。ITUは「人類共通の資源であり、条約レベルの合意による合理的管理を必要とする」と定義している [(ITU-R Backgrounder)](https://www.itu.int/en/mediacentre/backgrounders/Pages/itu-r-managing-the-radio-frequency-spectrum-for-the-world.aspx)。

**主権と国際協調の二層構造**

- **国家主権**: ITU憲章第1条は「各国がその通信を規制する主権的権利」を承認。スペクトラムは各国の**公共財（State's public domain）に属し、国内法で管理 [(ITU Digital Regulation Platform)](https://digitalregulation.org/spectrum-management-guidance-on-the-regulatory-framework-for-national-spectrum-management/)
- **国際条約**: 干渉は国境を超えるため、**ITU無線通信規則（Radio Regulations: RR）が拘束力ある国際条約として周波数配分・サービス間共用ルールを規定。最新改訂は2024年 [(ITU Press Release)](https://www.itu.int/en/mediacentre/Pages/PR-2024-07-04-ITU-Radio-Regulations.aspx)

**管理の3階層**

| 階層     | 機関                          | 機能                                      |
| ------ | --------------------------- | --------------------------------------- |
| **国際** | ITU-R（WRC: 世界無線通信会議、4年ごと改訂） | 周波数帯のサービス配分（固定/移動/衛星等）、国際干渉回避、国際周波数表の維持 |
| **国家** | 各国規制当局（下記参照）                | 国内の免許付与・オークション実施・利用監視・違反取締              |
| **運用** | MNO・放送局・衛星事業者               | 免許条件下でのサービス提供・干渉モニタリング                  |

#### 周波数帯の特性

| 帯域 | 伝播特性 | 用途 |
|---|---|---|
| 700–900MHz（Sub-1GHz） | 遠距離・壁透過性高 | 農村カバレッジ・屋内 |
| 1800–2100MHz（中帯域） | バランス型 | 主力4G帯域 |
| 2300–2600MHz | データ容量重視 | 都市部4G/5G |
| 3500MHz（Cバンド） | 5Gの国際標準主力帯 | 高速・大容量5G |
| mmWave（26/28GHz） | 超高速・超短距離 | 5G超高密度エリア |

#### オークション方式の比較

スペクトラムの配分方式は国・帯域により異なる [(Specure: SMRA vs CCA)](https://specure.com/spectrum-auction-formats-smra-vs-cca/)。

| 方式 | 仕組み | 長所 | 短所 | 採用例 |
|---|---|---|---|---|
| **SMRA** | 複数ロットを同時並行で繰り返し入札 | シンプル。1990年代から実績豊富 | 望むパッケージの一部しか取れない「暴露問題」 | 米国FCC（歴史的） |
| **CCA** | クロックラウンド→補充ラウンド→配分決定 | パッケージ入札で「一部だけ獲得」リスクなし | 複雑。落札結果が終了まで不明 | 英国Ofcom、豪州、カナダ |
| **CFP（比較審査）** | 規制当局が事業計画を評価して免許付与 | 政策目標（カバレッジ・卸売義務等）を直接反映可 | 不透明、政治的影響を受けやすい | シンガポールIMDA（5G初期割当） |

#### スペクトラムコストの国際動向

グローバルスペクトラムオークション収入は2025年に$7.1B （前年比減少） [(GSA)](https://telecomlead.com/5g/gsa-spectrum-auctions-revenue-touches-7-1-bn-in-2025-124053)。世界累計でスペクトラムコストはオペレーター収益の**7%に達し、過去10年で63%増加。1MHzあたりの収益支持力は10年前の**1/3**に低下している [(GSMA Global Spectrum Pricing)](https://www.gsma.com/connectivity-for-good/spectrum/wp-content/uploads/2025/05/Global-Spectrum-Pricing-v2.pdf)。

| 市場                      | スペクトラムコスト/収益            | 備考                                                                                                                                                                               |
| ----------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **インドネシア（IOH/XLSmart）** | **12–13%**              | APAC中央値8.7%を大幅超過。World Bank「G20最悪」 [(World Bank PDF)](https://documents1.worldbank.org/curated/en/099121525010013017/pdf/P513006-5a39c38f-b7cb-425f-966b-655852db27e7.pdf)       |
| インドネシア（TLKM）            | ~5%                     | 既存保有帯域の優位性                                                                                                                                                                       |
| タイ                      | 高（$1.3B+ 2025年6月オークション） | AIS/Trueが主要帯域の大半を落札 [(Telecom Review Asia)](https://www.telecomreviewasia.com/news/featured-articles/14650-the-battle-for-bandwidth-inside-the-asia-pacifics-spectrum-auctions/) |
| シンガポール                  | 低                       | 投資促進型のCFP方式で低コスト                                                                                                                                                                 |
| グローバル平均                 | 7%                      | 10年で63%増                                                                                                                                                                         |
※スペクトラムコスト/収益：スペクトラムの年間使用料（annual spectrum fees）/オペレーター収益。分子はオークション落札額の年次償却分＋年間免許更新料（BHP: Base Spectrum Feeなど）。分母はMNOの年間収益（revenue）
GSMAはインドネシアの高スペクトラム価格が2024–2030年に**$14B（IDR 216T）のGDP損失**をもたらすと警告 [(GSMA)](https://developingtelecoms.com/telecom-business/telecom-regulation/15775-gsma-warns-indonesia-its-5g-spectrum-prices-are-too-high.html)。
- 参考：[GSMA Global Spectrum Pricing](https://www.gsma.com/connectivity-for-good/spectrum/wp-content/uploads/2025/05/Global-Spectrum-Pricing-v2.pdf)

#### なぜTLKM ~5% vs IOH/XLSmart 12–13%の格差が生じるのか

インドネシアの「業界平均12.2%」はIOH/XLSmart寄りの数値であり、TLKMの~5%と大きく乖離する。この格差は単一要因ではなく、5つの構造的要因の複合で説明される [(GSMA 2023)](https://www.gsma.com/connectivity-for-good/spectrum/wp-content/uploads/2023/11/GSMA_Sustainable-spectrum-pricing-to-boost-Indonesias-digital-economy.pdf)。

**要因①: 収益規模の分母効果（最大要因）**

BHP（Biaya Hak Penggunaan Frekuensi = スペクトラム使用料）は帯域幅に比例する固定費的な性格を持つ。

| オペレーター | 連結収益（FY2024） | スペクトラムコスト/収益 | BHP推定絶対額 |
|---|---|---|---|
| TLKM | IDR 150.0T | ~5% | ~IDR 7.5T |
| IOH | IDR 55.9T | 12–13% | ~IDR 6.7–7.3T |
| XLSmart | IDR 42.5T | 12–13% | ~IDR 5.1–5.5T |

→ **BHP絶対額はTLKMとIOHでほぼ同水準（IDR 7T前後）**だが、TLKMの収益がIOHの**2.7倍**あるため、比率は自動的に1/2.7に縮小する。これが格差の最大の説明因子。

**要因②: 歴史的な行政割当（オークション以前の取得）**

Telkomselは1995年にインドネシア初のGSMオペレーターとして900MHz帯の免許を取得。当時はオークション制度が存在せず、**行政割当（beauty contest / direct assignment）で低コストに取得した [(Light Reading)](https://www.lightreading.com/asia/cautious-start-to-5g-in-spectrum-starved-indonesia/d/d-id/770175)。旧Satelindo（現Indosat）も行政割当で参入したが、TelkomselはBUMN子会社**としてより広い帯域を優先的に確保した。

900MHz/1800MHzのコア帯域はオークション以前に取得済みであり、年間BHPは旧基準の低い料率で固定されている。2010年以降の高額オークション帯域（2.1GHz, 2.3GHz等）はTelkomselの保有帯域全体の一部に過ぎず、加重平均コストは低く留まる。

**要因③: BHP料率の時代的差異**

BHP IPFRの計算は「帯域幅 × 周波数帯係数 × 経済パラメータ × 全国人口」で決まる [(Universitas Indonesia研究)](https://eng.ui.ac.id/en/ftui-doctor-develops-new-formula-for-fee-for-use-of-rights-bhp-for-2628-ghz-5g-mm-wave-private-network-frequency-in-indonesian-industrial-estates/)。2010年以降BHPは**5倍に増加**した [(Kompas.id)](https://www.kompas.id/baca/english/2023/11/09/en-biaya-spektrum-frekuensi-meningkat-lima-kali-sejak-2010) が、新料率の適用は主に新規取得帯域が対象。1990年代取得のコア帯域に旧料率が残存している可能性がある（Komdigiの公式料率一覧は一般未公開）。

参考: Komdigi管轄のPNBP（非税国家歳入）は年間約IDR 22–24Tであり、スペクトラム使用料がその中核を構成する。政府にとってBHPは重要な財源であり、大幅引き下げのインセンティブは限定的。

**要因④: BUMN構造による暗黙の優位**

TLKM（Telkomsel親会社）は政府が52.1%保有するBUMN。スペクトラム料金の設定者（Komdigi）と最大の支払者の大株主（政府）が**同一の経済主体**であるため、TLKMに過度に不利な料金設定にはなりにくい構造的インセンティブが存在する。

World Bankは「インドネシアの元来の電気通信法・規制は国有企業に独占的に事業を委ねる非常に独占的・反競争的なモデルだった。1999年電気通信法で自由化が始まったが、インカンベント優位は残存している」と指摘 [(ICLG 2026)](https://iclg.com/practice-areas/telecoms-media-and-internet-laws-and-regulations/indonesia)。既存免許保有者は新規選定プロセスではなく「評価（evaluation）」でスペクトラムを取得できる制度も残る [(Lexology)](https://www.lexology.com/library/detail.aspx?g=feb265f3-8cfc-479b-bd78-37ce3ad0a46c)。

**要因⑤: 帯域ポートフォリオの質と量の差**

| オペレーター | 合計 | 900MHz | 1800MHz | 2100MHz | 2300MHz TDD | その他 |
|---|---|---|---|---|---|---|
| Telkomsel | **~165MHz** | 15 | 45 | 40 | **30** | 800MHz 7.5等 |
| IOH | **~135MHz** | 25 | 60 | 50 | **なし** | — |

Telkomselは保有帯域が広い上に、**2.3GHz TDD 30MHzを独占保有**しており5G初期展開で先行。IOHは2.3GHz帯を持たず、5G展開に追加のスペクトラム取得（2.6GHz等）が必要 → このオークション取得コストがさらに比率を押し上げる。

**IOH側のコスト格差緩和策**

| 施策 | 内容 | 効果 |
|---|---|---|
| IOH合併シナジー | 帯域統合で135MHzに拡大（+40%）。$610M累積シナジー | MHz当たり効率向上 [(Telecoms.com)](https://www.telecoms.com/digital-transformation/-stronger-together-inside-the-successful-merger-of-indosat-ooredoo-hutchison) |
| FibreCo売却益 | 手取り~$700M（IDR 11.2T）を5Gスペクトラム取得に充当 | オークション費用（ベースケースIDR 3.4T/社）の自然ヘッジ |
| アセットライト化 | FibreCo分離後は共有インフラ活用（長期リース） | CapEx intensity圧縮 [(Developing Telecoms)](https://developingtelecoms.com/telecom-business/operator-news/19540-indosat-to-spin-off-fibre-assets-into-new-indonesia-infrastructure-jv.html) |
| AI TechCo収益拡大 | デジタル収益がコアテレコムの25%超（FY2025） | 収益分母の拡大→比率の自然低下 |

**ASEAN国際比較（World Bank 2025年12月）** [(Kompas.id)](https://www.kompas.id/artikel/en-sejumlah-catatan-bank-dunia-untuk-capaian-infrastruktur-digital-indonesia)

| 国 | スペクトラムコスト/収益 | 対インドネシア比 |
|---|---|---|
| **インドネシア** | **11.4%** | — |
| タイ | 9.0% | 0.79x |
| マレーシア | 3.6% | 0.32x |
| フィリピン | 1.9% | 0.17x |

インドネシアの負担は**フィリピンの6倍、マレーシアの3倍**。G20中でモバイル向けスペクトラム配分量が最少。

---

### 2-3. ASEAN 4カ国スペクトラム規制詳細

#### インドネシア（Komdigi / BRTI）

- **規制当局**: **Komdigi**（Kementerian Komunikasi dan Digital、旧Kominfo）＋ **BRTI**（電気通信規制委員会）
- **根拠法**: Telecommunications Law No. 36/1999
- **外資上限**: 49%

**帯域別配分状況**

| 帯域 | 配分 | 備考 |
|---|---|---|
| 900MHz | Telkomsel 15MHz / IOH 25MHz / XLSmart 37MHz | XLSmart 7.5MHz返却義務（2026年12月） [(Bisnis.com)](https://teknologi.bisnis.com/read/20250418/101/1870139/xlsmart-pastikan-kembalikan-frekuensi-900-mhz-pada-desember-2026) |
| 1800MHz | Telkomsel 45MHz / IOH 60MHz | 4G主力 |
| 2100MHz | Telkomsel 40MHz / IOH 50MHz | — |
| 2300MHz TDD | Telkomsel 30MHz | 5G初期展開（2021年Jakarta） |
| 1.4GHz TDD | 2025年10月オークション完了。80MHz、3社落札 | 10年免許。第三者オープンアクセス義務 |
| **700MHz** | **2026年Q2オークション予定**（2x45MHz = 112MHz） | 農村カバレッジ拡大。Komdigi DGが2026年1月26日に国会Commission Iで確認 [(700MHz記事)](https://www.qoo10.co.id/en/gadget/66711/700-mhz-spectrum-auction-set-for-2026-to-boost-5g-coverage-and-mobile-broadband-speeds/) |
| **2.6GHz TDD** | **2026年Q2オークション予定**（190MHz） | 5G容量帯域 [(Jakarta Globe)](https://jakartaglobe.id/tech/indonesia-to-auction-26-ghz-spectrum-for-5g-network-expansion) |
| 3.5GHz | **未開放**: 衛星事業者の長期リース占有。2028年以降見込み | 5G国際標準主力帯が使えないASEAN唯一の大規模市場 |

5Gカバレッジは居住エリアの**6.33%**（2025年末、RPJMN目標4.4%は超過）。2026年目標8.5%、2029年までに平均速度100Mbps目標（現状63.51Mbps） [(OpenSignal)](https://www.opensignal.com/2025/10/10/asean-digital-infrastructure-the-role-of-spectrum/dt)

#### ベトナム（MIC: 情報通信省）

- **規制当局**: **MIC**（Bộ Thông tin và Truyền thông、情報通信省）
- **根拠法**: Law on Radio Frequencies（2009年、2023年改正）
- **外資上限**: 49%（実質0%: 全MNO国有）

**5Gオークション実績（ベトナム初、2024年〜）**

| 帯域 | 落札者 | 落札額 | 免許条件 |
|---|---|---|---|
| 2500–2600MHz（100MHz） | **Viettel**（2024年3月） | VND 7.533T（~$296M） | 15年免許。12か月以内に商用5G開始。2年以内に3,000 BTS展開 [(Total Telecom)](https://totaltele.com/vietnam-finally-completes-long-awaited-5g-spectrum-auctions/) |
| 700MHz B2-B2′ | **Viettel**（2025年5月） | VND 1.95T（~$75M） | 2年以内に2,000 BTS（うち650局は海事・島嶼向け） [(RCR Wireless)](https://www.rcrwireless.com/20250523/5g/viettel-700-mhz-5g) |
| 700MHz B1-B1′, B3-B3′ | **再オークション中** | — | 初回不成立のため再入札。農村・僻地カバレッジ帯域 [(MST.gov.vn)](https://english.mst.gov.vn/vietnam-reopens-bidding-for-two-prime-4g-5g-spectrum-blocks-197250724094744076.htm) |

全MNO国有のため「オークション」は実質的に国庫への資金移転だが、形式的に競争入札を採用。設備費補助15%（20,000局展開条件）の仕組みでスペクトラム収入を再投資に循環。Viettelは5G商用開始（2025年3月）後、12.9M加入者・30,000 BTS展開済み。

#### マレーシア（MCMC + DNB）

- **規制当局**: **MCMC**（Malaysian Communications and Multimedia Commission）
- **根拠法**: Communications and Multimedia Act 1998（CMA）
- **外資上限**: 49%

**5Gモデルの変遷（政策転換の事例）**

| 時期 | モデル | 内容 |
|---|---|---|
| 2021年 | **Single Wholesale Network（SWN）** | 政府設立のDNB（Digital Nasional Berhad）が3.5GHz 200MHzを独占。エリクソン単独ベンダー |
| 2024年12月 | **Dual Network（DN）移行** | Ministerial Direction No.4 of 2024でSWN撤回。U Mobileを第2 NW事業者に選定 [(CMS Expert Guide)](https://cms.law/en/int/expert-guides/cms-expert-guide-to-5g-regulation-and-law/malaysia) |
| 2025年3月 | U Mobile参入 | Award Letter発行。Huawei/ZTEと5G-Advanced展開。2026年H2に人口カバレッジ80%目標 |
| 2025年10月 | DNBスペクトラム追加 | 3.3–3.4GHz 100MHzを追加配分（Ministerial Direction No.7）。DNB合計200MHzに復帰 [(The Edge)](https://theedgemalaysia.com/node/785373) |
| 2026年3月 | **テレコム各社がDNB完全買収** | 政府のexit完了。SWN→DN→民間移管という3段階を完走 [(RCR Wireless)](https://www.rcrwireless.com/20260309/5g/malaysian-telcos-dnb) |

DNBモデルの教訓: スペクトラム集中によるMNO投資インセンティブ低下と品質劣化（2025年に5Gダウンロード速度が低下） [(TechWire Asia)](https://techwireasia.com/2026/01/malaysia-5g-speeds-drop-dual-network-2025/)

#### シンガポール（IMDA）

- **規制当局**: **IMDA**（Infocomm Media Development Authority）
- **根拠法**: Telecommunications Act (Cap. 323)
- **スペクトラム管理マニュアル**: [IMDA Spectrum Management Handbook](https://www.imda.gov.sg/-/media/imda/files/regulation-licensing-and-consultations/frameworks-and-policies/spectrum-management-and-coordination/spectrummgmthb.pdf)
- **外資上限**: 制限なし（IMDA承認要）

**5Gスペクトラム配分**

| 帯域 | 方式 | 割当先 | 備考 |
|---|---|---|---|
| 3.5GHz（2x100MHz） | **CFP（比較審査）** | Singtel + StarHub/M1 JVCo（2019年決定） | 2つの全国5G NW。2025年末までに全国屋外カバレッジ義務。卸売アクセス義務あり [(IMDA 5G CFP)](https://www.imda.gov.sg/regulations-and-licensing-listing/spectrum-management/spectrum-rights-auctions-and-assignment/5g-cfp-2020) |
| 2.1GHz | **オークション** | Singtel / StarHub-M1 / SIMBA（2022年） | 5G追加容量 [(IMDA 2.1GHz)](https://www.imda.gov.sg/regulations-and-licensing-listing/spectrum-management/spectrum-rights-auctions-and-assignment/auction-of-2-1-ghz-spectrum-rights-2022-for-5g) |
| mmWave（26/28GHz） | **割当** | 全MNO | ローカル5Gホットスポット |

シンガポールは5G初期割当でオークションではなく**CFP（比較審査）**を採用した点が特異。収入最大化より政策目標（カバレッジ・卸売義務・技術革新計画）を優先する「規制主導型」アプローチ。5G SA普及率48.3%（2024年末、ASEAN最高）、2G/3G完全停波済み [(CMS Expert Guide)](https://cms.law/en/int/expert-guides/cms-expert-guide-to-5g-regulation-and-law/singapore)

---

### 2-4. ASEAN 4カ国スペクトラム規制比較サマリー

| 項目 | インドネシア | ベトナム | マレーシア | シンガポール |
|---|---|---|---|---|
| **規制当局** | Komdigi / BRTI | MIC | MCMC | IMDA |
| **5G主要帯域** | 2.3GHz（現行）、700/2.6GHz（予定） | 2.5–2.6GHz、700MHz | 3.5GHz（DNB+U Mobile） | 3.5GHz（CFP割当） |
| **3.5GHz利用** | **不可**（衛星占有、~2028年） | **割当済**（2024年） | **割当済**（2021年） | **割当済**（2020年） |
| **配分方式** | オークション | オークション（初: 2024年） | 政府卸売→二重NW→民間移管 | CFP＋オークション |
| **コスト/収益** | **12–13%（最高）** | 低〜中（国有間移転） | 中（政府一元管理） | 低（CFP方式） |
| **外資上限** | 49% | 49%（実質0%: 全社国有） | 49% | 制限なし |
| **5Gカバレッジ** | 6.33%（2025年末） | 急速拡大中 | DN移行中 | **ほぼ全国**（SA 48.3%） |
| **最大課題** | 高コスト＋3.5GHz不在 | 再オークション不成立帯域 | SWN→DN移行混乱 | 成熟市場でのARPU圧力 |

**補足: フィリピン外資規制の自由化**

2022年、フィリピンはPublic Service Act（Republic Act 11659）でテレコムを「公益事業」から「公共サービス」に再分類し、**外資100%保有を解禁**した。ASEAN史上最大の外資自由化であるが、「重要インフラ」指定の場合は安全保障審査が残る [(Global Compliance News)](https://www.globalcompliancenews.com/2022/04/18/philippines-amendment-allowing-full-foreign-ownership-of-telcos-signed-by-president-rodrigo-duterte010422/)

---

### 2-5. 外資規制（詳細）

| 国 | 外資上限 | 主要事例 |
|---|---|---|
| インドネシア | 49% | Ooredoo（カタール）・CK Hutchison（香港）がこの枠組みで参入 |
| フィリピン | **100%可能**（2022年改正、旧40%） | Republic Act 11659で自由化。Singtelが47%のGlobe株を保有 |
| ベトナム | 49%（実質0%：全社国有） | 外資MNOは事実上不可能 |
| シンガポール | 制限なし（IMDA承認要） | Temasek（Singtel）、KKR（M1）等が自由に参入 |
| タイ | 49%（電気通信事業法） | AIS（Singtel 23%）、True（CpAll/Charoen Pokphand） |

---

## 3. 収益構造の変遷

### 3-1. 音声 → データ → デジタルサービスへの移行

世界のテレコム収益構造は過去20年で根本的に変化した：

```
1990年代: 音声通話（国際電話・ローミングが主収益源）
2000年代: SMS・データ通信の台頭
2010年代: スマートフォン普及でデータが主力 → 音声収益の崩壊
2020年代: データ収益の成熟 → デジタルサービス（DC/クラウド/フィンテック/AI）へ
```

IOHの収益構造変化がこれを端的に示している：
- 音声収益: FY2025 -26.4% YoY（ほぼ消滅）
- データ収益: モバイルの99%を占める
- デジタルサービス: コアテレコムの25%超に到達（2025年）

---

### 3-2. ARPU国際比較と「ARPU/GDP比」

ARPUの絶対値だけでは国際比較に意味がない。購買力を調整した「ARPU/GDP比」が重要な指標となる。

| 市場 | ARPU（USD/月） | GDP/capita（USD） | ARPU/GDP比 |
|---|---|---|---|
| シンガポール | 17.5 | 90,674 | 0.23%（最低） |
| 米国 | ~50–60 | 80,000+ | ~0.75% |
| インドネシア | ~2.7（IOH4Q25: 44,000IDR） | 4,925 | **0.59–0.68%（ASEANで最低水準）** |
| フィリピン | 2.5 | 3,985 | 0.75% |
| ベトナム | 2.8 | 4,717 | 0.71% |

インドネシアのARPU/GDP比が低いことは「ARPUの上昇余地が大きい」ことを示唆するが、同時に「消費者の価格感応度が高い」ことも意味する。2025年のスターターパック価格フロア設定がどこまでARPU上昇を持続できるかが投資判断の核心。

---

### 3-3. CapEx循環：テレコムの宿命

テレコムは技術世代（2G→3G→4G→5G）ごとに大規模CapExを繰り返す宿命がある。

**米国の事例（参考）**：
- Verizon+AT&T+T-Mobile: 3社合計で年間$60–70B超のCapEx
- AT&Tは向こう5年で$250B投資コミットを発表 [(AT&T FY2025)](https://about.att.com/story/2026/4q-earnings-2025.html)
- T-Mobile: 高速・高品質5GでシェアをVerizonから奪取。2024–2025年で加入者純増首位

**ASEAN（Maybank予測、2026F）**:
- ASEANテレコム平均: 収益+4%、EBITDA+6%、CapEx intensity低下（~15.9%）
- FCF生成は配当コミットの1.8倍 [(Maybank ASEAN Equity Strategy)](https://mkefactsettd.maybank-ke.com/PDFS/506668.pdf)

---

## 4. インフラ分離トレンド（TowerCo / FiberCo化）

### 4-1. なぜインフラを切り離すのか

テレコムのバランスシートには「資産重い・収益安定・成長低い」インフラ資産（タワー・光ファイバー）が混在している。これを分離することで：

1. **テレコム本体のROIC向上**: 低リターン資産を切り離し、残存ビジネスの収益性指標が改善
2. **インフラの独立価値顕在化**: インフラはキャリアより低いWACCで評価されるため、高いEV/EBITDAで売却可能
3. **資本再配分**: 売却益をデジタル事業（AI/クラウド/5G）に再投入

**ASEAN主要インフラ分離案件**

| 案件 | 規模 | ステータス |
|---|---|---|
| IOH FibreCo（86,000km光ファイバー） | EV IDR 14.6T（~$870–940M） | 2025年12月Investment Agreement。2026年Q2–Q3着金予定 |
| TLKM Infranexia（TIF） | 推定IDR 100–150T（~$10B） | Phase 1完了（2025年Q4）、Phase 2は2026年H2 |
| Mitratel（タワー） | 上場済（IDX）、TLKM 60%保有 | 既存上場会社 |
| PLDT タワー資産 | 参考：PLDT資産売却検討中 | — |
| American Tower / Crown Castle（米国） | 米国最大タワーREIT | CrownはSmall Cell部門$8.5Bで売却（Zayo+EQT） |

インフラ分離は「テレコム企業のバランスシート軽量化戦略」であり、同時に「インフラへの機関投資家・インフラファンドの参入門戸」でもある。

---

## 5. デジタルサービスへの展開

### 5-1. データセンター・クラウド

**東南アジアDC市場**

東南アジアDC市場は$30.47B（2030年、CAGR 14.24%）に達する見込み。現在542施設、3,366MW総容量 [(ASEAN Investment Report 2025)](https://asean.org/wp-content/uploads/2025/10/AIR2025_rev17-Okt.pdf)。

ハイパースケーラーの投資コミット（累計）：
- Microsoft: インドネシア$1.7B（AI/クラウド）＋マレーシア$2.2B
- AWS: シンガポール$9B（2024–2028）＋タイ初クラウドリージョン（2025年1月）
- Google: シンガポール累計$5B＋マレーシア$2B
- Oracle: マレーシア$6.5B
- Amazon: マレーシア$6.2B

マレーシアのジョホール州とインドネシアのBatamが「Tier-2 DCハブ」として急浮上。シンガポールは2019年のモラトリアム（2022年一部解除）で容量制限があり、隣接地域への溢れ出しが発生している。

**テレコム企業のDC収益の現実**

ハイパースケーラーの直接DC投資増加により、テレコム系DC（NeutraDC、TLKM等）は価格競争に直面：
- TLKM NeutraDC: 3Q25に-6.6% YoY（ハイパースケーラーの直接投資との競合）
- PLDT DC: ハイパースケーラーとの協業に軸足

「土管」から「プラットフォーム」への転換は容易ではなく、ハイパースケーラーとの競合vs協業の戦略選択が問われている。

---

### 5-2. AI・GPUaaS：新たな差別化軸

AIはテレコムの事業モデルを二方向で変革する：

**ネットワーク内部へのAI適用（AIによるネットワーク最適化）**

- AIS（タイ）: FutureNet Asia「Network AI Award 2025」受賞。5G+AIで予測メンテナンス・リアルタイムRF最適化・エネルギー効率化を実現。AIによる効率化でAISは2025年に配当+11%を支払えると試算 [(Nokia AI pivot記事)](https://techblog.comsoc.org/2025/11/19/nokia-in-major-pivot-from-traditional-telecom-to-ai-cloud-infrastructure-data-center-networking-and-6g/)
- NokiaはAI・クラウドインフラ・DCネットワーキング・6Gへの大規模ピボットを発表
- 6GはネイティブなアーキテクチャにAIを統合（外部プラグインではなく制御ループとして）

**AI事業（GPUaaS / AI Platformとしての外販）**

IOH（インドネシア）は「AI Native TechCo」として：
- GPU Merdeka: H100+GB200によるGPUaaSを長期5–7年契約で提供
- Sahabat-AI: 70BパラメータLLM（GoToと共同）、5言語対応
- NVIDIAとの戦略的パートナーシップ（NCP認定、Blackwell GPU導入）

Jio（インド）はAMD・Cisco・Nokiaと「Open Telecom AI Platform」を構築中 [(ComputerWeekly)](https://www.computerweekly.com/news/366620092/Jio-AMD-Cisco-and-Nokia-to-build-telecom-AI-platform)

---

## 6. グローバル主要テレコム比較

### 6-1. ASEAN上位テレコム収益ランキング（2024年）

| 順位 | 企業 | 国 | 収益（USD） | 特記事項 |
|---|---|---|---|---|
| 1 | **Singtel** | シンガポール | 11.3B | パンASEAN投資家（AIS/Globe/Telkomsel/Airtel）。FY2025 NP S$2.47B（+9%） |
| 2 | **Telkom Indonesia（TLKM）** | インドネシア | 9.45B | BUMN（国有）。IndiHome FMC。Infranexia分離中 |
| 3 | **Viettel Group** | ベトナム | 7.47B | 海外収益$3.34B（+23.9%）。7市場でシェア1位。FY2025+13.8% |
| 4 | **AIS** | タイ | 6.13B | True-DTAC統合後も独立。5G+AI先進事例 |
| 5 | **True Corporation** | タイ | 5.91B | DTAC統合（2023年3月）完了。Thailand 3プレイヤー体制の一角 |
| 6 | **Axiata Group** | マレーシア | — | Celcom（XL Axiata親会社）、Digi統合（2022年） |
| 〜9位 | **IOH** | インドネシア | ~3.4B（FY2025、IDR 55.9T） | 第2位インドネシアキャリア。AI TechCo化 |

**Singtelのパンアジア投資**：AIS（タイ）23%、Globe Telecom（フィリピン）47%、Telkomsel（インドネシア）35%、Bharti Airtel（インド）29%。820M契約者を20カ国に保有する唯一のASEAN統括テレコム投資家。

---

### 6-2. 国別プロファイル

**シンガポール（成熟市場・世界最先進）**

- 人口600万。モバイル普及率165%、インターネット普及率94.4%
- 産業ARPU: USD 17.5/月（ASEAN最高）。ARPU/GDP 0.23%（世界最低水準）
- 5G SA普及率 48.3%（2024年末、ASEAN・世界でも上位）
- 3+1体制（Singtel 48%/StarHub 25%/M1 20%/Simba）
- 2G/3G完全停波済み。FTTH/B 100%近く
- 成長ドライバー: エンタープライズ（クラウド、サイバーセキュリティ、マネージドサービス）

**フィリピン（成長市場・3プレイヤー移行中）**

- 人口115.8M。市場規模USD 8.0B
- ARPU USD 2.5/月（ARPU/GDP 0.75%）
- Globe（GCash 9,400万）とPLDT-Smartの二強にDITOが参入
- GCash: 国内最大フィンテックエコシステム。Globe ARPUを引き上げる主要ドライバー
- 5G加入者: 3,100万（加入者の23%）。2024年に前年比280%拡大

**ベトナム（急成長・国有3社体制）**

- 人口101M。市場規模USD 7.2B
- ARPU USD 2.8/月、3社とも100%国有
- Viettel FY2025: 収益VND 220.4T（+13.8%）。海外9カ国+$3.34B収益
- 5G: 2025年3月商用開始。Viettelが12.9M加入者、30,000基地局
- 固定BB普及率: 世帯ベース46%（フィリピン33%、インドネシア22%と比較して高い）

---

## 7. 海底ケーブルと国際通信インフラ

AI時代においてデータセンター間の超高速・大容量接続（バックボーン）の重要性が急増している。Omdiaは「2031年にグローバルAIネットワークトラフィックが従来型を超過」と予測。

**Asia United Gateway East（AUG East）**
- 主導: Singtel、サプライヤー: NEC
- 全長8,900km。シンガポール–日本を接続（ブルネイ、インドネシア、マレーシア、フィリピン、韓国、台湾を経由）
- AI帯域需要対応の高本数ファイバーペア設計
- 2029年Q3完成予定

東南アジアには次世代インフラ整備に向けて5年間で$40–60Bの投資が必要（Arthur D. Little推計）。

---

## 8. 投資評価フレームワークへの示唆

### 8-1. テレコムのバリュエーション特性

テレコムは「高FCF・低成長・高配当」の典型的なインフラ型ビジネスであるため、以下の指標でのバリュエーションが一般的：

| 指標 | 特徴 | インドネシア水準 |
|---|---|---|
| **EV/EBITDA** | 最主要。設備償却前利益ベース | IOH 4.8x、TLKM 4.7–5.2x（過去5年平均5.9–6.2xを下回る） |
| **PER** | 減価償却・税務の影響大 | TLKM 13.7–15.8x |
| **FCF Yield** | 実質的な株主への還元余力 | TLKM 配当利回り7.4–7.5%（IDR 3T自社株買いも） |
| **ND/EBITDA** | 負債耐性の尺度 | IOH 0.39x（健全）、TLKM 0.6x（健全） |

### 8-2. テレコム株のリスクファクター体系

| リスク | 内容 | ASEAN固有の側面 |
|---|---|---|
| **ARPU圧力** | 競争激化・規制強化 | プリペイド市場比率が高く価格フロア施策への依存 |
| **CapEx増加** | 技術世代交代（5G、6G） | スペクトラムコストが収益の~11%（インドネシア） |
| **ハイパースケーラー競合** | DC収益が直撃 | TLKM NeutraDC -6.6% YoY |
| **通貨リスク** | 機器輸入コスト（USD建て）が現地通貨安で膨張 | IDR 16,925/USD圏 |
| **規制リスク** | 政府による価格介入・スペクトラム条件変更 | Danantara（インドネシア国有企業改革）の政策不確実性 |
| **OTT代替** | 音声・SMS収益の侵食（LINE、WhatsApp） | 音声収益はIOHでも-26.4% YoY（FY2025） |
| **衛星参入** | Starlink D2Cが農村基盤を侵食 | インドネシア農村・フィリピン島嶼で脅威 |

---

*最終更新: 2026年3月（research-neo4j KGデータ）*
*関連ファイル: `ISAT-IJ_調査.md` §1–§6*
