# 議論メモ: iDeCo×新NISA×企業型DC 2026年改正記事 全工程一括実行

**日付**: 2026-04-27
**参加**: ユーザー + AI

## 背景・コンテキスト

`articles/asset_management/2026-04-27_ideco-nisa-dc-2026-tax-portfolio/` に対して
`/article-full` を実行。ユーザー指示によりHFを全スキップし一括自動実行した。

## 議論のサマリー

- 記事タイトル: **iDeCo×新NISA×企業型DC｜2026年改正で節税を最大化する設計術**
- カテゴリ: asset_management / theme: ideco
- 対象読者: intermediate

### 実行フロー

| フェーズ | 内容 | 結果 |
|---------|------|------|
| Phase 2 リサーチ | 厚労省公式PDF・メディア含む7ソース | KGギャップ4件解消 |
| Phase 3 初稿 | 9,828字、セクション7+末尾 | 表3/チャート2プレースホルダー |
| Phase 4 批評 | 6エージェント並列（full mode） | 総合 **84/100** |
| Phase 4.4 画像生成 | 表3枚+チャート2枚 PNG生成 | images/ 5ファイル |
| Phase 5 投稿 | note.com下書き投稿 | 完了 |

### 2026年改正の3段階スケジュール（記事の主軸）

1. **2026年1月**: 退職所得控除「5年ルール」→「10年ルール」延長
2. **2026年4月**: 企業型DCマッチング拠出の「事業主掛金以下」制限撤廃
3. **2026年12月確定・2027年1月適用**: 掛金上限大幅引き上げ
   - 企業年金なし会社員: 月2.3万円 → 月6.2万円（約2.7倍）

## 決定事項

1. **HFスキップ方針**: ユーザー指示によりリサーチ確認・初稿レビュー・最終承認を全スキップ
2. **記事構成**: 3段階改正フェーズ別 + 属性別4ケース設計 + 節税シミュレーション
3. **統計誤解釈修正**: 「全加入者の約3人に1人」→「マッチング拠出導入企業在籍加入者の約34%」

## 批評スコア詳細（84/100）

| 批評項目 | スコア | 主な指摘 |
|---------|-------|---------|
| コンプライアンス | 83/100 | 「お勧めします」2箇所・免責事項不完全 |
| 事実正確性 | 82/100 | 統計解釈誤り・上限枠の時点不明確 |
| 構成 | 78/100 | 遷移文欠如・シミュレーション欠落 |
| データ正確性 | 90/100 | 自営業節税額の税率矛盾・端数誤差 |
| 読みやすさ | 83/100 | 200文字超の1文・専門用語説明不足 |
| ライター規約 | 88/100 | ソースURLリンク漏れ4箇所 |

→ 修正版で10件修正済み

## アクションアイテム

- [ ] note.comでカバー画像・ハッシュタグを設定して公開 (優先度: 高, 期日: 2026-04-28)
  - 下書きURL: https://editor.note.com/notes/n3d033831cdf1/edit/

## 生成ファイル

```
articles/asset_management/2026-04-27_ideco-nisa-dc-2026-tax-portfolio/
├── 01_research/
│   ├── research_notes.md     # 7ソース・KGギャップ分析
│   └── sources.json
├── 02_draft/
│   ├── first_draft.md        # 初稿 9,828字
│   ├── critic.json           # 6エージェント批評結果
│   ├── critic.md             # 批評レポート（人間可読）
│   └── revised_draft.md     # 修正版（10件修正）
├── images/
│   ├── table_comparison_three_plans.png
│   ├── table_contribution_limits.png
│   ├── table_attribute_matrix.png
│   ├── chart_reform_schedule.png
│   └── chart_tax_simulation.png
└── 03_published/
    └── article.md
```

## 参考情報

- 厚労省「iDeCoがパワーアップします！」PDF: https://www.mhlw.go.jp/content/12500000/001620594.pdf
- 厚労省「DC拠出限度額（令和8年12月〜）」PDF: https://www.mhlw.go.jp/content/12500000/001597082.pdf
- アムンディ「2026年の確定拠出年金の改正内容と活用法」: https://www.am-one.co.jp/hagukumu/article/column-20260319-1.html
