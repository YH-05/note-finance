---
name: backup-auradb
description: research-neo4j（ローカル）のデータを AuraDB（クラウド）にバックアップするスキル。MERGEベースの冪等移行で全ノード・リレーションを転送し、検証結果を報告する。「AuraDBにバックアップ」「Neo4jバックアップ」「グラフDBバックアップ」「クラウドにバックアップ」「AuraDB同期」「research-neo4j バックアップ」と言われたら必ずこのスキルを使うこと。
allowed-tools: Bash, Read
---

# backup-auradb スキル

research-neo4j（bolt://localhost:7688）のナレッジグラフデータを Neo4j AuraDB にバックアップする。
Python スクリプトで両DBに直接接続し、MERGE ベースで冪等に全データを転送する。

## 実行手順

### Step 1: ローカルDB起動確認

```bash
docker ps --filter name=neo4j-research --format '{{.Names}} {{.Status}}'
```

neo4j-research コンテナが起動していない場合はユーザーに通知して終了。

### Step 2: 移行スクリプト実行

```bash
uv run --with neo4j python .claude/skills/backup-auradb/scripts/migrate_to_aura.py
```

スクリプトは以下の4フェーズを自動実行する:

1. **接続テスト** — ローカル・AuraDB両方への接続を確認
2. **ノード移行** — 13ラベルをバッチ（100件単位）で MERGE 投入
3. **リレーション移行** — 30タイプをラベルペア別にバッチ投入
4. **検証** — AuraDB上のノード数・リレーション数を集計

### Step 3: 結果報告

スクリプト出力を読み取り、以下をユーザーに報告する:

- 移行されたノード数（ラベル別）
- 移行されたリレーション数（タイプ別）
- ローカルとの差分があれば原因を説明
- 実行時間

## 接続情報

| DB | URI | 備考 |
|----|-----|------|
| research-neo4j | bolt://localhost:7688 | ローカルDockerコンテナ |
| AuraDB | neo4j+s://57a2e342.databases.neo4j.io | Neo4j AuraDB Free |

接続認証情報は `.mcp.json` の `neo4j-research` と `neo4j-aura` エントリに格納されている。
スクリプトは `.mcp.json` から自動読み取りする。

## 除外対象

以下のノードはバックアップ対象外:
- `Memory` — MCP Memory 用ノード（finance-neo4j に存在）
- `Implementation` — 実装メモ（一時的なもの）

## 注意事項

- MERGE ベースなので何度実行しても安全（冪等）
- `topic_id` が未設定の Topic ノードへの SHARES_TOPIC リレーションは移行されない（派生データのため実害なし）
- AuraDB Free は容量制限（ノード 20万・リレーション 40万）があるが、現在のデータ量（~4Kノード・~20Kリレーション）では十分余裕がある
- 大量データ追加後はバックアップを再実行すること
