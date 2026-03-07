"""Playwright browser client for note.com editor automation.

Provides ``NoteBrowserClient``, an async context manager that wraps
Playwright to automate note.com's rich text editor. Handles session
persistence, draft creation, block insertion, image upload, and
draft saving.

Examples
--------
>>> from note_publisher.browser_client import NoteBrowserClient
>>> from note_publisher.config import load_config
>>>
>>> config = load_config()
>>> async with NoteBrowserClient(config) as client:
...     await client.create_new_draft()
...     await client.set_title("My Article")
...     for block in blocks:
...         await client.insert_block(block)
...     draft_url = await client.save_draft()
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from pathlib import Path

    from note_publisher.types import ContentBlock, NotePublisherConfig

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lazy Playwright import
# ---------------------------------------------------------------------------


def _async_playwright() -> Any:
    """Import and return ``async_playwright`` from the playwright package.

    Returns
    -------
    Any
        The ``async_playwright`` context manager object.

    Raises
    ------
    ImportError
        If the ``playwright`` package is not installed.
    """
    try:
        from playwright.async_api import (  # type: ignore[import-not-found]
            async_playwright,
        )

        return async_playwright()
    except ImportError as exc:
        raise ImportError(
            "playwright is not installed. "
            "Install with: uv add playwright && playwright install chromium"
        ) from exc


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------

# AIDEV-NOTE: Selectors are centralised here so that a single update
# propagates to every method that touches the note.com editor UI.
# Keys use snake_case identifiers; values are CSS selectors (or
# data-testid selectors where available).
_SELECTORS: dict[str, str] = {
    "login_button": 'a[href="/login"]',
    "user_menu": '[data-testid="user-menu"], .o-navbarUser',
    "editor_title": 'textarea[placeholder*="タイトル"], .o-editorHeader__titleTextarea',
    "editor_body": 'div[contenteditable="true"]',
    "save_button": 'button:has-text("下書き保存"), [data-testid="save-draft"]',
    "image_upload": 'input[type="file"]',
    "new_draft_url": "https://note.com/notes/new",
}


# ---------------------------------------------------------------------------
# NoteBrowserClient
# ---------------------------------------------------------------------------


class NoteBrowserClient:
    """note.com editor automation client powered by Playwright.

    Use as an async context manager to ensure proper resource cleanup:

        async with NoteBrowserClient(config) as client:
            await client.create_new_draft()
            await client.set_title("Title")
            for block in blocks:
                await client.insert_block(block)
            url = await client.save_draft()

    Parameters
    ----------
    config : NotePublisherConfig
        Publisher configuration (headless mode, timeouts, etc.).

    Attributes
    ----------
    _config : NotePublisherConfig
        Stored configuration.
    _playwright : Any | None
        Playwright instance (set on ``__aenter__``).
    _browser : Any | None
        Browser instance.
    _context : Any | None
        Browser context (carries cookies / storage state).
    _page : Any | None
        Active page used for editor interaction.
    """

    def __init__(self, config: NotePublisherConfig) -> None:
        self._config = config
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> NoteBrowserClient:
        """Start Playwright, launch browser, and create a page.

        Returns
        -------
        NoteBrowserClient
            Self, ready for editor operations.
        """
        logger.debug(
            "browser_client_starting",
            headless=self._config.headless,
            timeout_ms=self._config.timeout_ms,
        )

        pw = await _async_playwright().start()
        self._playwright = pw
        browser = await pw.chromium.launch(
            headless=self._config.headless,
        )
        self._browser = browser
        context = await browser.new_context()
        self._context = context
        self._page = await context.new_page()

        logger.info("browser_client_started")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Shut down browser resources.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type, if any.
        exc_val : BaseException | None
            Exception value, if any.
        exc_tb : Any
            Traceback, if any.
        """
        await self.close()

    async def close(self) -> None:
        """Release all Playwright resources.

        Safe to call multiple times -- subsequent calls are no-ops.
        """
        if self._page is not None:
            await self._page.close()
            self._page = None

        if self._context is not None:
            await self._context.close()
            self._context = None

        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

        logger.debug("browser_client_closed")

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _restore_session(self) -> bool:
        """Restore a previous browser session from the storage state file.

        If the file does not exist or the session is stale (user not
        logged in), returns ``False``.

        Returns
        -------
        bool
            ``True`` if the session was restored **and** the user is
            logged in; ``False`` otherwise.
        """
        state_path = self._config.storage_state_path
        if not state_path.exists():
            logger.debug("no_storage_state_file", path=str(state_path))
            return False

        logger.debug("restoring_session", path=str(state_path))

        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            await self._context.add_cookies(state.get("cookies", []))  # type: ignore[union-attr]
        except Exception:
            logger.warning("session_restore_failed", exc_info=True)
            return False

        # Navigate to note.com and check login status
        assert self._page is not None  # for type checker
        await self._page.goto(
            "https://note.com",
            timeout=self._config.timeout_ms,
        )

        if await self._is_logged_in():
            logger.info("session_restored")
            return True

        logger.info("session_stale")
        return False

    async def wait_for_manual_login(
        self,
        *,
        timeout_sec: int = 120,
    ) -> None:
        """Wait for the user to manually log in via the browser window.

        Opens the note.com login page and polls ``_is_logged_in``
        until the user completes authentication or the timeout elapses.

        Parameters
        ----------
        timeout_sec : int
            Maximum number of seconds to wait for login.

        Raises
        ------
        TimeoutError
            If the user does not log in within ``timeout_sec`` seconds.
        """
        assert self._page is not None

        await self._page.goto(
            "https://note.com/login",
            timeout=self._config.timeout_ms,
        )
        logger.info(
            "waiting_for_manual_login",
            timeout_sec=timeout_sec,
        )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_sec
        while loop.time() < deadline:
            if await self._is_logged_in():
                logger.info("manual_login_succeeded")
                await self._save_session()
                return
            await asyncio.sleep(2)

        raise TimeoutError(f"Manual login not completed within {timeout_sec} seconds")

    async def _save_session(self) -> None:
        """Persist the current browser context storage state to disk.

        Creates parent directories if they do not exist.
        """
        assert self._context is not None

        state = await self._context.storage_state()
        state_path = self._config.storage_state_path
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("session_saved", path=str(state_path))

    async def _is_logged_in(self) -> bool:
        """Check whether the user is logged in to note.com.

        Returns
        -------
        bool
            ``True`` if a logged-in indicator element is found on the
            current page; ``False`` otherwise.
        """
        assert self._page is not None

        try:
            locator = self._page.locator(_SELECTORS["user_menu"])
            count = await locator.count()
            return count > 0
        except Exception:
            logger.debug("login_check_failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Editor operations
    # ------------------------------------------------------------------

    async def create_new_draft(self) -> None:
        """Navigate to the note.com new-draft editor page.

        Waits for the editor body element to appear before returning.
        """
        assert self._page is not None

        url = _SELECTORS["new_draft_url"]
        logger.debug("creating_new_draft", url=url)

        await self._page.goto(url, timeout=self._config.timeout_ms)
        await self._page.wait_for_selector(
            _SELECTORS["editor_body"],
            timeout=self._config.timeout_ms,
        )

        logger.info("new_draft_created")

    async def set_title(self, title: str) -> None:
        """Type a title into the editor title field.

        Parameters
        ----------
        title : str
            The article title text.
        """
        assert self._page is not None

        logger.debug("setting_title", title=title)

        await self._page.fill(
            _SELECTORS["editor_title"],
            title,
        )
        await self._random_delay()

        logger.info("title_set", title=title)

    async def insert_block(self, block: ContentBlock) -> None:
        """Insert a single content block into the editor body.

        Dispatches to the appropriate handler based on ``block.block_type``.

        Parameters
        ----------
        block : ContentBlock
            The content block to insert.
        """
        assert self._page is not None

        logger.debug(
            "inserting_block",
            block_type=block.block_type,
            content_length=len(block.content),
        )

        match block.block_type:
            case "heading":
                await self._insert_heading(block)
            case "paragraph":
                await self._insert_paragraph(block)
            case "list_item":
                await self._insert_list_item(block)
            case "blockquote":
                await self._insert_blockquote(block)
            case "image":
                if block.image_path is not None:
                    await self.upload_image(block.image_path)
            case "separator":
                await self._insert_separator()

        await self._random_delay()

    async def upload_image(self, image_path: Path) -> None:
        """Upload an image file via the editor's file input.

        Parameters
        ----------
        image_path : Path
            Path to the image file to upload.

        Raises
        ------
        FileNotFoundError
            If the image file does not exist.
        """
        assert self._page is not None

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        logger.debug("uploading_image", path=str(image_path))

        file_input = await self._page.query_selector(
            _SELECTORS["image_upload"],
        )
        if file_input is None:
            logger.warning("image_upload_input_not_found")
            return

        await file_input.set_input_files(str(image_path))
        await self._random_delay()

        logger.info("image_uploaded", path=str(image_path))

    async def save_draft(self) -> str:
        """Click the save-draft button and return the draft URL.

        Returns
        -------
        str
            The URL of the saved draft page.
        """
        assert self._page is not None

        logger.debug("saving_draft")

        save_btn = await self._page.wait_for_selector(
            _SELECTORS["save_button"],
            timeout=self._config.timeout_ms,
        )
        await save_btn.click()

        # Wait briefly for the save to register
        await asyncio.sleep(1)

        draft_url: str = self._page.url
        logger.info("draft_saved", url=draft_url)
        return draft_url

    # ------------------------------------------------------------------
    # Private helpers -- block insertion
    # ------------------------------------------------------------------

    async def _insert_heading(self, block: ContentBlock) -> None:
        """Insert a heading block.

        Parameters
        ----------
        block : ContentBlock
            A heading block with ``level`` set (1-3).
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]
        await self._page.click(body_selector)

        # AIDEV-NOTE: note.com's editor uses Enter to create new lines.
        # Headings can be typed as "## text" in some editors, but note.com
        # typically requires formatting buttons. Here we type markdown-style
        # and press Enter as a pragmatic approach.
        level = block.level or 2
        prefix = "#" * level + " "
        await self._page.type(
            body_selector,
            prefix + block.content,
            delay=self._config.typing_delay_ms,
        )
        await self._page.press(body_selector, "Enter")

    async def _insert_paragraph(self, block: ContentBlock) -> None:
        """Insert a paragraph block.

        Parameters
        ----------
        block : ContentBlock
            A paragraph block.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]
        await self._page.type(
            body_selector,
            block.content,
            delay=self._config.typing_delay_ms,
        )
        await self._page.press(body_selector, "Enter")

    async def _insert_list_item(self, block: ContentBlock) -> None:
        """Insert a list item block.

        Parameters
        ----------
        block : ContentBlock
            A list_item block.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]
        await self._page.type(
            body_selector,
            f"- {block.content}",
            delay=self._config.typing_delay_ms,
        )
        await self._page.press(body_selector, "Enter")

    async def _insert_blockquote(self, block: ContentBlock) -> None:
        """Insert a blockquote block.

        Parameters
        ----------
        block : ContentBlock
            A blockquote block.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]
        await self._page.type(
            body_selector,
            f"> {block.content}",
            delay=self._config.typing_delay_ms,
        )
        await self._page.press(body_selector, "Enter")

    async def _insert_separator(self) -> None:
        """Insert a horizontal separator (``---``)."""
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]
        await self._page.type(
            body_selector,
            "---",
            delay=self._config.typing_delay_ms,
        )
        await self._page.press(body_selector, "Enter")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    async def _random_delay(self) -> None:
        """Sleep for a short random duration to reduce bot-detection risk.

        The delay is between 0.1 and 0.3 seconds, scaled by
        ``typing_delay_ms`` (higher delay -> longer pause).
        """
        base = self._config.typing_delay_ms / 1000.0
        jitter = random.uniform(0.1, 0.3)
        await asyncio.sleep(base * jitter)


__all__ = ["_SELECTORS", "NoteBrowserClient"]
