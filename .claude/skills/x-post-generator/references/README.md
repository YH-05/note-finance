# 参照ライブラリ — 運用ルール

X投稿の品質を継続的に高めるための優良サンプルライブラリ。
生成時に類似サンプルを参照し、`why_it_works` フィールドをヒントとして活用する。

---

## ディレクトリ構造

```
references/
├── README.md           ← 本ファイル（運用ルール）
├── index.yaml          ← 全サンプルの検索インデックス
├── asset_management/    ← 資産形成カテゴリのサンプル
├── asset_management/   ← 資産運用カテゴリのサンプル
├── macro_economy/      ← マクロ経済カテゴリのサンプル
├── stock_analysis/     ← 株式分析カテゴリのサンプル
├── market_report/      ← 週次レポートカテゴリのサンプル（必要時に追加）
├── side_business/      ← 副業カテゴリのサンプル（必要時に追加）
└── quant_analysis/     ← クオンツ分析カテゴリのサンプル（必要時に追加）
```

---

## ファイル命名規則

```
{audience}-{keyword}-hook-{pattern}.md
```

例:
- `beginner-ideco-hook-C.md`
- `intermediate-index-hook-B.md`
- `advanced-dividend-hook-D.md`

| 要素 | 値 |
|------|-----|
| audience | `beginner` / `intermediate` / `advanced` |
| keyword | 記事の核心キーワード（英語小文字、ハイフン区切り） |
| pattern | `A` / `B` / `C` / `D` |

---

## ファイルフォーマット

```yaml
---
sample_id: {category}-{audience}-{keyword}-hook-{pattern}-001
category: {category}
audience: {beginner|intermediate|advanced}
hook_pattern: {A|B|C|D}
engagement_score: null       # 実績エンゲージメント（後から追記）
impressions: null            # インプレッション数（後から追記）
posted_at: null              # 投稿日時（後から追記）
note_url: null               # note記事URL（後から追記）
why_it_works: >
  {なぜこの投稿が刺さるかの解説（生成時のヒントになる）}
tags: [{キーワード1}, {キーワード2}]
created_at: "YYYY-MM-DD"
source_article: {articles/category/YYYY-MM-DD_slug/}
---

# 本文

{投稿テキスト（実際のX投稿文）}
```

---

## サンプル追加条件

### 追加すべきケース
- ✅ 実際に投稿してエンゲージメントが良好だったもの
- ✅ 新しいフックパターンやカテゴリの最初のサンプル
- ✅ 特定の記事タイプ（制度変更、逆張り分析など）の代表例

### 追加してはいけないケース
- ❌ 未投稿のドラフトのみ（投稿後に `engagement_score` を更新してから検討）
- ❌ 明らかに文字数オーバー・品質不足のもの
- ❌ 既存サンプルとほぼ同一の内容

---

## 更新タイミング

| イベント | 対応 |
|--------|------|
| 記事を投稿してエンゲージメントデータが取れた | `engagement_score`, `impressions`, `posted_at` を追記 |
| 投稿が高エンゲージメントだった | `why_it_works` に追記・強化 |
| 投稿が低パフォーマンスだった | 削除または `why_it_works` に反省点を記録 |
| 新しいカテゴリ・層の記事を作った | 最初のサンプルとして追加 |

---

## 削除条件

- サンプルが3ヶ月以上古く、トレンドや制度が変わっている
- より良いサンプルが追加され、重複が生じている
- エンゲージメントが明らかに低く、改善の見込みがない

---

## index.yaml の更新方法

サンプルを追加・削除した場合は必ず `index.yaml` も更新すること。

```yaml
# index.yaml に追加する例
- sample_id: asset_management-beginner-ideco-hook-C-001
  file: asset_management/beginner-ideco-hook-C.md
  category: asset_management
  audience: beginner
  hook_pattern: C
  tags: [iDeCo, 節税, 上限引き上げ]
  engagement_score: null
```
