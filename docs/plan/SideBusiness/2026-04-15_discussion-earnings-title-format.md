# 議論メモ: earnings カテゴリ note.com 投稿タイトルフォーマット定義

**日付**: 2026-04-15
**参加**: ユーザー + AI

## 背景・コンテキスト

株投資ラボの earnings カテゴリ記事を note.com に投稿する際、タイトル形式が記事ごとに揺れていた（例: `TSLA Q1 2026 決算プレビュー — 4月22日、…`）。アカウントブランディングと一覧画面での視認性を統一するため、共通プレフィックスと構造を必須化する。

## 議論のサマリー

- ユーザーから新フォーマットの仕様提示: `【🇺🇸米株決算】企業名（ティッカー）QX YYYY 決算プレビュー/レビュー`
- 四半期（Q1-Q4）と西暦年は決算内容から判定する
- 米国企業限定の運用とし、米国上場であることをチェックする必要がある（TSMC=台湾、ASML=蘭などは別扱い）
- 既存スキルへ定義を組み込む方針で合意

## 決定事項

1. earnings カテゴリの note.com 投稿タイトルは以下の形式に統一する:
   - `【🇺🇸米株決算】{企業名}（{ティッカー}）Q{1-4} {YYYY} 決算プレビュー`
   - `【🇺🇸米株決算】{企業名}（{ティッカー}）Q{1-4} {YYYY} 決算レビュー`
2. プレフィックス `【🇺🇸米株決算】` は **米国上場企業のみ** に付与する。米国外企業（TSMC / ASML / Alibaba ADR 等）は対象外とする
3. 米国企業判定は `av_company_overview.Country == "USA"` または `Exchange in (NYSE, NASDAQ, NYSE ARCA)` または SEC EDGAR CIK 登録ありで確認する
4. フロントマターに `fiscal_quarter` / `fiscal_year` / `market: US` フィールドを追加する
5. ルールは以下の2スキルに定義する:
   - `.claude/skills/finance-article-writer/references/earnings.md`（生成時のルール）
   - `.claude/skills/article-publish/SKILL.md`（投稿前検証）

## アクションアイテム

- [x] earnings.md にタイトルフォーマット節を追加（優先度: 高）
- [x] earnings.md フロントマター例を新形式に更新（優先度: 高）
- [x] article-publish/SKILL.md Step 2 にタイトル検証ステップ追加（優先度: 高）
- [x] article-publish/SKILL.md チェックリストに earnings 専用2項目追加（優先度: 中）
- [ ] 既存の earnings 記事ドラフト（articles/earnings/2026-04-15_*）のタイトルを順次新形式へ移行（優先度: 中）
- [ ] meta.yaml への `market: US` / `fiscal_quarter` / `fiscal_year` フィールド追加を `/article-init` テンプレートにも反映（優先度: 低）

## 次回の議論トピック

- 米国外企業の決算記事を扱う場合のプレフィックス体系（例: `【🇹🇼台湾株決算】` / `【🇪🇺欧州株決算】`）
- 既存ドラフトのリネーム時、note.com 上で投稿済みのものは note 側タイトルも更新するか

## 参考情報

- 既存earnings記事サンプル: `articles/earnings/2026-04-15_tsla-q1-2026-earnings-preview/02_draft/revised_draft.md`
- 関連ルール: `.claude/rules/article-quality-standards.md`
