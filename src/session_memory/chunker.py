"""transcript.jsonl を Q&A チャンクに変換するチャンカー.

Claude Code の transcript.jsonl (JSONL形式) を読み込み、
user/assistant のQ&Aペアを Chunk データクラスに変換する。

主な機能:
- ``d['message']['content']`` パスで本文取得
- ``isSidechain=true`` はサブエージェント会話として除外
- 短ターン統合: user_text < 30 文字かつ疑問符なし -> 直前チャンクにマージ
- ``resolve_project()`` で worktree -> 親プロジェクトに解決
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from session_memory._logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_SHORT_TURN_THRESHOLD = 30
"""短ターン統合の閾値（文字数）."""

_WORKTREE_PATTERN = re.compile(r"/.worktrees/([^/]+)/[^/]+$")
"""worktree パスからプロジェクト名を抽出する正規表現."""

# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    """Q&Aペアを表すチャンク.

    Parameters
    ----------
    chunk_key : str
        チャンクの一意識別子（``session_id::N`` 形式）
    session_id : str
        所属するセッションID
    content : str
        Q&Aペアの本文（user + assistant を結合）
    role : str
        チャンクのロール（通常 "assistant"）
    project : str
        解決済みのプロジェクト名
    """

    chunk_key: str
    session_id: str
    content: str
    role: str = "assistant"
    project: str = ""


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


def parse_transcript(lines: list[str]) -> list[Chunk]:
    """transcript.jsonl 行リストを Q&A チャンクに変換する.

    Parameters
    ----------
    lines : list[str]
        transcript.jsonl の各行（JSON文字列）

    Returns
    -------
    list[Chunk]
        Q&Aペアのチャンクリスト
    """
    logger.debug("parse_transcript started", line_count=len(lines))

    # Phase 1: 有効な会話メッセージを抽出
    messages = _extract_messages(lines)
    logger.debug("Messages extracted", message_count=len(messages))

    if not messages:
        logger.debug("No valid messages found, returning empty list")
        return []

    # Phase 2: Q&Aペアを構築
    raw_pairs = _build_qa_pairs(messages)
    logger.debug("Raw QA pairs built", pair_count=len(raw_pairs))

    # Phase 3: 短ターン統合
    merged_pairs = _merge_short_turns(raw_pairs)
    logger.debug("Short turns merged", pair_count=len(merged_pairs))

    # Phase 4: Chunk オブジェクトに変換
    session_id = _resolve_session_id(messages)
    project = _resolve_project_from_messages(messages)
    chunks = _pairs_to_chunks(merged_pairs, session_id=session_id, project=project)

    logger.info(
        "parse_transcript completed",
        input_lines=len(lines),
        output_chunks=len(chunks),
        session_id=session_id,
        project=project,
    )
    return chunks


def resolve_project(cwd: str) -> str:
    """worktree パスを親プロジェクト名に解決する.

    Parameters
    ----------
    cwd : str
        作業ディレクトリのパス

    Returns
    -------
    str
        プロジェクト名。worktree パスの場合は親プロジェクト名、
        それ以外は末尾ディレクトリ名を返す。

    Examples
    --------
    >>> resolve_project("/Users/user/.worktrees/note-finance/feature-prj99")
    'note-finance'
    >>> resolve_project("/Users/user/Desktop/my-project")
    'my-project'
    """
    if not cwd:
        return ""

    match = _WORKTREE_PATTERN.search(cwd)
    if match:
        return match.group(1)

    # 通常パス: 末尾ディレクトリ名を返す
    stripped = cwd.rstrip("/")
    if not stripped:
        return ""
    last_slash = stripped.rfind("/")
    if last_slash == -1:
        return stripped
    return stripped[last_slash + 1 :]


# ---------------------------------------------------------------------------
# 内部関数
# ---------------------------------------------------------------------------


@dataclass
class _Message:
    """抽出済みメッセージの内部表現.

    Parameters
    ----------
    role : str
        メッセージロール（user / assistant）
    content : str
        テキスト本文
    session_id : str
        セッションID
    cwd : str
        作業ディレクトリ
    """

    role: str
    content: str
    session_id: str = ""
    cwd: str = ""


@dataclass
class _QAPair:
    """Q&Aペアの内部表現.

    Parameters
    ----------
    user_text : str
        ユーザーの質問テキスト
    assistant_text : str
        アシスタントの回答テキスト
    session_id : str
        セッションID
    cwd : str
        作業ディレクトリ
    """

    user_text: str
    assistant_text: str = ""
    session_id: str = ""
    cwd: str = ""


def _extract_messages(lines: list[str]) -> list[_Message]:
    """JSONL行リストから有効な会話メッセージを抽出する.

    以下のメッセージは除外される:
    - 不正なJSON行
    - isSidechain=true のメッセージ
    - message キーを持たない行
    - queue-operation 等の非会話行
    - tool_result を含むユーザー行

    Parameters
    ----------
    lines : list[str]
        JSONL行リスト

    Returns
    -------
    list[_Message]
        有効なメッセージのリスト
    """
    messages: list[_Message] = []

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            logger.debug("Skipping invalid JSON line", line_index=i)
            continue

        if not isinstance(data, dict):
            continue

        # queue-operation 等の非会話行をスキップ
        line_type = data.get("type")
        if line_type == "queue-operation":
            logger.debug("Skipping queue-operation line", line_index=i)
            continue

        # isSidechain フィルタリング
        if data.get("isSidechain", False):
            logger.debug("Skipping sidechain message", line_index=i)
            continue

        # message キーの存在チェック
        message = data.get("message")
        if not isinstance(message, dict):
            continue

        role = message.get("role", "")
        if role not in ("user", "assistant"):
            continue

        # content 抽出
        raw_content = message.get("content", "")
        text = _extract_text(raw_content)

        # tool_result のみの行はスキップ
        if not text and _is_tool_result_only(raw_content):
            logger.debug("Skipping tool_result-only line", line_index=i)
            continue

        # 空テキストはスキップ
        if not text:
            continue

        messages.append(
            _Message(
                role=role,
                content=text,
                session_id=data.get("sessionId", ""),
                cwd=data.get("cwd", ""),
            )
        )

    return messages


def _extract_text(content: str | list) -> str:
    """message.content からテキストを抽出する.

    content は文字列または配列形式（content blocks）のどちらかを取る。

    Parameters
    ----------
    content : str | list
        メッセージの content フィールド

    Returns
    -------
    str
        抽出されたテキスト
    """
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type", "")
            # tool_result ブロックは除外
            if block_type == "tool_result":
                continue
            # tool_use ブロックも除外
            if block_type == "tool_use":
                continue
            # text ブロックからテキスト抽出
            if block_type == "text":
                text = block.get("text", "")
                if text:
                    texts.append(text.strip())
        return "\n".join(texts)

    return ""


def _is_tool_result_only(content: str | list) -> bool:
    """content が tool_result のみで構成されているかを判定する.

    Parameters
    ----------
    content : str | list
        メッセージの content フィールド

    Returns
    -------
    bool
        tool_result のみで構成されている場合 True
    """
    if not isinstance(content, list):
        return False

    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            continue
        return False
    return len(content) > 0


def _build_qa_pairs(messages: list[_Message]) -> list[_QAPair]:
    """メッセージリストから Q&A ペアを構築する.

    user メッセージを起点として、続く assistant メッセージを
    1つの Q&A ペアにまとめる。

    Parameters
    ----------
    messages : list[_Message]
        有効なメッセージリスト

    Returns
    -------
    list[_QAPair]
        Q&Aペアのリスト
    """
    pairs: list[_QAPair] = []
    current_pair: _QAPair | None = None

    for msg in messages:
        if msg.role == "user":
            # 前のペアがあれば確定
            if current_pair is not None:
                pairs.append(current_pair)
            current_pair = _QAPair(
                user_text=msg.content,
                session_id=msg.session_id,
                cwd=msg.cwd,
            )
        elif msg.role == "assistant":
            if current_pair is not None:
                # assistant テキストを追加（複数assistant応答をまとめる）
                if current_pair.assistant_text:
                    current_pair.assistant_text += "\n" + msg.content
                else:
                    current_pair.assistant_text = msg.content
            else:
                # user なしの assistant は単独ペアとして扱う
                current_pair = _QAPair(
                    user_text="",
                    assistant_text=msg.content,
                    session_id=msg.session_id,
                    cwd=msg.cwd,
                )

    # 最後のペアを確定
    if current_pair is not None:
        pairs.append(current_pair)

    return pairs


def _is_short_turn(user_text: str) -> bool:
    """ユーザーテキストが短ターン統合の対象かを判定する.

    条件: 30文字未満 かつ 疑問符を含まない

    Parameters
    ----------
    user_text : str
        ユーザーのテキスト

    Returns
    -------
    bool
        短ターン統合対象の場合 True
    """
    if len(user_text) >= _SHORT_TURN_THRESHOLD:
        return False
    # 全角・半角の疑問符をチェック
    return not ("?" in user_text or "\uff1f" in user_text)


def _merge_short_turns(pairs: list[_QAPair]) -> list[_QAPair]:
    """短ターンのQ&Aペアを直前のペアにマージする.

    条件: user_text < 30文字 かつ 疑問符なし -> 直前チャンクにマージ

    Parameters
    ----------
    pairs : list[_QAPair]
        Q&Aペアのリスト

    Returns
    -------
    list[_QAPair]
        マージ後のQ&Aペアリスト
    """
    if not pairs:
        return []

    merged: list[_QAPair] = [pairs[0]]

    for pair in pairs[1:]:
        if _is_short_turn(pair.user_text) and merged:
            # 直前ペアにマージ
            prev = merged[-1]
            merged_user = prev.user_text + "\n" + pair.user_text
            merged_assistant = prev.assistant_text
            if pair.assistant_text:
                if merged_assistant:
                    merged_assistant += "\n" + pair.assistant_text
                else:
                    merged_assistant = pair.assistant_text
            merged[-1] = _QAPair(
                user_text=merged_user,
                assistant_text=merged_assistant,
                session_id=prev.session_id,
                cwd=prev.cwd,
            )
            logger.debug(
                "Short turn merged",
                user_text_len=len(pair.user_text),
                merged_into_index=len(merged) - 1,
            )
        else:
            merged.append(pair)

    return merged


def _resolve_session_id(messages: list[_Message]) -> str:
    """メッセージリストからセッションIDを解決する.

    Parameters
    ----------
    messages : list[_Message]
        メッセージリスト

    Returns
    -------
    str
        セッションID（最初に見つかったもの）
    """
    for msg in messages:
        if msg.session_id:
            return msg.session_id
    return "unknown"


def _resolve_project_from_messages(messages: list[_Message]) -> str:
    """メッセージリストからプロジェクト名を解決する.

    Parameters
    ----------
    messages : list[_Message]
        メッセージリスト

    Returns
    -------
    str
        プロジェクト名
    """
    for msg in messages:
        if msg.cwd:
            return resolve_project(msg.cwd)
    return ""


def _pairs_to_chunks(
    pairs: list[_QAPair],
    *,
    session_id: str,
    project: str,
) -> list[Chunk]:
    """Q&Aペアリストを Chunk リストに変換する.

    Parameters
    ----------
    pairs : list[_QAPair]
        Q&Aペアリスト
    session_id : str
        セッションID
    project : str
        プロジェクト名

    Returns
    -------
    list[Chunk]
        Chunk リスト
    """
    chunks: list[Chunk] = []

    for i, pair in enumerate(pairs):
        # content 構築: user + assistant を結合
        parts: list[str] = []
        if pair.user_text:
            parts.append(f"[user]\n{pair.user_text}")
        if pair.assistant_text:
            parts.append(f"[assistant]\n{pair.assistant_text}")

        content = "\n\n".join(parts)
        if not content:
            continue

        chunk_key = f"{session_id}::{i}"

        chunks.append(
            Chunk(
                chunk_key=chunk_key,
                session_id=session_id,
                content=content,
                role="assistant",
                project=project,
            )
        )

    return chunks


__all__ = [
    "Chunk",
    "parse_transcript",
    "resolve_project",
]
