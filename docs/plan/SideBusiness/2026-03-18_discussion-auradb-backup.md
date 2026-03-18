# 議論メモ: research-neo4j → AuraDB Free バックアップ

**日付**: 2026-03-18
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j (bolt://localhost:7688) はDockerコンテナで運用中だが、クラウドバックアップが存在しない状態だった。データ消失リスクに備え、Neo4j AuraDB Free Tierへのバックアップを検討。

## 調査結果

### research-neo4j データサイズ

| 項目 | 値 |
|------|-----|
| ノード数 | 3,282 |
| リレーション数 | 5,310 |
| ラベル種別 | 14 (Source, Claim, Chunk, FinancialDataPoint, Entity, Fact, Topic, Metric, Insight, FiscalPeriod, Author, Stance, Memory, Implementation) |
| リレーション種別 | 21 |
| プロパティキー | 120 |

### AuraDB Free Tier 仕様

| 項目 | 上限 |
|------|------|
| ノード数 | 200,000 |
| リレーション数 | 400,000 |
| APOC | 400+関数利用可（ファイルシステム系は不可） |
| 自動バックアップ | なし（手動スナップショット1つのみ） |
| 注意 | 長期未アクセスで自動停止の可能性あり |

### 移行方式の比較

| 方式 | 概要 | 採用 |
|------|------|------|
| neo4j-admin dump → upload | CLI経由のバイナリダンプ | 不採用 |
| APOC export → LOAD CSV | CSV経由 | 不採用 |
| MCP経由 Cypherベース | neo4j-research MCP読み取り → neo4j-aura MCP書き込み | **採用** |

## 決定事項

1. **AuraDB Free を採用**: データサイズは上限の2%未満で十分収容可能
2. **MCP経由移行方式**: 既存MCPインフラを活用し、Cypherベースで直接移行

## 実施内容

### 完了

- [x] AuraDB Free インスタンス作成（d7634098.databases.neo4j.io）
- [x] .mcp.json に neo4j-aura MCP設定追加（namespace: aura）

### 未完了（インスタンスプロビジョニング待ち）

- [ ] AuraDB接続テスト（DNS解決確認）
- [ ] Claude Code再起動でneo4j-aura MCP有効化
- [ ] MCP経由で全データ移行（ノード→インデックス→リレーション）
- [ ] データ検証（ノード数・リレーション数の一致確認）

## AuraDB 接続情報

- URI: `neo4j+s://d7634098.databases.neo4j.io`
- Username: `d7634098`
- Password: (settings.local.json参照)

## MCP設定（.mcp.json に追加済み）

```json
{
  "neo4j-aura": {
    "command": "uvx",
    "args": [
      "mcp-neo4j-cypher",
      "--db-url", "neo4j+s://d7634098.databases.neo4j.io",
      "--username", "d7634098",
      "--password", "***",
      "--database", "neo4j",
      "--namespace", "aura"
    ]
  }
}
```

## 次回の作業

1. AuraDBインスタンスがRunningになったら接続テスト
2. Claude Code再起動 → neo4j-aura MCPの動作確認
3. 移行スクリプト実行（ラベル別バッチ投入）
4. 検証完了後、定期バックアップ運用の検討
