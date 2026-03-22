# 議論メモ: Docker Desktop 外付けSSD bind mount 問題の解決

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j と creator-neo4j が `/tmp`（再起動で消失リスク）で稼働していた。原因は Docker Desktop for Mac が外付けSSD（`/Volumes/NeoData`、APFS形式）を bind mount できないこと。

## ストレージ構成

| ストレージ | パス | 種類 | 容量 |
|-----------|------|------|------|
| ローカルSSD | `/` | APFS内蔵 | 57GB空き |
| 外付けSSD | `/Volumes/NeoData` | APFS外付け | 1.9TB空き |
| NAS | `/Volumes/personal_folder` | SMB (Tailscale) | 5.4TB空き |

## 調査結果

### 根本原因
Docker Desktop for Mac の VirtioFS が外付け APFS ボリュームの bind mount に失敗する既知バグ（[GitHub #7480](https://github.com/docker/for-mac/issues/7480)）。VM内部で `/host_mnt/Volumes/NeoData` を `mkdir` しようとして `file exists` エラー。

### 試した方法
- `-v` 構文: 失敗
- `--mount type=bind` 構文: 失敗
- symlink 経由: 失敗（Docker がリンク先を解決してしまう）
- `~/` 配下: 成功（内蔵SSDのみ）

### 解決策
Docker Desktop → Settings → General → file sharing implementation を **VirtioFS → gRPC FUSE** に変更。即座に外付けSSD bind mount が成功。

### 検討した他の案
- **案B: Docker VM ディスクイメージごと外付けSSDに移動**（symlink方式）— 確実だが大掛かり。不要になった。

## 決定事項

1. **gRPC FUSE で外付けSSD直結を採用** — VirtioFS比でI/O速度がやや低下するが、Neo4j用途では十分
2. **ストレージ方針**: Neo4jデータは外付けSSD、PDF/数値データはNAS

## 移行結果

| インスタンス | 移行前 | 移行後 |
|-------------|-------|-------|
| research-neo4j | `/tmp/neo4j-research-data` | `/Volumes/NeoData/neo4j-research/data` |
| creator-neo4j | `/tmp/creator-neo4j-data` | `/Volumes/NeoData/neo4j-creator/data` |
| note-neo4j | Docker named volume | （変更なし） |
| quants-neo4j | Docker named volume | （変更なし） |

## 完了したActionItem

- [x] act-2026-03-21-008: NASマウント恒久対応
- [x] act-2026-03-21-009: /tmp→NASデータ書き戻し

## 次回の議論トピック

- gRPC FUSE のパフォーマンス影響モニタリング（問題があればディスクイメージ移動案Bに移行）
- note-neo4j / quants-neo4j も外付けSSD bind mount に統一するか検討
