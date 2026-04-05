"""Unit tests for note_publisher.markdown_parser module.

revised_draft.md を ArticleDraft に変換する parse_draft() 関数のテスト。
YAML frontmatter 抽出、修正履歴除外、6種類のブロックパース、テーブル→画像変換を検証する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from note_publisher.markdown_parser import parse_draft
from note_publisher.types import ArticleDraft
from structlog.testing import capture_logs

if TYPE_CHECKING:
    from pathlib import Path

# =============================================================================
# Frontmatter
# =============================================================================


class TestFrontmatter:
    """YAML frontmatter の抽出テスト。"""

    def test_正常系_frontmatterを正しく抽出できる(self, tmp_path: Path) -> None:
        """YAML frontmatter が ArticleDraft.frontmatter に正しく格納されることを確認。"""
        md = """\
---
title: テスト記事タイトル
category: investment
tags:
  - 投資
  - 資産形成
---

# テスト記事タイトル

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert isinstance(result, ArticleDraft)
        assert result.frontmatter["title"] == "テスト記事タイトル"
        assert result.frontmatter["category"] == "investment"
        assert result.frontmatter["tags"] == ["投資", "資産形成"]
        assert result.title == "テスト記事タイトル"

    def test_エッジケース_frontmatterがない場合(self, tmp_path: Path) -> None:
        """frontmatter がない Markdown でも正常にパースできることを確認。"""
        md = """\
# タイトルのみ

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.frontmatter == {}
        assert result.title == "タイトルのみ"


# =============================================================================
# 修正履歴の除外
# =============================================================================


class TestRevisionHistory:
    """修正履歴セクションの除外テスト。"""

    def test_正常系_修正履歴を除外できる(self, tmp_path: Path) -> None:
        """``## 修正履歴`` セクション以降が body_blocks に含まれないことを確認。"""
        md = """\
---
title: 修正履歴テスト
---

# 修正履歴テスト

本文テキスト。

## 修正履歴

- 2024-01-01: 初版作成
- 2024-01-02: 誤字修正
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 修正履歴セクションの内容がブロックに含まれないことを確認
        all_content = " ".join(b.content for b in result.body_blocks)
        assert "初版作成" not in all_content
        assert "誤字修正" not in all_content

        # 「## 修正履歴」という見出しブロック自体もないことを確認
        revision_headings = [
            b
            for b in result.body_blocks
            if b.block_type == "heading" and b.content == "修正履歴"
        ]
        assert len(revision_headings) == 0

        # 本文テキストは含まれる
        assert any(b.content == "本文テキスト。" for b in result.body_blocks)


# =============================================================================
# ブロックパース（6種類）
# =============================================================================


class TestHeadingBlock:
    """見出しブロックのテスト。"""

    def test_正常系_見出しブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """h2, h3 が body_blocks に含まれ、h1 はタイトルに移動して本文から除去されることを確認。"""
        md = """\
# 大見出し

## 中見出し

### 小見出し
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # h1 はタイトルとして抽出され、本文からは除去される
        assert result.title == "大見出し"

        headings = [b for b in result.body_blocks if b.block_type == "heading"]
        assert len(headings) == 2

        assert headings[0].content == "中見出し"
        assert headings[0].level == 2

        assert headings[1].content == "小見出し"
        assert headings[1].level == 3


class TestParagraphBlock:
    """段落ブロックのテスト。"""

    def test_正常系_段落ブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """通常テキスト行が paragraph ブロックとしてパースされることを確認。

        連続段落の間には空 paragraph が1つ挿入される（note.com 上で1行空ける
        ための spacer）ので、非空 paragraph のみを対象にカウントする。
        """
        md = """\
# タイトル

最初の段落です。

二番目の段落です。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        non_empty_paragraphs = [
            b
            for b in result.body_blocks
            if b.block_type == "paragraph" and b.content
        ]
        assert len(non_empty_paragraphs) == 2
        assert non_empty_paragraphs[0].content == "最初の段落です。"
        assert non_empty_paragraphs[1].content == "二番目の段落です。"


class TestListItemBlock:
    """リスト項目ブロックのテスト。"""

    def test_正常系_リスト項目を正しくパースできる(self, tmp_path: Path) -> None:
        """``- `` で始まる行が list_item ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

- 項目1
- 項目2
- 項目3
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        list_items = [b for b in result.body_blocks if b.block_type == "list_item"]
        assert len(list_items) == 3
        assert list_items[0].content == "項目1"
        assert list_items[1].content == "項目2"
        assert list_items[2].content == "項目3"


class TestBlockquoteBlock:
    """引用ブロックのテスト。"""

    def test_正常系_引用ブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """``> `` で始まる行が blockquote ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

> これは引用テキストです。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        quotes = [b for b in result.body_blocks if b.block_type == "blockquote"]
        assert len(quotes) == 1
        assert quotes[0].content == "これは引用テキストです。"


class TestSeparatorBlock:
    """区切り線ブロックのテスト。"""

    def test_正常系_区切り線を正しくパースできる(self, tmp_path: Path) -> None:
        """``---`` 行が separator ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

本文1

---

本文2
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        separators = [b for b in result.body_blocks if b.block_type == "separator"]
        assert len(separators) == 1
        assert separators[0].content == ""


class TestImageBlock:
    """画像ブロックのテスト。"""

    def test_正常系_画像ブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """``![alt](path)`` パターンが image ブロックとしてパースされることを確認。

        実運用では ``02_draft/revised_draft.md`` から ``images/chart.png``
        を参照すると、article root (tmp_path) の ``images/`` にフォールバック
        して解決される。
        """
        md = """\
# タイトル

![グラフ画像](images/chart.png)
"""
        # 実運用の構造を再現: article_root/02_draft/revised_draft.md
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像は article root の images/ に配置
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "chart.png").write_bytes(b"fake png")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1
        assert images[0].content == "グラフ画像"
        assert images[0].image_path == tmp_path / "images" / "chart.png"


# =============================================================================
# テーブル→画像変換
# =============================================================================


class TestTableToImage:
    """テーブル→画像変換のテスト。"""

    def test_正常系_テーブルを画像ブロックに変換できる(self, tmp_path: Path) -> None:
        """Markdown テーブルが ``images/table_0.png`` の画像ブロックに変換されることを確認。"""
        md = """\
# タイトル

テーブルの前の段落。

| 銘柄 | 価格 |
|------|------|
| AAPL | 150  |
| GOOG | 140  |

テーブルの後の段落。
"""
        # 実運用の構造を再現: article_root/02_draft/revised_draft.md
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像を article root の images/ に作成
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "table_0.png").write_bytes(b"fake png")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1
        assert images[0].image_path == images_dir / "table_0.png"

        # テーブルの生テキストがブロックに残っていないことを確認
        all_content = " ".join(b.content for b in result.body_blocks)
        assert "| 銘柄" not in all_content
        assert "|------" not in all_content

    def test_正常系_複数テーブルの連番が正しい(self, tmp_path: Path) -> None:
        """複数のテーブルが出現順に ``table_0.png``, ``table_1.png`` と変換されることを確認。"""
        md = """\
# タイトル

| A | B |
|---|---|
| 1 | 2 |

中間テキスト。

| C | D |
|---|---|
| 3 | 4 |
"""
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像を article root の images/ に作成
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "table_0.png").write_bytes(b"fake png 0")
        (images_dir / "table_1.png").write_bytes(b"fake png 1")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 2
        assert images[0].image_path == images_dir / "table_0.png"
        assert images[1].image_path == images_dir / "table_1.png"

    def test_エッジケース_テーブルPNGが存在しない場合(
        self,
        tmp_path: Path,
    ) -> None:
        """テーブル PNG が存在しない場合に警告ログが出力されることを確認。"""
        md = """\
# タイトル

| X | Y |
|---|---|
| 1 | 2 |
"""
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        with capture_logs() as cap_logs:
            result = parse_draft(draft_path)

        # 画像ブロックは生成されるがファイルが見つからない警告が出る
        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1

        # structlog.testing.capture_logs で警告ログをキャプチャ
        warning_logs = [log for log in cap_logs if log.get("log_level") == "warning"]
        assert len(warning_logs) >= 1
        assert "table_0.png" in str(warning_logs[0].get("expected_path", ""))


# =============================================================================
# エッジケース
# =============================================================================


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_エッジケース_空のファイル(self, tmp_path: Path) -> None:
        """空のファイルでもエラーなくパースできることを確認。"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text("", encoding="utf-8")

        result = parse_draft(draft_path)

        assert isinstance(result, ArticleDraft)
        assert result.title == ""
        assert result.body_blocks == []
        assert result.frontmatter == {}

    def test_正常系_image_pathsに画像パスが収集される(self, tmp_path: Path) -> None:
        """body_blocks 内の image ブロックのパスが image_paths にも収集されることを確認。"""
        md = """\
# タイトル

![画像1](images/fig1.png)

テキスト段落。

![画像2](images/fig2.png)
"""
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像は article root の images/ に配置
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "fig1.png").write_bytes(b"fake png")
        (images_dir / "fig2.png").write_bytes(b"fake png")

        result = parse_draft(draft_path)

        assert len(result.image_paths) == 2
        assert tmp_path / "images" / "fig1.png" in result.image_paths
        assert tmp_path / "images" / "fig2.png" in result.image_paths

    def test_正常系_titleはfrontmatterのtitleを優先する(self, tmp_path: Path) -> None:
        """frontmatter に title がある場合はそちらを優先することを確認。"""
        md = """\
---
title: frontmatterのタイトル
---

# Markdownのタイトル

本文。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "frontmatterのタイトル"

    def test_正常系_titleはh1見出しから取得される(self, tmp_path: Path) -> None:
        """frontmatter に title がない場合は最初の h1 見出しをタイトルに使うことを確認。"""
        md = """\
---
category: investment
---

# これがタイトル

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "これがタイトル"

    def test_正常系_テーブル画像がimage_pathsに含まれる(self, tmp_path: Path) -> None:
        """テーブルから変換された画像パスも image_paths に含まれることを確認。"""
        md = """\
# タイトル

| A | B |
|---|---|
| 1 | 2 |
"""
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "table_0.png").write_bytes(b"fake")

        result = parse_draft(draft_path)

        assert images_dir / "table_0.png" in result.image_paths


# =============================================================================
# インラインURL削除
# =============================================================================


class TestInlineLinkStripping:
    """インラインリンク [text](url) の除去テスト。"""

    def test_正常系_段落内のインラインリンクがテキストのみになる(
        self, tmp_path: Path
    ) -> None:
        md = """\
# タイトル

純資産総額が[10兆円に到達](https://example.com/source)しました。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert len(paragraphs) == 1
        assert paragraphs[0].content == "純資産総額が10兆円に到達しました。"

    def test_正常系_出典リンクがテキストのみになる(self, tmp_path: Path) -> None:
        md = """\
# タイトル

重要なデータです（出典：[金融庁](https://www.fsa.go.jp/)）。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert paragraphs[0].content == "重要なデータです（出典：金融庁）。"

    def test_正常系_見出し内のリンクも除去される(self, tmp_path: Path) -> None:
        md = """\
# タイトル

## [公式レポート](https://example.com)の要約
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        headings = [b for b in result.body_blocks if b.block_type == "heading"]
        assert headings[0].content == "公式レポートの要約"

    def test_正常系_リスト項目内のリンクも除去される(self, tmp_path: Path) -> None:
        md = """\
# タイトル

- [三菱UFJ銀行](https://www.bk.mufg.jp/)の報告
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        items = [b for b in result.body_blocks if b.block_type == "list_item"]
        assert items[0].content == "三菱UFJ銀行の報告"


# =============================================================================
# ディスクレーマー末尾移動
# =============================================================================


class TestDisclaimerRelocation:
    """免責事項ブロックの末尾移動テスト。"""

    def test_正常系_太字ディスクレーマーが末尾に移動する(self, tmp_path: Path) -> None:
        md = """\
# タイトル

**免責事項**: 本記事は情報提供を目的としており、投資勧誘ではありません。

## 第1章

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 末尾が separator → disclaimer の順
        assert result.body_blocks[-2].block_type == "separator"
        assert result.body_blocks[-1].block_type == "paragraph"
        assert "免責事項" in result.body_blocks[-1].content

        # disclaimer が本文の途中にないことを確認
        non_tail = result.body_blocks[:-2]
        assert all("免責事項" not in b.content for b in non_tail)

    def test_正常系_引用ブロックのディスクレーマーが段落に変換される(
        self, tmp_path: Path
    ) -> None:
        md = """\
# タイトル

## 本文

テキスト。

> **免責事項**: 投資判断は自己責任で行ってください。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # blockquote ではなく paragraph に変換される
        assert result.body_blocks[-1].block_type == "paragraph"
        assert result.body_blocks[-2].block_type == "separator"

    def test_エッジケース_ディスクレーマーがない場合は変更なし(
        self, tmp_path: Path
    ) -> None:
        md = """\
# タイトル

## セクション

本文のみ。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # separator が追加されていないことを確認
        assert result.body_blocks[-1].block_type == "paragraph"
        assert result.body_blocks[-1].content == "本文のみ。"


# =============================================================================
# タイトル本文除去
# =============================================================================


class TestTitleRemovalFromBody:
    """h1 見出しが本文から除去されるテスト。"""

    def test_正常系_h1がbody_blocksに含まれない(self, tmp_path: Path) -> None:
        md = """\
# 記事タイトル

## セクション1

本文。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "記事タイトル"

        h1_blocks = [
            b for b in result.body_blocks if b.block_type == "heading" and b.level == 1
        ]
        assert len(h1_blocks) == 0

    def test_正常系_frontmatterタイトル時もh1は除去される(self, tmp_path: Path) -> None:
        md = """\
---
title: FMタイトル
---

# Markdownタイトル

本文。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "FMタイトル"

        h1_blocks = [
            b for b in result.body_blocks if b.block_type == "heading" and b.level == 1
        ]
        assert len(h1_blocks) == 0


# =============================================================================
# 参考データソース節の除去
# =============================================================================


class TestReferencesSection:
    """``## 参考データソース`` / ``## 参考情報`` 節の除去テスト。"""

    def test_正常系_参考データソース節が除去される(self, tmp_path: Path) -> None:
        """``## 参考データソース`` 見出しとそのリストが body から除外される。"""
        md = """\
# タイトル

## 第1章

本文テキスト。

---

## 参考データソース

- [リンク1](https://example.com/1)
- [リンク2](https://example.com/2)

※ データは2026年4月時点のものです。

---

免責事項: 本記事は情報提供を目的としています。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        all_content = " ".join(b.content for b in result.body_blocks)
        assert "参考データソース" not in all_content
        assert "リンク1" not in all_content
        assert "リンク2" not in all_content
        assert "2026年4月時点" not in all_content

        # 本文は残る
        assert any("本文テキスト" in b.content for b in result.body_blocks)
        # 免責事項は残る（末尾に移動）
        assert any("免責事項" in b.content for b in result.body_blocks)

    def test_正常系_参考情報節も除去される(self, tmp_path: Path) -> None:
        """``## 参考情報`` という別表記の見出しも除去対象。"""
        md = """\
# タイトル

本文。

## 参考情報

- 出典A
- 出典B

免責事項: 投資は自己責任で。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        all_content = " ".join(b.content for b in result.body_blocks)
        assert "参考情報" not in all_content
        assert "出典A" not in all_content
        assert "出典B" not in all_content

    def test_エッジケース_参考セクションがない場合は変更なし(
        self, tmp_path: Path
    ) -> None:
        """参考節が存在しない記事では body が変化しないことを確認。"""
        md = """\
# タイトル

## 本文

通常のテキストのみです。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert any("通常のテキスト" in b.content for b in result.body_blocks)


# =============================================================================
# 免責事項の直前 separator を常に1本だけに統一
# =============================================================================


class TestDisclaimerSeparatorCount:
    """免責事項の直前に置かれる separator が常に1本であることのテスト。"""

    def test_正常系_複数の末尾separatorが1本に統一される(
        self, tmp_path: Path
    ) -> None:
        """参考データソース + 複数 separator + 免責事項 の構造でも、
        note.com 出力は免責事項直前に separator を1本だけ残す。
        """
        md = """\
# タイトル

## 本文

本文テキスト。

---

## 参考データソース

- [リンク](https://example.com)

---

免責事項: 投資は自己責任で。

---
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 免責事項の直前ブロックは separator、その前は非 separator であること
        disclaimer_idx = next(
            i
            for i, b in enumerate(result.body_blocks)
            if "免責事項" in b.content
        )
        assert disclaimer_idx >= 1
        assert result.body_blocks[disclaimer_idx - 1].block_type == "separator"
        if disclaimer_idx >= 2:
            assert result.body_blocks[disclaimer_idx - 2].block_type != "separator"

        # separator の総数は本文内で明示された1本（参考セクション前）を除去 +
        # 免責事項直前の1本のみ → 合計1本
        total_separators = [
            b for b in result.body_blocks if b.block_type == "separator"
        ]
        assert len(total_separators) == 1

    def test_正常系_免責事項直後のseparatorも含めて1本に統一される(
        self, tmp_path: Path
    ) -> None:
        """免責事項の後ろに余分な separator があっても、
        relocate 後は直前1本のみになる。
        """
        md = """\
# タイトル

本文。

---

免責事項: 情報提供のみ。

---

---
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 末尾は [..., separator, disclaimer]
        assert result.body_blocks[-1].block_type == "paragraph"
        assert "免責事項" in result.body_blocks[-1].content
        assert result.body_blocks[-2].block_type == "separator"
        # さらに前は separator であってはならない
        if len(result.body_blocks) >= 3:
            assert result.body_blocks[-3].block_type != "separator"


# =============================================================================
# 連続段落間の空 paragraph 挿入（note.com で1行空ける）
# =============================================================================


class TestParagraphSpacing:
    """連続する paragraph ブロック間に空 paragraph が挿入されるテスト。"""

    def test_正常系_連続段落の間に空paragraphが1つ挿入される(
        self, tmp_path: Path
    ) -> None:
        """note.com 上で1行空けるため、連続する段落の間に
        ``paragraph(content='')`` が1つ挿入される。
        """
        md = """\
# タイトル

段落A。

段落B。

段落C。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 想定される並び: [段落A, 空, 段落B, 空, 段落C]
        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert len(paragraphs) == 5
        assert paragraphs[0].content == "段落A。"
        assert paragraphs[1].content == ""
        assert paragraphs[2].content == "段落B。"
        assert paragraphs[3].content == ""
        assert paragraphs[4].content == "段落C。"

    def test_正常系_段落と見出しの間には空paragraphが入らない(
        self, tmp_path: Path
    ) -> None:
        """``paragraph → heading`` の境界には spacer を挿入しない。"""
        md = """\
# タイトル

段落A。

## 見出し

段落B。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 並び: [段落A, 見出し, 段落B] （空 paragraph は存在しない）
        empty_paragraphs = [
            b
            for b in result.body_blocks
            if b.block_type == "paragraph" and b.content == ""
        ]
        assert len(empty_paragraphs) == 0

    def test_正常系_段落とリストの間には空paragraphが入らない(
        self, tmp_path: Path
    ) -> None:
        """``paragraph → list_item`` の境界には spacer を挿入しない。"""
        md = """\
# タイトル

段落A。

- 項目1
- 項目2

段落B。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        empty_paragraphs = [
            b
            for b in result.body_blocks
            if b.block_type == "paragraph" and b.content == ""
        ]
        assert len(empty_paragraphs) == 0

    def test_エッジケース_単一段落では挿入なし(self, tmp_path: Path) -> None:
        """段落が1つしかない場合は spacer を挿入しない。"""
        md = """\
# タイトル

唯一の段落。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert len(paragraphs) == 1
        assert paragraphs[0].content == "唯一の段落。"
