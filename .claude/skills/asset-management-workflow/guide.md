# 資産形成ワークフロー詳細ガイド

このガイドは、asset-management-workflow スキルの詳細な処理フローとルールを説明します。

## 目次

1. [テーマ一覧と詳細](#テーマ一覧と詳細)
2. [Phase 1: ソース収集の詳細](#phase-1-ソース収集の詳細)
3. [Phase 2: 記事生成の詳細](#phase-2-記事生成の詳細)
4. [Phase 3: コンプライアンスチェックの詳細](#phase-3-コンプライアンスチェックの詳細)
5. [出力ファイル一覧](#出力ファイル一覧)
6. [手動検証チェックリスト](#手動検証チェックリスト)
7. [エラーハンドリング詳細](#エラーハンドリング詳細)

---

## テーマ一覧と詳細

### 1. nisa（NISA制度）

| 項目 | 内容 |
|------|------|
| 日本語名 | NISA制度 |
| キーワード | NISA, つみたて, 非課税, 積立投資 |
| 対象ソース | fsa（金融庁）, morningstar_jp, emaxis |
| 想定トピック例 | 新NISAの活用法、つみたて投資枠と成長投資枠の違い |
| 関連スニペット | `snippets/nisa-disclaimer.md`（NISA制度変更注記） |

### 2. fund_selection（ファンド選び）

| 項目 | 内容 |
|------|------|
| 日本語名 | ファンド選び |
| キーワード | インデックス, ファンド, 信託報酬, eMAXIS, オルカン |
| 対象ソース | emaxis, morningstar_jp |
| 想定トピック例 | インデックスファンドの選び方、信託報酬の比較 |

### 3. asset_allocation（資産配分）

| 項目 | 内容 |
|------|------|
| 日本語名 | 資産配分 |
| キーワード | 資産配分, ポートフォリオ, 分散投資, リバランス |
| 対象ソース | daiwa（大和証券）, morningstar_jp |
| 想定トピック例 | 初心者向けポートフォリオ構築、リバランスのタイミング |

### 4. ideco（iDeCo・企業型DC）

| 項目 | 内容 |
|------|------|
| 日本語名 | iDeCo・企業型DC |
| キーワード | iDeCo, 確定拠出年金, DC, 節税 |
| 対象ソース | fsa（金融庁）, morningstar_jp |
| 想定トピック例 | iDeCoの節税効果、企業型DCとの併用 |

### 5. market_basics（市場の基礎知識）

| 項目 | 内容 |
|------|------|
| 日本語名 | 市場の基礎知識 |
| キーワード | 株式市場, 経済指標, 為替, 債券, 金利 |
| 対象ソース | jpx（東証）, boj（日銀）, daiwa |
| 想定トピック例 | 経済指標の読み方、金利と債券価格の関係 |

### 6. simulation（資産形成シミュレーション）

| 項目 | 内容 |
|------|------|
| 日本語名 | 資産形成シミュレーション |
| キーワード | 複利, 積立, シミュレーション, 老後資金 |
| 対象ソース | fsa（金融庁）, daiwa |
| 想定トピック例 | 複利効果の実例、老後資金のシミュレーション |

---

## Phase 1: ソース収集の詳細

### 処理フロー

```
[1] テーマ設定読み込み
    +-- data/config/asset-management-themes.json
    +-- 6テーマ定義 + content_rules
    |
[2] JP RSSプリセット読み込み
    +-- data/config/rss-presets-jp.json
    +-- 有効なフィードのみ取得（enabled: true）
    |
[3] ソース別RSS記事取得
    +-- FeedReader でローカルデータ読み込み
    +-- URL パターンからソースキーを特定
    |       fsa.go.jp -> fsa
    |       boj.or.jp -> boj
    |       dir.co.jp -> daiwa
    |       jpx.co.jp -> jpx
    |       emaxis -> emaxis
    |       morningstar -> morningstar_jp
    |
[4] テーマ別処理
    +-- 対象ソースから記事を収集
    +-- 日付フィルタリング（--days、デフォルト14日）
    +-- キーワードマッチング（部分文字列一致、大文字小文字不問）
    +-- 上位N件選択（--top-n、公開日時の新しい順）
    |
[5] セッションJSON出力
    +-- .tmp/asset-mgmt-{YYYYMMDD}-{HHMMSS}.json
```

### キーワードマッチングロジック

```python
def match_keywords(item: dict, keywords: list[str]) -> bool:
    """title と summary を結合し、各キーワードの部分文字列一致を確認。

    - 大文字小文字不問（.lower() 比較）
    - いずれか1つでも一致すれば True
    - title / summary が空でも処理可能
    """
    title = (item.get("title") or "").lower()
    summary = (item.get("summary") or "").lower()
    text = f"{title} {summary}"

    return any(keyword.lower() in text for keyword in keywords)
```

### 日付フィルタリング

- デフォルト: 14日（finance-news-workflow の 7日 より長い）
- 理由: JP RSSフィードは更新頻度が低いため、より広い期間をカバー
- `published` フィールドを優先、なければ `fetched_at` をフォールバック

### パラメータの影響

| パラメータ | 影響 |
|-----------|------|
| `--days 7` | 直近1週間のみ。最新ニュースに絞りたい場合 |
| `--days 14` | デフォルト。通常はこれで十分 |
| `--days 30` | ソース不足時に拡大 |
| `--top-n 5` | ソースを厳選したい場合 |
| `--top-n 10` | デフォルト。十分な量のソースを確保 |

---

## Phase 2: 記事生成の詳細

### ソースキュレーション

asset-management-writer がソースに関連度スコア（0-100）を付与します。

| 基準 | 配点 | 説明 |
|------|------|------|
| テーマ適合度 | 30点 | テーマのキーワード・概念との一致度 |
| 情報の信頼性 | 25点 | 公的機関 > 大手金融機関 > メディア > 個人 |
| 鮮度 | 20点 | 直近の情報ほど高スコア |
| 初心者理解度 | 15点 | 初心者が理解しやすい説明があるか |
| 独自性 | 10点 | 他ソースにない独自の視点・データ |

**信頼性ランク**:

| ランク | ソース例 |
|--------|---------|
| A（最高） | 金融庁、日銀、東証、GPIF |
| B（高） | 大和証券、モーニングスター、eMAXIS公式 |
| C（中） | 主要メディア（日経、Bloomberg等） |
| D（参考） | 個人ブログ、SNS（検証必須） |

スコア50以上のソースのみ記事に使用。50未満は `used_in_article: false` として記録のみ。

### note記事の構成ガイドライン

| セクション | 文字数目安 | 内容 |
|-----------|-----------|------|
| はじめに | 200-300字 | 記事で学べること、対象読者の明示 |
| 基礎知識 | 500-800字 | 制度・概念の定義と仕組み、重要性 |
| 実践ガイド | 800-1200字 | ステップバイステップの解説、ポイント、FAQ |
| 注意点・リスク | 300-500字 | よくある間違い、注意すべきリスク |
| まとめ | 200-400字 | 要点整理、次のステップ |

### 必須スニペット

| 位置 | スニペット | ファイル |
|------|-----------|---------|
| 冒頭（タイトル直後） | 免責事項 | `snippets/not-advice.md` |
| 末尾（参考情報の後） | リスク開示 | `snippets/investment-risk.md` |

NISAテーマの場合は追加で `snippets/nisa-disclaimer.md` を含める。

### 専門用語の平易化ルール

初出時に以下のいずれかの方法で説明を追加:

1. **括弧書き**: 「インデックスファンド（市場全体の値動きに連動する投資信託）」
2. **直後の補足文**: 「リバランスを行います。リバランスとは、値動きによってずれた資産配分を元の比率に戻す作業のことです。」
3. **例示**: 「ドルコスト平均法、つまり毎月同じ金額を積み立てる方法」

2回目以降は説明不要。

### 禁止表現リスト

| 禁止表現 | 代替表現 |
|---------|---------|
| 買うべき | 検討に値する、選択肢の一つ |
| 売るべき | リスクを考慮する必要がある |
| おすすめ | 一つの選択肢として |
| 間違いない | 可能性が高いと考えられる |
| 絶対に | 一般的には、多くの場合 |
| 必ず | 〜の傾向がある |
| 必ず儲かる | リターンが期待できる可能性がある |
| 損しない | リスクを抑えられる可能性がある |
| 最強の | 優れた特徴を持つ |
| 一番良い | 多くの投資家に選ばれている |
| 推奨 | 一つの選択肢 |

### X投稿の制約

| 項目 | 制約 |
|------|------|
| 文字数 | 280字以内（厳守） |
| 構成 | フック(1行) + 要点(2-3行) + CTA(1行) + ハッシュタグ |
| 必須ハッシュタグ | `#資産形成` `#投資初心者` |
| 追加ハッシュタグ | テーマ別に1-3個（`#NISA` `#iDeCo` 等） |
| 絵文字 | 控えめに使用（最大2-3個） |

---

## Phase 3: コンプライアンスチェックの詳細

### finance-critic-compliance の評価軸

| チェック項目 | 内容 |
|-------------|------|
| 投資助言規制 | 特定銘柄の売買推奨、「買うべき」「売るべき」等 |
| 免責事項 | 投資リスク警告、投資助言ではない旨、過去実績の免責 |
| 表現の適切性 | 過度に断定的な将来予測、リターンの保証示唆 |
| 情報の公正性 | 特定の立場への偏り、リスク開示、メリット・デメリット提示 |
| データソース | 使用データの出典明記、分析期間の明示 |

### スコアリング

```
score = 100 - (critical x 30 + high x 15 + medium x 5 + low x 2)
```

| ステータス | 条件 | アクション |
|-----------|------|-----------|
| pass | score >= 80, critical = 0 | 修正不要、Phase 4 へ |
| warning | high 問題あり、または必須免責欠落 | reviser で修正 |
| fail | critical 問題が1件以上 | reviser で修正（必須） |

### asset-management-reviser の修正範囲

| 修正対象 | 修正する |
|---------|---------|
| compliance critical | 必ず修正 |
| compliance high | 必ず修正 |
| compliance medium | スキップ |
| compliance low | スキップ |
| structure | スキップ |
| readability | スキップ |
| data_accuracy | スキップ |

修正後のファイルは `revised_draft.md` として出力。元の `first_draft.md` は保持。

---

## 出力ファイル一覧

### セッションファイル（Phase 1）

| ファイル | パス | 説明 |
|---------|------|------|
| セッションJSON | `.tmp/asset-mgmt-{YYYYMMDD}-{HHMMSS}.json` | テーマ別記事データ、統計情報 |

### 記事ファイル（Phase 2-3）

記事ファイルは `/new-finance-article` で作成される記事ディレクトリ内に出力されます。

| ファイル | パス | 説明 |
|---------|------|------|
| note記事初稿 | `{article_dir}/02_draft/first_draft.md` | 2000-4000字 |
| X投稿 | `{article_dir}/02_draft/x_post.md` | 280字以内 |
| キュレーション結果 | `{article_dir}/02_draft/curated_sources.json` | ソース関連度スコア |
| コンプライアンス批評 | `{article_dir}/02_draft/critic.json` | compliance セクション |
| 修正済み記事 | `{article_dir}/02_draft/revised_draft.md` | compliance 修正後（修正時のみ） |

### curated_sources.json フォーマット

```json
{
  "theme": "nisa",
  "curated_at": "2026-03-06T12:00:00+09:00",
  "sources": [
    {
      "url": "https://...",
      "title": "ソースタイトル",
      "publisher": "発行元",
      "reliability_rank": "A",
      "relevance_score": 85,
      "key_findings": ["発見1", "発見2"],
      "used_in_article": true
    }
  ],
  "stats": {
    "total_sources": 10,
    "used_sources": 6,
    "avg_relevance_score": 72
  }
}
```

### critic.json（compliance セクション）フォーマット

```json
{
  "critic_type": "compliance",
  "score": 90,
  "status": "pass",
  "issues": [],
  "required_disclaimers": {
    "investment_risk": { "present": true, "location": "末尾" },
    "not_advice": { "present": true, "location": "冒頭" },
    "past_performance": { "present": true, "required": false },
    "data_source": { "present": true, "location": "末尾" }
  },
  "prohibited_expressions_found": []
}
```

---

## 手動検証チェックリスト

記事公開前に以下を手動で確認してください。

### 記事内容の検証

- [ ] 記事タイトルがテーマに合致している
- [ ] 対象読者（投資初心者）に適切な難易度である
- [ ] 専門用語が初出時に平易化されている
- [ ] 文字数が2000-4000字の範囲内である
- [ ] 論理の流れに飛躍がない

### コンプライアンスの検証

- [ ] 冒頭に免責事項（`snippets/not-advice.md`）が含まれている
- [ ] 末尾にリスク開示（`snippets/investment-risk.md`）が含まれている
- [ ] NISAテーマの場合、NISA制度変更注記（`snippets/nisa-disclaimer.md`）が含まれている
- [ ] 禁止表現が含まれていない
- [ ] 特定銘柄の売買推奨と受け取られる表現がない
- [ ] リターンを保証する表現がない
- [ ] 「絶対」「必ず」「間違いない」等の断定表現がない

### ソースの検証

- [ ] 出典が全て明記されている
- [ ] 出典URLが有効（リンク切れなし）
- [ ] 信頼性ランクC以上のソースが主に使用されている
- [ ] データの引用が正確である

### X投稿の検証

- [ ] 280字以内である
- [ ] `#資産形成` `#投資初心者` ハッシュタグが含まれている
- [ ] 特定銘柄の推奨と受け取られる表現がない
- [ ] note記事へのリンク用プレースホルダー `{URL}` が含まれている

---

## エラーハンドリング詳細

### E001: テーマ設定ファイルエラー

**発生条件**:
- `data/config/asset-management-themes.json` が存在しない
- JSON形式が不正

**対処法**:

```bash
# ファイル存在確認
ls -la data/config/asset-management-themes.json

# JSON検証
python3 -c "import json; json.load(open('data/config/asset-management-themes.json'))"
```

### E002: JP RSSプリセットエラー

**発生条件**:
- `data/config/rss-presets-jp.json` が存在しない
- JSON形式が不正
- 有効なプリセットが0件

**対処法**:

```bash
# ファイル存在確認
ls -la data/config/rss-presets-jp.json

# 有効なプリセット数を確認
python3 -c "
import json
data = json.load(open('data/config/rss-presets-jp.json'))
enabled = [p for p in data.get('presets', []) if p.get('enabled', True)]
print(f'Enabled presets: {len(enabled)}')
"
```

### E003: Python CLI エラー

**発生条件**:
- `prepare_asset_management_session.py` の実行エラー
- session_utils のインポートエラー
- FeedReader の初期化失敗

**対処法**:

```bash
# verbose モードで再実行
uv run python scripts/prepare_asset_management_session.py --verbose --days 14

# session_utils のインポート確認
uv run python -c "from session_utils import filter_by_date, select_top_n"
```

### E004: ソース不足

**発生条件**:
- セッションJSON の articles が全テーマ合計0件
- 関連度スコア50以上のソースが2件未満

**対処法**:

1. `--days` を増やす（14 -> 30）
2. `--no-search false` でWeb検索を有効化
3. テーマのキーワードを見直す（`asset-management-themes.json`）
4. JP RSSプリセットのフィードURLが有効か確認

```bash
# ソースの確認
uv run python scripts/prepare_asset_management_session.py --days 30 --verbose
```

### E005: 記事生成失敗

**発生条件**:
- asset-management-writer がエラーで中断
- 出力ファイルが生成されない

**対処法**:

1. セッションJSON の articles 件数を確認
2. テンプレートファイルの存在確認

```bash
# テンプレート確認
ls -la template/asset_management/02_draft/
```

### E006: コンプライアンス fail

**発生条件**:
- compliance critical 問題が1件以上

**対処法**:

1. asset-management-reviser で自動修正を試みる
2. 修正後も fail が継続する場合は手動修正
3. critic.json の issues を確認し、個別に対応

```bash
# critic.json の確認
cat {article_dir}/02_draft/critic.json | python3 -m json.tool
```

---

## 参考資料

- **SKILL.md**: `.claude/skills/asset-management-workflow/SKILL.md`
- **テーマ設定**: `data/config/asset-management-themes.json`
- **JP RSSプリセット**: `data/config/rss-presets-jp.json`
- **記事ライター**: `.claude/agents/asset-management-writer.md`
- **コンプライアンス批評**: `.claude/agents/finance-critic-compliance.md`
- **軽量リバイザー**: `.claude/agents/asset-management-reviser.md`
- **記事テンプレート**: `template/asset_management/`
- **プロジェクト計画**: `docs/project/project-4/project.md`
