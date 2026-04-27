# 議論メモ: 2026-04-27 asset_management 5記事 note.com下書き投稿セッション

**日付**: 2026-04-27
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-04-27-article-publish-session

## 背景・コンテキスト

本日作成したasset_management記事5本をnote.comに下書き投稿するセッション。
投稿前に2記事のmeta.yamlがstatus=publishedかつnote_url記録済みだったが、
実際にはnote.comに存在しないことが判明し修正が必要となった。

## 投稿結果

| 記事 | 下書きURL | 備考 |
|------|-----------|------|
| 高配当株・インデックス・サイドFIRE | https://editor.note.com/notes/n5d76cac4cd99/edit/ | 重複下書きあり（削除要） |
| iDeCo×新NISA×企業型DC | https://editor.note.com/notes/nb2e0cfbbff4f/edit/ | |
| 老後2000万円問題 再検証 | https://editor.note.com/notes/n6d207cc9f3d9/edit/ | 本文中の繰り下げ表が欠落 |
| インフレ3%防衛戦略 | https://editor.note.com/notes/n99e2be5f9282/edit/ | |
| 米Z世代IRA→新NISA示唆 | https://editor.note.com/notes/n96f85cb3c21f/edit/ | 別スレッドで投稿済み |

## 発見した問題と対処

### 1. meta.yaml誤記録（2記事）

`dividend-vs-index-vs-sidefire` と `ideco-nisa-dc-2026-tax-portfolio` の2記事が
`status: published` かつ `note_url` 記録済みにもかかわらず、実際にはnote.comに存在しなかった。

**原因推定**: 前回セッションで投稿スクリプトが部分的に成功してmeta.yamlを更新したが、
ブラウザ操作が実際には失敗していた可能性。

**対処**: meta.yamlを `status: draft`、`note_url: null`、`published_at: null`、
`workflow.publish: pending` にリセットし、改めて投稿。

### 2. 投稿スクリプト二重実行（dividend記事）

dividend記事の投稿時にコマンドを誤って2回実行し、重複下書きが発生。

- 有効: https://editor.note.com/notes/n5d76cac4cd99/edit/
- 削除要: https://editor.note.com/notes/ncd3cd0aad817/edit/

### 3. 免責事項の損失免責文言欠落（retirement記事）

`retirement-2000man-2026-recheck` の revised_draft.md の免責事項に
「本記事の内容により生じたいかなる損失についても責任を負いかねます」が欠落。
投稿前に発見し修正済み。

### 4. マークダウン表のスキップ（retirement記事）

本文中の繰り下げ受給増加率表（2列×4行）をパーサーが `table_0.png` として
処理しようとしたが、ファイル未生成のためスキップ。
note.comの下書きに表が表示されていない。

## 決定事項

- **dec-2026-04-27-meta-yaml-publish-status**: 投稿後はnote.com上で目視確認を必須とする
- **dec-2026-04-27-disclaimer-loss-clause**: 投稿前チェックで損失免責文言を必ず確認する

## アクションアイテム

- [ ] **[高/即時]** ncd3cd0aad817の重複下書きをnote.comから削除
- [ ] **[中/2026-04-28]** retirement記事の下書きで繰り下げ受給表を手動補完

## 収益化戦略アクションアイテム（disc-2026-04-27-kabu-lab-monetization-strategyより）

- [ ] **[高/2026-04-30]** kabutoushi_laboプロフィール書き換え（肩書控えめ・asset_managementフォーカス）
- [ ] **[高/2026-05-04]** 既存ヒット記事3本を有料化 + asset_managementマガジン購読開設（月額¥1,980）
