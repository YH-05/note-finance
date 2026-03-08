---
name: sync-claude-gemini
description: .claude/ と .gemini/ のスキル・コマンド・ワークフローを同期するスキル。
片方で作成・更新された設定をもう片方にも反映する。
/sync-claude-gemini コマンドで使用、またはスキル・コマンド変更時にプロアクティブに使用。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Sync Claude-Gemini - 設定同期スキル

`.claude/` と `.gemini/` のスキル・コマンド・ワークフローを双方向に同期します。

## いつ使うか

以下の操作を行った**直後**にこのスキルを実行すること：

1. `.claude/commands/` にコマンドを追加・更新・削除した
2. `.claude/skills/` にスキルを追加・更新した
3. `.agents/skills/` に共有スキルを追加・更新した
4. `.agents/workflows/` にワークフローを追加・更新した
5. `.gemini/commands/` にコマンドを追加・更新・削除した

## ディレクトリ構造マッピング

```
.claude/commands/*.md      ←→  .gemini/commands/*.toml
.claude/skills/*/SKILL.md  ←→  .agents/skills/*/SKILL.md  (共有)
.agents/workflows/*.md     ←→  (Claude/Gemini 両方から参照)
```

### ファイル形式の変換ルール

#### Claude コマンド (.md) → Gemini コマンド (.toml)

**入力**: `.claude/commands/{name}.md`
```markdown
---
description: コマンドの説明
argument-hint: [--option value]  # あれば
---

# コマンドタイトル
...
```

**出力**: `.gemini/commands/{name}.toml`

参照先の決定ロジック:

1. `.claude/commands/{name}.md` の内容を読む
2. スキル参照（`.claude/skills/{name}/SKILL.md`）がある場合:
   - `.agents/skills/{name}/SKILL.md` が存在するか確認
   - 存在する → prompt に `.agents/skills/{name}/SKILL.md` を参照させる
   - 存在しない → `.claude/skills/{name}/SKILL.md` を `.agents/skills/{name}/SKILL.md` にコピーし、prompt で参照
3. ワークフロー参照（`.agents/workflows/{name}.md`）がある場合:
   - prompt に `.agents/workflows/{name}.md` を参照させる
4. どちらでもない場合:
   - コマンド内容を要約して prompt に直接記述

**TOML 生成テンプレート**:

```toml
# スキル参照パターン
prompt = "Activate the `{name}` skill by following the instructions in `.agents/skills/{name}/SKILL.md`."
description = "{description（日本語）}"

# ワークフロー参照パターン
prompt = "Activate the {Title} workflow by following the instructions in `.agents/workflows/{name}.md`."
description = "{description（日本語）}"
```

#### Gemini コマンド (.toml) → Claude コマンド (.md)

**入力**: `.gemini/commands/{name}.toml`
```toml
prompt = "..."
description = "コマンドの説明"
```

**出力**: `.claude/commands/{name}.md`

```markdown
---
description: {description}
---

# {タイトル}

{prompt の内容に基づいた説明}

**必須**: 対応するスキルまたはワークフローを参照すること。

> **スキル参照**: `.claude/skills/{name}/SKILL.md` または `.agents/skills/{name}/SKILL.md`
```

## 実行手順

### ステップ 1: 差分検出

```bash
# Claude コマンド一覧
ls .claude/commands/ | sed 's/\.md$//' | sort > /tmp/claude_cmds.txt

# Gemini コマンド一覧
ls .gemini/commands/ | sed 's/\.toml$//' | sort > /tmp/gemini_cmds.txt

# 差分表示
diff /tmp/claude_cmds.txt /tmp/gemini_cmds.txt
```

### ステップ 2: 不足ファイルの特定

差分から以下を分類:
- **Claude のみ**: `.claude/commands/` にあるが `.gemini/commands/` にないもの
- **Gemini のみ**: `.gemini/commands/` にあるが `.claude/commands/` にないもの
- **共通**: 両方にあるもの（内容の同期を確認）

### ステップ 3: 同期実行

#### 3a. Claude → Gemini 同期（不足分の作成）

Claude にのみ存在するコマンドについて:

1. `.claude/commands/{name}.md` を読む
2. description を抽出（YAML frontmatter から）
3. 参照先を特定（スキル or ワークフロー）
4. `.gemini/commands/{name}.toml` を生成

#### 3b. Gemini → Claude 同期（不足分の作成）

Gemini にのみ存在するコマンドについて:

1. `.gemini/commands/{name}.toml` を読む
2. description を抽出
3. 参照先を特定（prompt の内容から）
4. `.claude/commands/{name}.md` を生成

#### 3c. 共有スキルの同期

`.claude/skills/*/SKILL.md` が更新された場合:

1. `.agents/skills/{name}/SKILL.md` が存在するか確認
2. 存在する場合: 内容を比較し、新しい方で上書き
3. 存在しない場合: `.agents/skills/{name}/` を作成しコピー

### ステップ 4: 検証

```bash
# 再度差分を確認（空になるべき）
diff <(ls .claude/commands/ | sed 's/\.md$//' | sort) \
     <(ls .gemini/commands/ | sed 's/\.toml$//' | sort)

# 各 toml の構文チェック
for f in .gemini/commands/*.toml; do
  python3 -c "import tomllib; tomllib.load(open('$f', 'rb'))" 2>&1 && echo "OK: $f" || echo "ERROR: $f"
done
```

### ステップ 5: 結果報告

```markdown
## 同期結果

| 方向 | 作成 | 更新 | スキップ |
|------|------|------|----------|
| Claude → Gemini | N件 | N件 | N件 |
| Gemini → Claude | N件 | N件 | N件 |
| 共有スキル同期 | N件 | N件 | N件 |

### 作成されたファイル
- `.gemini/commands/{name}.toml`
- ...

### 更新されたファイル
- `.agents/skills/{name}/SKILL.md`
- ...
```

## 注意事項

- `.claude/agents/` はClaude Code固有のため、Geminiには同期しない
- `.claude/rules/` はClaude Code固有のため、Geminiには同期しない
- `.gemini/settings.json` はGemini固有のため、Claudeには同期しない
- 共有スキル（`.agents/skills/`）の更新時は、Claude/Gemini両方からの参照を確認
- TOML ファイルの `prompt` フィールドで日本語を使う場合はUTF-8であること
