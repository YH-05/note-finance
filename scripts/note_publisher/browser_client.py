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
    "user_menu": "button.o-navbarPrimary__userIconButton, .o-navbarUser",
    "editor_title": 'textarea[placeholder*="タイトル"], .o-editorHeader__titleTextarea',
    "editor_body": 'div[contenteditable="true"]',
    "save_button": 'button:has-text("下書き保存"), [data-testid="save-draft"]',
    "image_upload": 'input[type="file"]',
    "new_draft_url": "https://note.com/notes/new",
    # AIDEV-NOTE: Heading selectors for note.com editor.
    # 大見出し/小見出し appear in the block-inserter dropdown opened by the "+" button.
    "heading_h2": 'button:has-text("大見出し")',
    "heading_h3": 'button:has-text("小見出し")',
    # "+" button that opens the block-inserter menu (appears on empty lines).
    "add_content_button": 'button[aria-label="メニューを開く"]',
    "bullet_list": 'button:has-text("箇条書きリスト")',
    "numbered_list": 'button:has-text("番号付きリスト")',
    "toc_menu": 'button:has-text("目次")',
    "blockquote_menu": 'button:has-text("引用")',
    "image_add_button": 'button:has-text("画像")',
    "separator_menu": 'button:has-text("区切り線")',
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
        self._in_list: bool = False
        self._in_numbered_list: bool = False

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

        # AIDEV-NOTE: Use channel="chrome" to launch the user's installed
        # Chrome browser instead of Playwright's bundled Chromium.  This
        # prevents Google OAuth from blocking login with "This browser or
        # app may not be secure".  Falls back to bundled Chromium if
        # Chrome is not installed.
        launch_kwargs: dict[str, Any] = {"headless": self._config.headless}
        if not self._config.headless:
            launch_kwargs["channel"] = "chrome"

        try:
            browser = await pw.chromium.launch(**launch_kwargs)
        except Exception:
            logger.warning("chrome_channel_launch_failed_falling_back_to_chromium")
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
            try:
                # AIDEV-NOTE: After OAuth (e.g. Google login), the browser
                # may be on a third-party domain.  Check hostname (not
                # substring) because Google OAuth URLs often include
                # note.com in query parameters like ?continue=...note.com/...
                current_url = self._page.url
                if not current_url.startswith("https://note.com"):
                    logger.debug(
                        "not_on_note_com",
                        current_url=current_url,
                    )
                    await asyncio.sleep(3)
                    continue

                if await self._is_logged_in():
                    logger.info("manual_login_succeeded")
                    await self._save_session()
                    return
            except Exception:
                logger.debug("login_poll_error", exc_info=True)
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
        self._in_list = False
        self._in_numbered_list = False

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

        # リストから非リストへ遷移する際は空Enterでリストを抜ける
        if self._in_list and block.block_type != "list_item":
            await self._page.press(_SELECTORS["editor_body"], "Enter")
            self._in_list = False
        if self._in_numbered_list and block.block_type != "numbered_list_item":
            await self._page.press(_SELECTORS["editor_body"], "Enter")
            self._in_numbered_list = False

        match block.block_type:
            case "heading":
                await self._insert_heading(block)
            case "paragraph":
                await self._insert_paragraph(block)
            case "list_item":
                await self._insert_list_item(block)
            case "numbered_list_item":
                await self._insert_numbered_list_item(block)
            case "toc":
                await self._insert_toc()
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

        Ensures the cursor is on an empty line (where the "+" button
        appears), then opens the block-inserter menu to trigger the
        file input.

        Parameters
        ----------
        image_path : Path
            Path to the image file to upload.
        """
        assert self._page is not None

        if not image_path.exists():
            logger.warning("image_not_found_skipping", path=str(image_path))
            return

        logger.debug("uploading_image", path=str(image_path))

        # AIDEV-NOTE: The "+" block-inserter button only appears on empty
        # paragraph lines.  Wait for the editor to settle after the
        # previous block insertion, then ensure we are on an empty line.
        await asyncio.sleep(0.5)

        file_input = await self._page.query_selector(
            _SELECTORS["image_upload"],
        )

        # If no file input is in the DOM, trigger via the block-inserter menu
        if file_input is None:
            file_input = await self._trigger_image_upload()

        if file_input is None:
            logger.warning("image_upload_input_not_found")
            return

        await file_input.set_input_files(str(image_path))
        # Wait for the image to be processed by the editor
        await asyncio.sleep(2)

        logger.info("image_uploaded", path=str(image_path))

    async def _trigger_image_upload(self) -> Any:
        """Click the "+" menu then "画像" to make the file input available.

        Opens the block-inserter menu first, waits for it to render,
        then clicks the image button to trigger the hidden file input.

        Returns
        -------
        Any
            The file input element if found after clicking, else ``None``.
        """
        assert self._page is not None

        # Step 1: Open the "+" block-inserter menu
        try:
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=5000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(1.0)
                logger.debug("image_trigger_menu_opened")
        except Exception:
            logger.warning("image_trigger_add_button_not_found")
            return None

        # Step 2: Click the "画像" button inside the menu
        try:
            img_btn = await self._page.wait_for_selector(
                _SELECTORS["image_add_button"],
                timeout=5000,
            )
            if img_btn:
                await img_btn.click()
                await asyncio.sleep(1.0)
                logger.debug("image_trigger_image_button_clicked")
        except Exception:
            logger.warning("image_trigger_image_button_not_found")
            return None

        # Step 3: Wait for the file input to appear in DOM.
        # note.com creates file inputs as hidden elements, so we must
        # use state="attached" instead of default "visible".
        try:
            file_input = await self._page.wait_for_selector(
                _SELECTORS["image_upload"],
                state="attached",
                timeout=5000,
            )
            logger.debug("image_trigger_file_input_found")
            return file_input
        except Exception:
            logger.warning("image_trigger_file_input_not_found")
            return None

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
        """Insert a heading block via the block-inserter "+" menu.

        Opens the "+" (メニューを開く) button that appears on an empty line,
        clicks 大見出し (h2) or 小見出し (h3), then types the heading text.
        Falls back to plain paragraph text if the menu cannot be opened.

        Parameters
        ----------
        block : ContentBlock
            A heading block with ``level`` set (1-3).
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]
        level = block.level or 2
        selector_key = "heading_h3" if level >= 3 else "heading_h2"

        inserted = False
        try:
            # Wait for the "+" menu button (visible when cursor is on an empty line)
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=3000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(0.3)
                heading_btn = await self._page.wait_for_selector(
                    _SELECTORS[selector_key],
                    timeout=2000,
                )
                if heading_btn:
                    await heading_btn.click()
                    await asyncio.sleep(0.3)
                    await self._page.type(
                        body_selector,
                        block.content,
                        delay=self._config.typing_delay_ms,
                    )
                    inserted = True
        except Exception:
            logger.debug("block_inserter_heading_failed", level=level)

        if not inserted:
            # Fallback: insert as plain text (avoid literal ### which note.com ignores)
            logger.warning("heading_fallback_plain_text", level=level)
            await self._page.type(
                body_selector,
                block.content,
                delay=self._config.typing_delay_ms,
            )

        await self._page.press(body_selector, "Enter")

    async def _try_toolbar_heading(self, content: str, level: int) -> bool:
        """Try to insert a heading using the editor toolbar.

        Types the text, selects it, then clicks the heading button.

        Parameters
        ----------
        content : str
            Heading text.
        level : int
            Heading level (1-3). 1 is mapped to h2 on note.com.

        Returns
        -------
        bool
            ``True`` if toolbar heading was applied, ``False`` if the
            toolbar button was not found.
        """
        assert self._page is not None

        # Map level to selector: note.com only has h2 (大見出し) and h3 (小見出し)
        selector_key = "heading_h3" if level >= 3 else "heading_h2"
        heading_selector = _SELECTORS[selector_key]

        body_selector = _SELECTORS["editor_body"]

        # Type the content first
        await self._page.click(body_selector)
        await self._page.type(
            body_selector,
            content,
            delay=self._config.typing_delay_ms,
        )

        # Select the typed text (Ctrl/Cmd+A selects within the block on most editors)
        await self._page.keyboard.press("Home")
        await self._page.keyboard.press("Shift+End")

        # Try to click the heading toolbar button
        try:
            heading_btn = await self._page.wait_for_selector(
                heading_selector,
                timeout=2000,
            )
            if heading_btn:
                await heading_btn.click()
                logger.debug("toolbar_heading_applied", level=level)
                # Move cursor to end of line
                await self._page.keyboard.press("End")
                return True
        except Exception:
            logger.debug(
                "toolbar_heading_not_found",
                selector=heading_selector,
                level=level,
            )

        # Undo the typed text so fallback can re-type with markdown prefix
        await self._page.keyboard.press("End")
        await self._page.keyboard.press("Home")
        await self._page.keyboard.press("Shift+End")
        await self._page.keyboard.press("Backspace")

        return False

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

    async def _start_bullet_list(self) -> bool:
        """Open the "+" block-inserter and click 箇条書きリスト.

        Returns
        -------
        bool
            ``True`` if the bullet-list block was successfully started.
        """
        assert self._page is not None

        try:
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=3000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(0.3)
                list_btn = await self._page.wait_for_selector(
                    _SELECTORS["bullet_list"],
                    timeout=2000,
                )
                if list_btn:
                    await list_btn.click()
                    await asyncio.sleep(0.3)
                    return True
        except Exception:
            logger.debug("block_inserter_list_failed")

        return False

    async def _insert_list_item(self, block: ContentBlock) -> None:
        """Insert a list item block via the block-inserter or existing list.

        For the first item, opens the "+" menu and selects 箇条書きリスト.
        For subsequent consecutive items, types directly (already in list mode).
        Falls back to plain paragraph text if the block inserter fails.

        Parameters
        ----------
        block : ContentBlock
            A list_item block.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]

        if not self._in_list:
            started = await self._start_bullet_list()
            if started:
                self._in_list = True
            else:
                logger.warning("list_fallback_plain_text")
                await self._page.type(body_selector, block.content, delay=self._config.typing_delay_ms)
                await self._page.press(body_selector, "Enter")
                return

        await self._page.type(body_selector, block.content, delay=self._config.typing_delay_ms)
        await self._page.press(body_selector, "Enter")

    async def _start_numbered_list(self) -> bool:
        """Open the "+" block-inserter and click 番号付きリスト.

        Returns
        -------
        bool
            ``True`` if the numbered-list block was successfully started.
        """
        assert self._page is not None

        try:
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=3000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(0.3)
                list_btn = await self._page.wait_for_selector(
                    _SELECTORS["numbered_list"],
                    timeout=2000,
                )
                if list_btn:
                    await list_btn.click()
                    await asyncio.sleep(0.3)
                    return True
        except Exception:
            logger.debug("block_inserter_numbered_list_failed")

        return False

    async def _insert_numbered_list_item(self, block: ContentBlock) -> None:
        """Insert a numbered list item via the block-inserter or existing list.

        For the first item, opens the "+" menu and selects 番号付きリスト.
        For subsequent consecutive items, types directly (already in list mode).
        The number prefix must already be stripped from ``block.content``; note.com
        auto-numbers the items.
        Falls back to plain paragraph text if the block inserter fails.

        Parameters
        ----------
        block : ContentBlock
            A numbered_list_item block. ``content`` must NOT include the leading
            ``N. `` number prefix.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]

        if not self._in_numbered_list:
            started = await self._start_numbered_list()
            if started:
                self._in_numbered_list = True
            else:
                logger.warning("numbered_list_fallback_plain_text")
                await self._page.type(body_selector, block.content, delay=self._config.typing_delay_ms)
                await self._page.press(body_selector, "Enter")
                return

        await self._page.type(body_selector, block.content, delay=self._config.typing_delay_ms)
        await self._page.press(body_selector, "Enter")

    async def _insert_toc(self) -> None:
        """Insert a table-of-contents block via the block-inserter "+" menu.

        Opens the "+" (メニューを開く) button and selects 目次.
        note.com automatically generates the TOC from heading blocks in the article.
        Falls back silently if the menu cannot be opened.
        """
        assert self._page is not None

        try:
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=3000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(0.3)
                toc_btn = await self._page.wait_for_selector(
                    _SELECTORS["toc_menu"],
                    timeout=2000,
                )
                if toc_btn:
                    await toc_btn.click()
                    await asyncio.sleep(1.0)
                    # note.com moves cursor to document start after TOC insertion.
                    # Use JavaScript to set DOM selection to document end, then press
                    # End to trigger ProseMirror's selection-sync so subsequent blocks
                    # are inserted after the TOC (not before the intro paragraph).
                    await self._page.evaluate("""
                        () => {
                            const editor = document.querySelector(
                                'div[contenteditable="true"]'
                            );
                            if (!editor) return;
                            editor.focus();
                            const range = document.createRange();
                            range.selectNodeContents(editor);
                            range.collapse(false);
                            const sel = window.getSelection();
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }
                    """)
                    await asyncio.sleep(0.4)
                    # Fire End key so ProseMirror syncs internal cursor with DOM selection
                    await self._page.keyboard.press("End")
                    await asyncio.sleep(0.2)
                    # Press Enter to escape the TOC block and create a new empty paragraph.
                    # The "+" block-inserter button only appears on empty paragraph lines,
                    # so this ensures the next heading block can find and use it.
                    await self._page.press(
                        _SELECTORS["editor_body"], "Enter"
                    )
                    await asyncio.sleep(0.3)
                    return
        except Exception:
            logger.debug("block_inserter_toc_failed")

        logger.warning("toc_insert_failed_skipped")

    async def _insert_blockquote(self, block: ContentBlock) -> None:
        """Insert a blockquote block via the block-inserter "+" menu.

        Opens the "+" (メニューを開く) button and selects 引用, then types
        the blockquote text.  Falls back to plain paragraph text if the menu
        cannot be opened.

        Parameters
        ----------
        block : ContentBlock
            A blockquote block.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]

        inserted = False
        try:
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=3000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(0.3)
                quote_btn = await self._page.wait_for_selector(
                    _SELECTORS["blockquote_menu"],
                    timeout=2000,
                )
                if quote_btn:
                    await quote_btn.click()
                    await asyncio.sleep(0.3)
                    await self._page.type(
                        body_selector,
                        block.content,
                        delay=self._config.typing_delay_ms,
                    )
                    inserted = True
        except Exception:
            logger.debug("block_inserter_blockquote_failed")

        if not inserted:
            logger.warning("blockquote_fallback_plain_text")
            await self._page.type(
                body_selector,
                block.content,
                delay=self._config.typing_delay_ms,
            )

        await self._page.press(body_selector, "Enter")

    async def _insert_separator(self) -> None:
        """Insert a horizontal separator via the block-inserter "+" menu.

        Opens the "+" (メニューを開く) button and selects 区切り線.
        Falls back to typing ``---`` if the menu cannot be opened.
        """
        assert self._page is not None

        body_selector = _SELECTORS["editor_body"]

        inserted = False
        try:
            menu_btn = await self._page.wait_for_selector(
                _SELECTORS["add_content_button"],
                timeout=3000,
            )
            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(0.5)
                sep_btn = await self._page.wait_for_selector(
                    _SELECTORS["separator_menu"],
                    timeout=3000,
                )
                if sep_btn:
                    await sep_btn.click()
                    await asyncio.sleep(0.5)
                    inserted = True
        except Exception:
            logger.debug("block_inserter_separator_failed")

        if not inserted:
            logger.warning("separator_fallback_typing")
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
