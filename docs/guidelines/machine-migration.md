# 別マシンへの移行手順

最終更新: 2026-09-07

このリポジトリは **Git に載らない資産**（Neo4j グラフ 2GB、APIキー、MCP設定）に
依存している。Git clone だけでは動作しない。本書はその差分を埋める手順。

## 移行対象の全体像

| 資産 | 所在 | 移送方法 |
|------|------|----------|
| コード・記事・RawStore | GitHub `YH-05/note-finance` | `git clone` |
| Neo4j グラフ（5 DB / 211MB） | `~/neo4j-backup-20260907/` | 手動コピー（dump） |
| `.env` / `.mcp.json` / `settings.local.json` / `data/config/` | `~/note-finance-migration-20260907/secrets/` | 手動コピー |
| `data/scraped/` (294MB) | ローカルのみ・gitignore | 再取得可（下記） |
| launchd 定期実行 | `config/launchd/*.plist` | 移行先で再インストール |

## 手順

### 1. リポジトリ取得

```bash
git clone https://github.com/YH-05/note-finance.git
cd note-finance
uv sync --all-extras
```

### 2. 秘匿ファイルを配置

`~/note-finance-migration-20260907/secrets/` を移行先へ運び、展開する。

```bash
SRC=~/note-finance-migration-20260907/secrets
cp "$SRC/.env" .env
cp "$SRC/.mcp.json" .mcp.json
cp "$SRC/.claude/settings.local.json" .claude/settings.local.json
cp -R "$SRC/data/config/." data/config/
chmod go-rwx .env .mcp.json

# 完全性チェック
cd ~/note-finance-migration-20260907/secrets && \
  shasum -a 256 -c ../SECRETS_SHA256SUMS.txt
```

> `.claude/settings.local.json` は権限許可リスト41件。
> `sync-nas` スキルの同期対象外（「マシン固有」扱い）のため手動で運ぶ必要がある。

### 3. Neo4j 復元

`~/neo4j-backup-20260907/RESTORE.md` の手順に従う。要点のみ:

```bash
mkdir -p ~/neo4j-data/enterprise/{data,logs,plugins,import}
cp ~/neo4j-backup-20260907/*.dump ~/neo4j-data/enterprise/import/

docker compose up -d neo4j && docker stop neo4j-enterprise
for db in system research creator note quants; do
  docker run --rm -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
    -v "$HOME/neo4j-data/enterprise/data:/data" \
    -v "$HOME/neo4j-data/enterprise/import:/var/lib/neo4j/import" \
    neo4j:5.26-enterprise \
    neo4j-admin database load "$db" --from-path=/var/lib/neo4j/import --overwrite-destination=true
done
docker start neo4j-enterprise
```

### 4. パス依存の確認

`.env` の以下3変数は**コメントアウト済み**（旧マシンの絶対パスだったため）。
移行先で外部ボリュームを使う場合のみ再設定する。

| 変数 | 未設定時の挙動 |
|------|---------------|
| `DATA_ROOT` | `{project}/data` にフォールバック |
| `CONVERT_PDF_DIR` | `DATA_ROOT/processed` にフォールバック |
| `FRED_HISTORICAL_CACHE_DIR` | コード内参照 0 件（削除可） |

> ⚠ `DATA_ROOT` は**設定済みかつパス不在なら `DataPathError` を送出する**
> （フォールバックしない設計）。存在しないパスを書くと 14 ファイル分の
> スクリプトが起動時に落ちる。

NAS (`/Volumes/personal_folder`) 前提のスキル10件は、NAS 未マウントでも
`scripts/_script_utils.py` がプロジェクトローカルへフォールバックする。

### 5. launchd 定期実行の再インストール（必要な場合のみ）

plist 内のパスは旧マシンの絶対パスを含むため、**書き換えが必須**。

```bash
for f in config/launchd/*.plist; do
  sed "s|/Users/yukihata|$HOME|g; s|/Users/yuki/Desktop/note-finance|$PWD|g" "$f" \
    > ~/Library/LaunchAgents/$(basename "$f")
  launchctl bootstrap gui/$UID ~/Library/LaunchAgents/$(basename "$f")
done
```

旧マシンでは 2026-09-07 に全16ジョブを `bootout` 済み
（plist は `trash/LaunchAgents-20260907/` に退避）。

### 6. `data/scraped/` の扱い

294MB・gitignore 対象・NAS 同期対象外のため移送されない。
中身は 11 ソースのスクレイピング生データで、**再取得可能**。
ただし重複排除の基準が失われるため、初回実行時に既取得記事を
再度処理する可能性がある。必要なら手動でコピーすること。

## 移行元マシンでの後始末

1. 本書の手順で移行先の動作確認が取れるまで、**ローカルリポジトリと
   `~/neo4j-data/` を削除しないこと**
2. 確認後に削除する対象:
   - `~/Desktop/note-finance/`（3.6GB）
   - `~/neo4j-data/`（2.0GB）
   - `~/neo4j-backup-20260907/` と `~/note-finance-migration-20260907/`（移送後）
3. `~/note-finance-migration-20260907/` には API キー30種が平文で入っている。
   移送完了後は確実に削除すること。
