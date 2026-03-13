"""Unit tests for note_publisher.types module.

BlockType, ContentBlock, ArticleDraft, PublishResult, NotePublisherConfig の
バリデーションと正常系・異常系・エッジケースを検証する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from note_publisher.types import (
    ArticleDraft,
    ContentBlock,
    NotePublisherConfig,
    PublishResult,
)
from pydantic import ValidationError

from data_paths import get_path

# =============================================================================
# BlockType (Literal 型)
# =============================================================================


class TestBlockType:
    """BlockType Literal 型のテスト。"""

    VALID_BLOCK_TYPES: ClassVar[list[str]] = [
        "heading",
        "paragraph",
        "list_item",
        "blockquote",
        "image",
        "separator",
    ]

    @pytest.mark.parametrize("block_type", VALID_BLOCK_TYPES)
    def test_正常系_有効なブロックタイプでContentBlock生成できる(
        self,
        block_type: str,
    ) -> None:
        """6種類の有効な BlockType で ContentBlock を生成できることを確認。"""
        block = ContentBlock(block_type=block_type, content="test")  # type: ignore[arg-type]
        assert block.block_type == block_type

    def test_異常系_無効なブロックタイプでValidationError(self) -> None:
        """未定義のブロックタイプで ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            ContentBlock(block_type="unknown", content="test")  # type: ignore[arg-type]

    def test_正常系_全6種類が定義されている(self) -> None:
        """BlockType が正確に6種類であることを確認。"""
        assert len(self.VALID_BLOCK_TYPES) == 6


# =============================================================================
# ContentBlock
# =============================================================================


class TestContentBlock:
    """ContentBlock モデルのテスト。"""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        """block_type と content のみで ContentBlock を生成できることを確認。"""
        block = ContentBlock(block_type="paragraph", content="Hello world")

        assert block.block_type == "paragraph"
        assert block.content == "Hello world"
        assert block.level is None
        assert block.image_path is None

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        """全フィールドを指定して ContentBlock を生成できることを確認。"""
        block = ContentBlock(
            block_type="heading",
            content="Section Title",
            level=2,
            image_path=Path("/images/header.png"),
        )

        assert block.block_type == "heading"
        assert block.content == "Section Title"
        assert block.level == 2
        assert block.image_path == Path("/images/header.png")

    def test_正常系_headingにlevelを設定できる(self) -> None:
        """heading タイプに level を設定できることを確認。"""
        block = ContentBlock(block_type="heading", content="Title", level=1)
        assert block.level == 1

    def test_正常系_imageにimage_pathを設定できる(self) -> None:
        """image タイプに image_path を設定できることを確認。"""
        path = Path("assets/photo.jpg")
        block = ContentBlock(
            block_type="image",
            content="Photo caption",
            image_path=path,
        )
        assert block.image_path == path

    def test_正常系_separatorは空contentで生成できる(self) -> None:
        """separator タイプは空文字の content で生成できることを確認。"""
        block = ContentBlock(block_type="separator", content="")
        assert block.content == ""

    def test_異常系_block_type未指定でValidationError(self) -> None:
        """block_type を指定しない場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            ContentBlock(content="test")  # type: ignore[call-arg]

    def test_異常系_content未指定でValidationError(self) -> None:
        """content を指定しない場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            ContentBlock(block_type="paragraph")  # type: ignore[call-arg]

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        """model_dump でシリアライズできることを確認。"""
        block = ContentBlock(block_type="paragraph", content="text")
        data = block.model_dump()

        assert data == {
            "block_type": "paragraph",
            "content": "text",
            "level": None,
            "image_path": None,
        }

    def test_正常系_dictからmodel_validateで生成できる(self) -> None:
        """辞書から model_validate で ContentBlock を生成できることを確認。"""
        data = {"block_type": "blockquote", "content": "A wise quote"}
        block = ContentBlock.model_validate(data)

        assert block.block_type == "blockquote"
        assert block.content == "A wise quote"


# =============================================================================
# ArticleDraft
# =============================================================================


class TestArticleDraft:
    """ArticleDraft モデルのテスト。"""

    def test_正常系_titleのみで生成できる(self) -> None:
        """title のみで ArticleDraft を生成できることを確認。"""
        draft = ArticleDraft(title="Test Article")

        assert draft.title == "Test Article"
        assert draft.body_blocks == []
        assert draft.image_paths == []
        assert draft.frontmatter == {}

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        """全フィールドを指定して ArticleDraft を生成できることを確認。"""
        blocks = [
            ContentBlock(block_type="heading", content="Intro", level=1),
            ContentBlock(block_type="paragraph", content="Body text."),
        ]
        images = [Path("img/photo1.jpg"), Path("img/photo2.png")]
        frontmatter: dict[str, Any] = {
            "tags": ["finance", "tech"],
            "category": "analysis",
        }

        draft = ArticleDraft(
            title="Full Article",
            body_blocks=blocks,
            image_paths=images,
            frontmatter=frontmatter,
        )

        assert draft.title == "Full Article"
        assert len(draft.body_blocks) == 2
        assert draft.body_blocks[0].block_type == "heading"
        assert draft.body_blocks[1].block_type == "paragraph"
        assert len(draft.image_paths) == 2
        assert draft.frontmatter["tags"] == ["finance", "tech"]

    def test_異常系_title未指定でValidationError(self) -> None:
        """title を指定しない場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            ArticleDraft()  # type: ignore[call-arg]

    def test_正常系_body_blocksにネストしたContentBlockを保持できる(self) -> None:
        """body_blocks にネストした ContentBlock のリストを保持できることを確認。"""
        blocks = [
            ContentBlock(block_type="heading", content="H1", level=1),
            ContentBlock(block_type="paragraph", content="Para 1"),
            ContentBlock(block_type="list_item", content="Item 1"),
            ContentBlock(block_type="blockquote", content="Quote"),
            ContentBlock(block_type="image", content="", image_path=Path("a.png")),
            ContentBlock(block_type="separator", content=""),
        ]
        draft = ArticleDraft(title="All Blocks", body_blocks=blocks)

        assert len(draft.body_blocks) == 6

    def test_エッジケース_空のbody_blocksで生成できる(self) -> None:
        """空の body_blocks でも ArticleDraft を生成できることを確認。"""
        draft = ArticleDraft(title="Empty", body_blocks=[])
        assert draft.body_blocks == []

    def test_正常系_frontmatterに任意のデータを格納できる(self) -> None:
        """frontmatter に任意のキーバリューデータを格納できることを確認。"""
        fm: dict[str, Any] = {
            "tags": ["a", "b"],
            "is_premium": False,
            "revision": 3,
            "nested": {"key": "value"},
        }
        draft = ArticleDraft(title="Meta", frontmatter=fm)
        assert draft.frontmatter["nested"] == {"key": "value"}

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        """model_dump でシリアライズできることを確認。"""
        draft = ArticleDraft(title="Dump Test")
        data = draft.model_dump()

        assert data["title"] == "Dump Test"
        assert data["body_blocks"] == []
        assert data["image_paths"] == []
        assert data["frontmatter"] == {}

    def test_正常系_dictからmodel_validateで生成できる(self) -> None:
        """辞書から model_validate で ArticleDraft を生成できることを確認。"""
        data: dict[str, Any] = {
            "title": "From Dict",
            "body_blocks": [
                {"block_type": "paragraph", "content": "text"},
            ],
        }
        draft = ArticleDraft.model_validate(data)

        assert draft.title == "From Dict"
        assert len(draft.body_blocks) == 1
        assert draft.body_blocks[0].content == "text"

    def test_異常系_body_blocksに不正データでValidationError(self) -> None:
        """body_blocks に不正なデータを渡した場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            ArticleDraft.model_validate(
                {
                    "title": "Bad",
                    "body_blocks": [{"block_type": "invalid", "content": "x"}],
                }
            )

    def test_エッジケース_デフォルト値が共有されない(self) -> None:
        """異なるインスタンスのデフォルト値が共有されないことを確認。"""
        draft1 = ArticleDraft(title="A")
        draft2 = ArticleDraft(title="B")

        draft1.body_blocks.append(
            ContentBlock(block_type="paragraph", content="only in draft1")
        )

        assert len(draft1.body_blocks) == 1
        assert len(draft2.body_blocks) == 0


# =============================================================================
# PublishResult
# =============================================================================


class TestPublishResult:
    """PublishResult モデルのテスト。"""

    def test_正常系_成功結果を生成できる(self) -> None:
        """成功時の PublishResult を生成できることを確認。"""
        result = PublishResult(
            success=True,
            draft_url="https://note.com/drafts/123",
        )

        assert result.success is True
        assert result.draft_url == "https://note.com/drafts/123"
        assert result.error_message is None

    def test_正常系_失敗結果を生成できる(self) -> None:
        """失敗時の PublishResult を生成できることを確認。"""
        result = PublishResult(
            success=False,
            error_message="Login failed",
        )

        assert result.success is False
        assert result.draft_url is None
        assert result.error_message == "Login failed"

    def test_正常系_successのみで生成できる(self) -> None:
        """success のみで PublishResult を生成できることを確認。"""
        result = PublishResult(success=True)

        assert result.success is True
        assert result.draft_url is None
        assert result.error_message is None

    def test_異常系_success未指定でValidationError(self) -> None:
        """success を指定しない場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            PublishResult()  # type: ignore[call-arg]

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        """model_dump でシリアライズできることを確認。"""
        result = PublishResult(success=True, draft_url="https://note.com/drafts/456")
        data = result.model_dump()

        assert data == {
            "success": True,
            "draft_url": "https://note.com/drafts/456",
            "error_message": None,
        }

    def test_正常系_成功と失敗の両フィールドを設定できる(self) -> None:
        """draft_url と error_message を同時に設定できることを確認。"""
        result = PublishResult(
            success=False,
            draft_url="https://note.com/drafts/789",
            error_message="Partial failure",
        )

        assert result.draft_url is not None
        assert result.error_message is not None


# =============================================================================
# NotePublisherConfig
# =============================================================================


class TestNotePublisherConfig:
    """NotePublisherConfig モデルのテスト。"""

    def test_正常系_デフォルト値で生成できる(self) -> None:
        """全フィールドにデフォルト値が設定されていることを確認。"""
        config = NotePublisherConfig()

        assert config.headless is True
        assert config.storage_state_path == get_path("config/note-storage-state.json")
        assert config.timeout_ms == 30000
        assert config.typing_delay_ms == 50

    def test_正常系_カスタム値で生成できる(self) -> None:
        """カスタム値で NotePublisherConfig を生成できることを確認。"""
        config = NotePublisherConfig(
            headless=False,
            storage_state_path=Path("/custom/state.json"),
            timeout_ms=60000,
            typing_delay_ms=100,
        )

        assert config.headless is False
        assert config.storage_state_path == Path("/custom/state.json")
        assert config.timeout_ms == 60000
        assert config.typing_delay_ms == 100

    def test_正常系_headlessをFalseに設定できる(self) -> None:
        """headless を False に設定できることを確認。"""
        config = NotePublisherConfig(headless=False)
        assert config.headless is False

    def test_異常系_timeout_msが1000未満でValidationError(self) -> None:
        """timeout_ms が 1000 未満の場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            NotePublisherConfig(timeout_ms=999)

    def test_異常系_timeout_msが0でValidationError(self) -> None:
        """timeout_ms が 0 の場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            NotePublisherConfig(timeout_ms=0)

    def test_異常系_timeout_msが負の値でValidationError(self) -> None:
        """timeout_ms が負の値の場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            NotePublisherConfig(timeout_ms=-1)

    def test_正常系_timeout_msが1000で生成できる(self) -> None:
        """timeout_ms の境界値 1000 で生成できることを確認。"""
        config = NotePublisherConfig(timeout_ms=1000)
        assert config.timeout_ms == 1000

    def test_異常系_typing_delay_msが負の値でValidationError(self) -> None:
        """typing_delay_ms が負の値の場合 ValidationError が発生することを確認。"""
        with pytest.raises(ValidationError):
            NotePublisherConfig(typing_delay_ms=-1)

    def test_正常系_typing_delay_msが0で生成できる(self) -> None:
        """typing_delay_ms の境界値 0 で生成できることを確認。"""
        config = NotePublisherConfig(typing_delay_ms=0)
        assert config.typing_delay_ms == 0

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        """model_dump でシリアライズできることを確認。"""
        config = NotePublisherConfig()
        data = config.model_dump()

        assert data["headless"] is True
        assert data["timeout_ms"] == 30000
        assert data["typing_delay_ms"] == 50

    def test_正常系_dictからmodel_validateで生成できる(self) -> None:
        """辞書から model_validate で NotePublisherConfig を生成できることを確認。"""
        data = {
            "headless": False,
            "storage_state_path": "/tmp/state.json",
            "timeout_ms": 15000,
            "typing_delay_ms": 25,
        }
        config = NotePublisherConfig.model_validate(data)

        assert config.headless is False
        assert config.storage_state_path == Path("/tmp/state.json")
        assert config.timeout_ms == 15000
        assert config.typing_delay_ms == 25

    def test_正常系_storage_state_pathが文字列から変換される(self) -> None:
        """storage_state_path に文字列を渡しても Path に変換されることを確認。"""
        config = NotePublisherConfig(
            storage_state_path="/custom/path.json",  # type: ignore[arg-type]
        )
        assert isinstance(config.storage_state_path, Path)
        assert config.storage_state_path == Path("/custom/path.json")
