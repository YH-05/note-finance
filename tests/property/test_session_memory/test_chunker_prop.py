"""chunker モジュールのプロパティベーステスト.

受け入れ条件:
- Hypothesis で任意入力でクラッシュしないこと
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from session_memory.chunker import Chunk, parse_transcript, resolve_project

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_role_strategy = st.sampled_from(["user", "assistant"])
_sidechain_strategy = st.booleans()
_content_strategy = st.text(min_size=0, max_size=500)
_session_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    min_size=1,
    max_size=50,
)
_cwd_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd", "Po")),
    min_size=1,
    max_size=200,
)


@st.composite
def transcript_line(draw: st.DrawFn) -> str:
    """有効な transcript.jsonl 行を生成する Strategy.

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis の draw 関数

    Returns
    -------
    str
        JSON文字列（1行分）
    """
    role = draw(_role_strategy)
    content = draw(_content_strategy)
    is_sidechain = draw(_sidechain_strategy)
    session_id = draw(_session_id_strategy)
    cwd = draw(_cwd_strategy)

    line = {
        "isSidechain": is_sidechain,
        "cwd": cwd,
        "sessionId": session_id,
        "message": {
            "role": role,
            "content": content,
        },
    }
    return json.dumps(line, ensure_ascii=False)


@st.composite
def transcript_lines(draw: st.DrawFn) -> list[str]:
    """transcript.jsonl 行リストを生成する Strategy.

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis の draw 関数

    Returns
    -------
    list[str]
        JSON文字列のリスト
    """
    return draw(st.lists(transcript_line(), min_size=0, max_size=30))


# ---------------------------------------------------------------------------
# プロパティテスト: parse_transcript
# ---------------------------------------------------------------------------


class TestParseTranscriptProperty:
    """parse_transcript のプロパティテスト."""

    @given(lines=transcript_lines())
    @settings(max_examples=100)
    def test_プロパティ_任意入力でクラッシュしない(self, lines: list[str]) -> None:
        """任意の有効な transcript.jsonl 入力でクラッシュしない."""
        result = parse_transcript(lines)
        assert isinstance(result, list)
        for chunk in result:
            assert isinstance(chunk, Chunk)

    @given(lines=transcript_lines())
    @settings(max_examples=100)
    def test_プロパティ_チャンクは常に有効なroleを持つ(self, lines: list[str]) -> None:
        """出力チャンクの role は常に有効な値."""
        result = parse_transcript(lines)
        valid_roles = {"user", "assistant", "system"}
        for chunk in result:
            assert chunk.role in valid_roles

    @given(lines=transcript_lines())
    @settings(max_examples=100)
    def test_プロパティ_チャンク数は入力メッセージ数以下(
        self, lines: list[str]
    ) -> None:
        """出力チャンク数は入力行数を超えない."""
        result = parse_transcript(lines)
        assert len(result) <= len(lines)

    @given(lines=transcript_lines())
    @settings(max_examples=100)
    def test_プロパティ_チャンクのcontentは空でない(self, lines: list[str]) -> None:
        """生成されたチャンクの content は空文字列でない."""
        result = parse_transcript(lines)
        for chunk in result:
            assert len(chunk.content) > 0

    @given(lines=transcript_lines())
    @settings(max_examples=100)
    def test_プロパティ_chunk_keyはユニーク(self, lines: list[str]) -> None:
        """生成されたチャンクの chunk_key は全てユニーク."""
        result = parse_transcript(lines)
        keys = [chunk.chunk_key for chunk in result]
        assert len(keys) == len(set(keys))

    @given(lines=st.lists(st.text(min_size=0, max_size=200), min_size=0, max_size=20))
    @settings(max_examples=50)
    def test_プロパティ_不正入力でもクラッシュしない(self, lines: list[str]) -> None:
        """完全にランダムな文字列でもクラッシュしない."""
        result = parse_transcript(lines)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# プロパティテスト: resolve_project
# ---------------------------------------------------------------------------


class TestResolveProjectProperty:
    """resolve_project のプロパティテスト."""

    @given(path=st.text(min_size=0, max_size=500))
    @settings(max_examples=100)
    def test_プロパティ_任意パスでクラッシュしない(self, path: str) -> None:
        """任意のパス文字列でクラッシュしない."""
        result = resolve_project(path)
        assert isinstance(result, str)

    @given(
        project=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
            min_size=1,
            max_size=50,
        ),
        branch=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(max_examples=50)
    def test_プロパティ_worktreeパスは常にプロジェクト名を返す(
        self, project: str, branch: str
    ) -> None:
        """worktree パスからは常に親プロジェクト名が抽出される."""
        path = f"/Users/user/.worktrees/{project}/{branch}"
        result = resolve_project(path)
        assert result == project
