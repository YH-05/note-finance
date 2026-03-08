"""Orchestrator for publishing article drafts to note.com.

Coordinates ``markdown_parser`` (pure logic) and ``browser_client``
(side effects) to handle the full flow: locate the revised draft,
parse it, launch a browser, log in, create a draft, insert blocks,
upload images, and save.

Error Codes
-----------
E001
    ``revised_draft.md`` not found in the article directory.
E002
    Markdown parse error.
E003
    Browser launch / connection error.
E004
    note.com login error.
E005
    Draft save error.

Examples
--------
>>> from note_publisher.draft_publisher import DraftPublisher
>>> publisher = DraftPublisher()
>>> draft = publisher.dry_run(Path("articles/example"))
>>> draft.title
'記事タイトル'
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import structlog
from note_publisher.browser_client import NoteBrowserClient
from note_publisher.config import load_config
from note_publisher.markdown_parser import parse_draft
from note_publisher.types import ArticleDraft, NotePublisherConfig, PublishResult

logger = structlog.get_logger(__name__)

# AIDEV-NOTE: The revised draft is always located at
# article_dir / "02_edit" / "revised_draft.md" by convention.
_DRAFT_RELATIVE_PATH = Path("02_edit") / "revised_draft.md"


class DraftPublisher:
    """note.com draft publishing orchestrator.

    Coordinates Markdown parsing and Playwright browser automation to
    publish article drafts to note.com.

    Parameters
    ----------
    config : NotePublisherConfig | None
        Publisher configuration.  When ``None``, ``load_config()`` is
        called to obtain the configuration from environment variables
        and defaults.

    Examples
    --------
    >>> publisher = DraftPublisher()
    >>> draft = publisher.dry_run(Path("articles/my-article"))
    >>> draft.title
    'My Article'
    """

    def __init__(self, config: NotePublisherConfig | None = None) -> None:
        self._config = config or load_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dry_run(self, article_dir: Path) -> ArticleDraft:
        """Parse the Markdown draft without browser operations.

        Parameters
        ----------
        article_dir : Path
            Path to the article directory. The draft file is expected at
            ``article_dir / "02_edit" / "revised_draft.md"``.

        Returns
        -------
        ArticleDraft
            Parsed article draft.

        Raises
        ------
        FileNotFoundError
            ``E001`` -- ``revised_draft.md`` not found.
        ValueError
            ``E002`` -- Markdown parse error.
        """
        logger.info("dry_run_started", article_dir=str(article_dir))

        draft_path = article_dir / _DRAFT_RELATIVE_PATH
        self._validate_draft_exists(draft_path)

        try:
            draft = parse_draft(draft_path)
        except Exception as exc:
            error_msg = f"E002: Markdownパースエラー: {exc}"
            logger.error("dry_run_parse_error", error=str(exc))
            raise ValueError(error_msg) from exc

        logger.info(
            "dry_run_completed",
            title=draft.title,
            block_count=len(draft.body_blocks),
        )
        return draft

    async def publish(
        self,
        article_dir: Path,
        *,
        update_meta: bool = True,
    ) -> PublishResult:
        """Publish an article draft to note.com.

        Performs the full flow: locate draft -> parse -> launch browser
        -> authenticate -> create draft -> insert blocks -> save.

        Parameters
        ----------
        article_dir : Path
            Path to the article directory. The draft file is expected at
            ``article_dir / "02_edit" / "revised_draft.md"``.
        update_meta : bool
            Whether to update article metadata after publishing.
            When ``True``, updates ``article-meta.json`` (status,
            published_at, draft_url) and copies the draft to
            ``03_published/article.md``.  Defaults to ``True``.

        Returns
        -------
        PublishResult
            Outcome of the publish operation.  On failure,
            ``success=False`` and ``error_message`` contains the error
            code and description.
        """
        logger.info(
            "publish_started",
            article_dir=str(article_dir),
            update_meta=update_meta,
        )

        # --- Step 1: Locate the draft file (E001) ---
        draft_path = article_dir / _DRAFT_RELATIVE_PATH
        try:
            self._validate_draft_exists(draft_path)
        except FileNotFoundError as exc:
            logger.error("publish_draft_not_found", path=str(draft_path))
            return PublishResult(success=False, error_message=str(exc))

        # --- Step 2: Parse the draft (E002) ---
        try:
            draft = parse_draft(draft_path)
        except Exception as exc:
            error_msg = f"E002: Markdownパースエラー: {exc}"
            logger.error("publish_parse_error", error=str(exc))
            return PublishResult(success=False, error_message=error_msg)

        logger.info(
            "publish_draft_parsed",
            title=draft.title,
            block_count=len(draft.body_blocks),
        )

        # --- Step 3-6: Browser operations ---
        result = await self._execute_browser_publish(draft)

        # --- Step 7: Update article metadata ---
        if result.success and update_meta:
            self._update_article_meta(article_dir, result.draft_url)
            self._copy_to_published(article_dir)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_draft_exists(draft_path: Path) -> None:
        """Validate that the draft file exists.

        Parameters
        ----------
        draft_path : Path
            Expected path to the draft file.

        Raises
        ------
        FileNotFoundError
            ``E001`` if the file does not exist.
        """
        if not draft_path.exists():
            error_msg = f"E001: revised_draft.md が見つかりません: {draft_path}"
            logger.error("draft_not_found", path=str(draft_path))
            raise FileNotFoundError(error_msg)

    @staticmethod
    def _update_article_meta(article_dir: Path, draft_url: str | None) -> None:
        """Update article-meta.json after successful publish.

        Sets ``status`` to ``"published"``, records ``published_at``
        timestamp, stores the ``draft_url``, and marks
        ``workflow.publishing.published`` as ``"done"``.

        Parameters
        ----------
        article_dir : Path
            Path to the article directory.
        draft_url : str | None
            URL of the created draft on note.com.
        """
        meta_path = article_dir / "article-meta.json"
        if not meta_path.exists():
            logger.warning("article_meta_not_found", path=str(meta_path))
            return

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("article_meta_read_error", error=str(exc))
            return

        now = datetime.now(timezone.utc).isoformat()
        meta["status"] = "published"
        meta["published_at"] = now
        meta["updated_at"] = now
        if draft_url:
            meta["draft_url"] = draft_url

        # Update workflow.publishing
        workflow = meta.get("workflow", {})
        publishing = workflow.get("publishing", {})
        publishing["published"] = "done"
        publishing["final_review"] = "done"
        workflow["publishing"] = publishing
        meta["workflow"] = workflow

        try:
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8",
            )
            logger.info("article_meta_updated", path=str(meta_path), status="published")
        except OSError as exc:
            logger.error("article_meta_write_error", error=str(exc))

    @staticmethod
    def _copy_to_published(article_dir: Path) -> None:
        """Copy revised_draft.md to 03_published/article.md.

        Parameters
        ----------
        article_dir : Path
            Path to the article directory.
        """
        src = article_dir / "02_edit" / "revised_draft.md"
        dest_dir = article_dir / "03_published"
        dest = dest_dir / "article.md"

        if not src.exists():
            logger.warning("revised_draft_not_found_for_copy", path=str(src))
            return

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        logger.info("draft_copied_to_published", src=str(src), dest=str(dest))

    async def _execute_browser_publish(
        self,
        draft: ArticleDraft,
    ) -> PublishResult:
        """Run browser operations to publish the draft.

        Parameters
        ----------
        draft : ArticleDraft
            Parsed article draft.

        Returns
        -------
        PublishResult
            Outcome of the browser publish operation.
        """
        try:
            async with NoteBrowserClient(self._config) as client:
                # --- Step 4: Authenticate (E004) ---
                try:
                    session_ok = await client._restore_session()
                    if not session_ok:
                        await client.wait_for_manual_login()
                except (TimeoutError, Exception) as exc:
                    error_msg = f"E004: note.com ログインエラー: {exc}"
                    logger.error("publish_login_error", error=str(exc))
                    return PublishResult(success=False, error_message=error_msg)

                # --- Step 5: Create draft and insert content (E005) ---
                try:
                    await client.create_new_draft()
                    await client.set_title(draft.title)

                    for block in draft.body_blocks:
                        await client.insert_block(block)

                    draft_url = await client.save_draft()
                except Exception as exc:
                    error_msg = f"E005: 下書き保存エラー: {exc}"
                    logger.error("publish_save_error", error=str(exc))
                    return PublishResult(success=False, error_message=error_msg)
        except (ConnectionError, OSError, ImportError, Exception) as exc:
            error_msg = f"E003: ブラウザ起動/接続エラー: {exc}"
            logger.error("publish_browser_error", error=str(exc))
            return PublishResult(success=False, error_message=error_msg)

        logger.info("publish_completed", draft_url=draft_url)
        return PublishResult(success=True, draft_url=draft_url)


__all__ = ["DraftPublisher"]
