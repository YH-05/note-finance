# 議論メモ: Meta Developer App作成 + Threads/Instagram API接続 + R2画像ホスティング構築

**日付**: 2026-03-23
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-23-meta-api-setup

## 背景・コンテキスト

Threads×Instagram自動投稿マネタイズ戦略（3アカウント構成、転職からパイロット）の技術基盤構築セッション。
disc-2026-03-21-threads-instagram-api-research で調査済みのAPI仕様に基づき、実際の環境構築を実施。

## 議論のサマリー

### 実施内容（全て1セッションで完了）

1. **新規アカウント作成**
   - 新規Facebookアカウント + Instagramアカウント(`career_sister`)を作成
   - InstagramをCreatorアカウントに設定

2. **Meta Developer App作成**
   - App名: threads-poster-IG
   - App ID: 954784063626270
   - Use Case: Threads API + Instagram API (Instagram Login方式)
   - テスター追加・承認の手順を経てトークン取得

3. **API接続確認**
   - Threads API: テキスト投稿成功（https://www.threads.com/@career_sister/post/DWNiPIvkhON）
   - Instagram API: 画像投稿成功（https://www.instagram.com/p/DWNijP4knsn/）
   - Instagram User ID: 34332538239725913
   - Threads User ID: 26810623045189279

4. **Cloudflare R2 画像ホスティング構築**
   - バケット: instagram-image (APAC)
   - Public Development URL有効化
   - API Token発行（Object Read & Write）
   - ローカル画像→R2→Instagram投稿パイプライン動作確認済み

5. **Python投稿モジュール実装**（`src/creator/`）
   - `poster.py`: Threads/Instagram投稿（text/image/carousel対応）
   - `image_hosting.py`: Cloudflare R2画像アップロード
   - `token_refresh.py`: トークン自動リフレッシュ（cron対応）

6. **トークンリフレッシュ実行**
   - Threads: 59日有効に更新
   - Instagram: 59日有効に更新
   - `.env` 自動更新済み

### セットアップ時のハマりポイント

- Meta Developer ポータルのUI変更で「My Apps」→「App Dashboard」に変更されていた
- 「Add Product」は廃止、Use Caseベースに移行
- Instagram トークン生成前に「役割」タブでテスター追加・承認が必要
- テスター招待の承認場所: Instagramアプリ→設定→「アプリのウェブサイトへのアクセス許可」
- Dashboard生成トークンは通常の長命トークン交換(`ig_exchange_token`)が使えない → リフレッシュ(`ig_refresh_token`)は正常動作
- Instagram APIは画像の公開URL必須（ローカルファイル直接アップロード不可）

## 決定事項

1. **dec-2026-03-23-meta-app-created**: Meta Developer App作成完了。career_sisterアカウントでThreads/Instagram両API接続確認
2. **dec-2026-03-23-r2-image-hosting**: Cloudflare R2を画像ホスティングに採用。instagram-imageバケット(APAC)
3. **dec-2026-03-23-creator-package**: src/creator/パッケージ（poster.py + image_hosting.py + token_refresh.py）を新規作成

## 完了したアクションアイテム

- [x] act-2026-03-21-020: Meta Developer App 作成（Threads + Instagram両方のUse Case設定）
- [x] act-2026-03-21-021: OAuth フロー実装 + Long-lived token取得・自動リフレッシュ
- [x] act-2026-03-21-022: 画像ホスティング選定・セットアップ（Cloudflare R2）
- [x] act-2026-03-21-023: Threads投稿モジュール実装（text/image/carousel対応）
- [x] act-2026-03-21-024: Instagramカルーセル投稿モジュール実装（5ステップフロー）

## 残タスク（未着手）

- [ ] act-2026-03-21-025: レート制限モニタリング + 投稿スケジューラー設計 (medium)
- [ ] act-2026-03-21-030: App Review申請: threads_keyword_search スコープ承認 (high)
- [ ] act-2026-03-21-031: App Review申請: Instagram Public Content Access feature承認 (high)
- [ ] act-2026-03-21-032: Threads競合投稿取得モジュール実装 (medium)
- [ ] act-2026-03-21-033: Threadsキーワード検索モジュール実装 (medium)
- [ ] act-2026-03-21-034: Instagram Business Discoveryモジュール実装 (medium)
- [ ] act-2026-03-21-035: Instagram Hashtag Searchモジュール実装 (medium)
- [ ] act-2026-03-21-016: pencil.devでカルーセルテンプレート作成 (high)
- [ ] act-2026-03-21-019: pencil.dev環境セットアップ (high, in_progress)
- [ ] act-2026-03-21-010: ASP登録実行 (high)

## 次回の議論トピック

- pencil.dev でカルーセルテンプレートの作成・検証
- 投稿スケジューラーの設計（cron vs 常駐プロセス）
- 転職アカウントのペルソナ設計・ナレッジファイル作成
- ASP案件選定・登録
- App Review申請（読み取りAPI用）

## 技術情報

### .env に保存された認証情報

| 変数 | 用途 |
|------|------|
| META_APP_ID | Meta App ID |
| META_APP_SECRET | Meta App Secret |
| INSTAGRAM_APP_ID | Instagram App ID |
| INSTAGRAM_APP_SECRET | Instagram App Secret |
| INSTAGRAM_ACCESS_TOKEN | Instagram長命トークン（59日有効） |
| INSTAGRAM_USER_ID | Instagram User ID |
| THREADS_ACCESS_TOKEN | Threads長命トークン（59日有効） |
| THREADS_USER_ID | Threads User ID |
| R2_ACCOUNT_ID | Cloudflare Account ID |
| R2_ACCESS_KEY_ID | R2 API Access Key |
| R2_SECRET_ACCESS_KEY | R2 API Secret Key |
| R2_BUCKET_NAME | R2バケット名 (instagram-image) |
| R2_PUBLIC_URL | R2公開URL |

### CLIの使い方

```bash
# Threadsテキスト投稿
uv run python -m src.creator.poster threads --text "投稿内容"

# Instagram画像投稿
uv run python -m src.creator.poster instagram --text "キャプション" --image-url "https://..."

# トークンリフレッシュ
uv run python -m src.creator.token_refresh
```

## 参考情報

- テスト投稿(Threads): https://www.threads.com/@career_sister/post/DWNiPIvkhON
- テスト投稿(Instagram): https://www.instagram.com/p/DWNijP4knsn/
- R2経由テスト投稿(Instagram): https://www.instagram.com/p/DWNkiBskman/
- Meta Developer App Dashboard: https://developers.facebook.com/apps/954784063626270/
- Cloudflare R2 Dashboard: https://dash.cloudflare.com/
