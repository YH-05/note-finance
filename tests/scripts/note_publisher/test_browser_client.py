"""Unit tests for NoteBrowserClient.

This module tests the NoteBrowserClient class to ensure:
- It correctly implements async context manager protocol
- Session management (restore, save, login check) works as expected
- Editor operations (create draft, set title, insert block, etc.) work
- close() is safe to call multiple times
- Error handling works correctly
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from note_publisher.types import ContentBlock, NotePublisherConfig

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config(tmp_path: Path) -> NotePublisherConfig:
    """Create a NotePublisherConfig with tmp storage state path."""
    return NotePublisherConfig(
        headless=True,
        storage_state_path=tmp_path / "storage-state.json",
        timeout_ms=30000,
        typing_delay_ms=50,
    )


@pytest.fixture
def mock_page() -> MagicMock:
    """Create a mock Playwright Page."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.type = AsyncMock()
    page.press = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_url = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.set_input_files = AsyncMock()
    page.url = "https://note.com/some_page"
    page.close = AsyncMock()
    page.evaluate = AsyncMock()

    # keyboard mock for heading toolbar operations
    keyboard_mock = MagicMock()
    keyboard_mock.press = AsyncMock()
    page.keyboard = keyboard_mock

    # AIDEV-NOTE: locator() returns a Locator mock that supports
    # .first and async .inner_text() so that _is_logged_in()
    # can check for a logged-in indicator element.
    locator_mock = MagicMock()
    locator_mock.first = MagicMock()
    locator_mock.first.inner_text = AsyncMock(return_value="")
    locator_mock.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=locator_mock)

    return page


@pytest.fixture
def mock_context(mock_page: MagicMock) -> MagicMock:
    """Create a mock Playwright BrowserContext."""
    context = MagicMock()
    context.new_page = AsyncMock(return_value=mock_page)
    context.close = AsyncMock()
    context.storage_state = AsyncMock(return_value={"cookies": [], "origins": []})
    context.add_cookies = AsyncMock()
    return context


@pytest.fixture
def mock_browser(mock_context: MagicMock) -> MagicMock:
    """Create a mock Playwright Browser."""
    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=mock_context)
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_playwright_instance(mock_browser: MagicMock) -> MagicMock:
    """Create a mock Playwright instance."""
    pw = MagicMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=mock_browser)
    pw.stop = AsyncMock()
    return pw


@pytest.fixture
def _patch_playwright(mock_playwright_instance: MagicMock) -> Any:
    """Patch async_playwright to return our mock instance.

    Yields the mock so tests can introspect calls if needed.
    """
    mock_cm = MagicMock()
    mock_cm.start = AsyncMock(return_value=mock_playwright_instance)

    with patch(
        "note_publisher.browser_client._async_playwright",
        return_value=mock_cm,
    ):
        yield mock_cm


# ---------------------------------------------------------------------------
# Tests: Context Manager
# ---------------------------------------------------------------------------


class TestNoteBrowserClientContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_コンテキストマネージャでブラウザが起動する(
        self,
        config: NotePublisherConfig,
        mock_browser: MagicMock,
    ) -> None:
        """Browser should be launched when entering the context manager."""
        from note_publisher.browser_client import NoteBrowserClient

        async with NoteBrowserClient(config) as client:
            assert client._browser is not None

        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_コンテキストマネージャ終了でリソースが解放される(
        self,
        config: NotePublisherConfig,
        mock_browser: MagicMock,
        mock_playwright_instance: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Resources should be released when exiting the context manager."""
        from note_publisher.browser_client import NoteBrowserClient

        async with NoteBrowserClient(config):
            pass

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_closeの二重呼び出しが安全(
        self,
        config: NotePublisherConfig,
        mock_browser: MagicMock,
    ) -> None:
        """Calling close() twice should not raise an error."""
        from note_publisher.browser_client import NoteBrowserClient

        client = NoteBrowserClient(config)
        await client.__aenter__()
        await client.close()
        await client.close()  # second call is safe

        mock_browser.close.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Session Management
# ---------------------------------------------------------------------------


class TestNoteBrowserClientSession:
    """Tests for session management methods."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_ストレージステートが存在する場合セッション復元(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """_restore_session should return True when storage state file exists and login succeeds."""
        from note_publisher.browser_client import NoteBrowserClient

        # Write a dummy storage state file
        config.storage_state_path.write_text(
            json.dumps({"cookies": [{"name": "sid", "value": "abc"}], "origins": []}),
        )

        # Mock _is_logged_in to return True
        async with NoteBrowserClient(config) as client:
            with patch.object(client, "_is_logged_in", return_value=True):
                result = await client._restore_session()

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_ストレージステートが存在しない場合復元スキップ(
        self,
        config: NotePublisherConfig,
    ) -> None:
        """_restore_session should return False when no storage state file."""
        from note_publisher.browser_client import NoteBrowserClient

        async with NoteBrowserClient(config) as client:
            result = await client._restore_session()

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_save_sessionでストレージステートを保存(
        self,
        config: NotePublisherConfig,
        mock_context: MagicMock,
    ) -> None:
        """_save_session should write the storage state to disk."""
        from note_publisher.browser_client import NoteBrowserClient

        dummy_state = {"cookies": [{"name": "sid"}], "origins": []}
        mock_context.storage_state = AsyncMock(return_value=dummy_state)

        async with NoteBrowserClient(config) as client:
            await client._save_session()

        assert config.storage_state_path.exists()
        saved = json.loads(config.storage_state_path.read_text())
        assert saved == dummy_state

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_is_logged_inがログイン状態を検出(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """_is_logged_in should return True when the user menu is found."""
        from note_publisher.browser_client import NoteBrowserClient

        # Simulate the logged-in indicator being present
        locator_mock = MagicMock()
        locator_mock.count = AsyncMock(return_value=1)
        mock_page.locator = MagicMock(return_value=locator_mock)

        async with NoteBrowserClient(config) as client:
            result = await client._is_logged_in()

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_is_logged_inが未ログイン状態を検出(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """_is_logged_in should return False when the user menu is absent."""
        from note_publisher.browser_client import NoteBrowserClient

        locator_mock = MagicMock()
        locator_mock.count = AsyncMock(return_value=0)
        mock_page.locator = MagicMock(return_value=locator_mock)

        async with NoteBrowserClient(config) as client:
            result = await client._is_logged_in()

        assert result is False


# ---------------------------------------------------------------------------
# Tests: Editor Operations
# ---------------------------------------------------------------------------


class TestNoteBrowserClientEditorOperations:
    """Tests for editor manipulation methods."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_create_new_draftでエディタページに遷移(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """create_new_draft should navigate to the note.com editor page."""
        from note_publisher.browser_client import NoteBrowserClient

        async with NoteBrowserClient(config) as client:
            await client.create_new_draft()

        mock_page.goto.assert_called()
        call_args = mock_page.goto.call_args
        assert "note.com" in call_args[0][0]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_set_titleでタイトルを入力(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """set_title should type the title into the title field."""
        from note_publisher.browser_client import NoteBrowserClient

        async with NoteBrowserClient(config) as client:
            await client.set_title("テスト記事タイトル")

        # Should have interacted with the page (fill or type)
        assert mock_page.fill.called or mock_page.type.called

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_insert_blockで段落ブロックを挿入(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """insert_block should insert a paragraph content block."""
        from note_publisher.browser_client import NoteBrowserClient

        block = ContentBlock(block_type="paragraph", content="テスト段落です。")

        async with NoteBrowserClient(config) as client:
            await client.insert_block(block)

        # Should have used type or keyboard to input text
        assert mock_page.type.called or mock_page.press.called or mock_page.fill.called

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_insert_blockで見出しブロックを挿入(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """insert_block should handle heading blocks."""
        from note_publisher.browser_client import NoteBrowserClient

        block = ContentBlock(block_type="heading", content="テスト見出し", level=2)

        async with NoteBrowserClient(config) as client:
            await client.insert_block(block)

        # The method should complete without error
        assert mock_page.type.called or mock_page.press.called or mock_page.fill.called

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_upload_imageで画像をアップロード(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
        tmp_path: Path,
    ) -> None:
        """upload_image should trigger a file upload via the file input."""
        from note_publisher.browser_client import NoteBrowserClient

        image_path = tmp_path / "test.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        # Mock the file input element
        file_input_mock = MagicMock()
        file_input_mock.set_input_files = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=file_input_mock)

        async with NoteBrowserClient(config) as client:
            await client.upload_image(image_path)

        file_input_mock.set_input_files.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_playwright")
    async def test_正常系_save_draftで下書きURLを返す(
        self,
        config: NotePublisherConfig,
        mock_page: MagicMock,
    ) -> None:
        """save_draft should click save and return the current URL."""
        from note_publisher.browser_client import NoteBrowserClient

        mock_page.url = "https://note.com/api/v2/drafts/n123abc"

        # Mock click for save button
        save_btn_mock = MagicMock()
        save_btn_mock.click = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=save_btn_mock)

        async with NoteBrowserClient(config) as client:
            url = await client.save_draft()

        assert "note.com" in url


# ---------------------------------------------------------------------------
# Tests: Selectors constant
# ---------------------------------------------------------------------------


class TestNoteBrowserClientSelectors:
    """Tests for the _SELECTORS constant."""

    def test_正常系_SELECTORSが辞書として定義されている(self) -> None:
        """_SELECTORS should be a dict[str, str]."""
        from note_publisher.browser_client import _SELECTORS

        assert isinstance(_SELECTORS, dict)
        assert len(_SELECTORS) > 0
        for key, value in _SELECTORS.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_正常系_必須セレクタキーが定義されている(self) -> None:
        """_SELECTORS should contain essential keys for editor operations."""
        from note_publisher.browser_client import _SELECTORS

        essential_keys = {
            "editor_title",
            "editor_body",
            "save_button",
            "image_upload",
        }
        for key in essential_keys:
            assert key in _SELECTORS, f"Missing selector key: {key}"
