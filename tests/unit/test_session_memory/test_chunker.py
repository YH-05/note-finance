"""chunker モジュールのユニットテスト.

受け入れ条件:
- parse_transcript() が user/assistant メッセージのみを Chunk に変換すること
- isSidechain=true はサブエージェント会話として除外
- 短ターン統合: user_text < 30 文字かつ疑問符なし -> 直前チャンクにマージ
- resolve_project() で worktree -> 親プロジェクトに解決
"""

import json

from session_memory.chunker import Chunk, parse_transcript, resolve_project

# ---------------------------------------------------------------------------
# テストデータヘルパー
# ---------------------------------------------------------------------------


def _make_line(
    *,
    role: str = "user",
    content: str = "Hello",
    is_sidechain: bool = False,
    cwd: str = "/Users/user/project",
    session_id: str = "session-001",
    msg_type: str | None = None,
) -> str:
    """transcript.jsonl の1行を生成するヘルパー.

    Parameters
    ----------
    role : str
        メッセージのロール
    content : str
        メッセージ本文
    is_sidechain : bool
        サブエージェント会話フラグ
    cwd : str
        作業ディレクトリ
    session_id : str
        セッションID
    msg_type : str | None
        行レベルの type フィールド（"user" / "queue-operation" など）

    Returns
    -------
    str
        JSON文字列（1行分）
    """
    line: dict = {
        "isSidechain": is_sidechain,
        "cwd": cwd,
        "sessionId": session_id,
        "message": {
            "role": role,
            "content": content,
        },
    }
    if msg_type is not None:
        line["type"] = msg_type
    return json.dumps(line, ensure_ascii=False)


def _make_content_blocks(text: str) -> list[dict]:
    """content を配列形式で返す.

    Parameters
    ----------
    text : str
        テキスト内容

    Returns
    -------
    list[dict]
        content blocks 配列
    """
    return [{"type": "text", "text": text}]


def _make_tool_result_line(
    *,
    tool_use_id: str = "toolu_abc123",
    content: str = "tool result",
    cwd: str = "/Users/user/project",
    session_id: str = "session-001",
) -> str:
    """ツール結果行を生成するヘルパー.

    Parameters
    ----------
    tool_use_id : str
        ツール使用ID
    content : str
        ツール結果内容
    cwd : str
        作業ディレクトリ
    session_id : str
        セッションID

    Returns
    -------
    str
        JSON文字列（1行分）
    """
    return json.dumps(
        {
            "isSidechain": False,
            "cwd": cwd,
            "sessionId": session_id,
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "tool_use_id": tool_use_id,
                        "type": "tool_result",
                        "content": content,
                    }
                ],
            },
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# parse_transcript テスト
# ---------------------------------------------------------------------------


class TestParseTranscript:
    """parse_transcript の基本動作テスト."""

    def test_正常系_user_assistantメッセージがChunkに変換される(self) -> None:
        """user と assistant の会話が Q&A チャンクに変換される."""
        lines = [
            _make_line(role="user", content="Pythonについて教えてください"),
            _make_line(
                role="assistant", content="Pythonは汎用プログラミング言語です。"
            ),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) >= 1
        # user と assistant がペアになっているか確認
        first_chunk = chunks[0]
        assert "Pythonについて教えてください" in first_chunk.content
        assert "Pythonは汎用プログラミング言語です" in first_chunk.content

    def test_正常系_複数QAペアが変換される(self) -> None:
        """複数のQ&Aペアがそれぞれのチャンクになる."""
        lines = [
            _make_line(
                role="user",
                content="Pythonの型ヒントについて詳しく教えてください。PEP 484の詳細が知りたいです",
            ),
            _make_line(role="assistant", content="型ヒントはPEP 484で導入されました。"),
            _make_line(
                role="user",
                content="次にPydanticのBaseModelの使い方について具体的に説明してください",
            ),
            _make_line(role="assistant", content="PydanticのBaseModelは..."),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 2
        assert "型ヒント" in chunks[0].content
        assert "PEP 484" in chunks[0].content
        assert "Pydantic" in chunks[1].content
        assert "BaseModel" in chunks[1].content

    def test_正常系_content配列形式のメッセージが処理される(self) -> None:
        """message.content が配列形式でも正しくテキスト抽出される."""
        line_data = {
            "isSidechain": False,
            "cwd": "/Users/user/project",
            "sessionId": "session-001",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "これは回答です。"},
                    {"type": "text", "text": "続きの回答です。"},
                ],
            },
        }
        lines = [
            _make_line(role="user", content="質問です"),
            json.dumps(line_data, ensure_ascii=False),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1
        assert "これは回答です" in chunks[0].content
        assert "続きの回答です" in chunks[0].content

    def test_正常系_session_idが設定される(self) -> None:
        """チャンクにセッションIDが正しく設定される."""
        lines = [
            _make_line(role="user", content="質問", session_id="test-session-42"),
            _make_line(role="assistant", content="回答", session_id="test-session-42"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1
        assert chunks[0].session_id == "test-session-42"

    def test_正常系_chunk_keyが連番で生成される(self) -> None:
        """chunk_key が session_id::N の形式で連番生成される."""
        lines = [
            _make_line(
                role="user",
                content="Pythonのデコレータについて詳しく教えてください。具体的な例も示してほしいです",
            ),
            _make_line(
                role="assistant", content="デコレータは関数を装飾するパターンです。"
            ),
            _make_line(
                role="user",
                content="次にジェネレータの使い方について詳しく解説してください。yield文の動作を理解したいです",
            ),
            _make_line(role="assistant", content="ジェネレータはyieldを使います。"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 2
        assert "::0" in chunks[0].chunk_key
        assert "::1" in chunks[1].chunk_key

    def test_正常系_roleがassistantに設定される(self) -> None:
        """Q&Aチャンクのroleはassistantとして記録される."""
        lines = [
            _make_line(role="user", content="質問"),
            _make_line(role="assistant", content="回答"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1
        assert chunks[0].role == "assistant"


class TestSidechainFiltering:
    """isSidechain フィルタリングのテスト."""

    def test_正常系_sidechainメッセージが除外される(self) -> None:
        """isSidechain=true のメッセージは除外される."""
        lines = [
            _make_line(
                role="user",
                content="メインの質問です。Pythonのasync/awaitについて詳しく教えてください",
            ),
            _make_line(
                role="assistant", content="メインの回答です。asyncは非同期処理..."
            ),
            _make_line(
                role="user", content="サブエージェントの質問", is_sidechain=True
            ),
            _make_line(
                role="assistant", content="サブエージェントの回答", is_sidechain=True
            ),
            _make_line(
                role="user",
                content="次のメインの質問です。データベースの接続プーリングについて教えてください",
            ),
            _make_line(
                role="assistant", content="次のメインの回答です。接続プーリングは..."
            ),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 2
        for chunk in chunks:
            assert "サブエージェント" not in chunk.content

    def test_正常系_全てsidechainの場合は空リスト(self) -> None:
        """全メッセージが sidechain の場合は空リストを返す."""
        lines = [
            _make_line(role="user", content="サブ質問", is_sidechain=True),
            _make_line(role="assistant", content="サブ回答", is_sidechain=True),
        ]
        chunks = parse_transcript(lines)
        assert chunks == []


class TestShortTurnMerging:
    """短ターン統合のテスト."""

    def test_正常系_短いユーザーメッセージが直前チャンクにマージされる(self) -> None:
        """30文字未満・疑問符なしのユーザーメッセージは直前チャンクにマージ."""
        lines = [
            _make_line(role="user", content="Pythonの型ヒントについて教えてください"),
            _make_line(role="assistant", content="型ヒントはPEP 484で導入されました。"),
            _make_line(role="user", content="なるほど"),  # 短い、疑問符なし -> マージ
            _make_line(role="assistant", content="さらに詳しく説明すると..."),
        ]
        chunks = parse_transcript(lines)
        # 短ターンが直前にマージされるので1チャンクになる
        assert len(chunks) == 1
        assert "型ヒント" in chunks[0].content
        assert "なるほど" in chunks[0].content
        assert "さらに詳しく説明すると" in chunks[0].content

    def test_正常系_疑問符付きの短いメッセージはマージされない(self) -> None:
        """30文字未満でも疑問符があれば新規チャンクになる."""
        lines = [
            _make_line(role="user", content="Pythonについて教えてください"),
            _make_line(role="assistant", content="Pythonは汎用言語です。"),
            _make_line(
                role="user", content="例えば？"
            ),  # 短いが疑問符あり -> 新チャンク
            _make_line(role="assistant", content="Webアプリ開発などに使えます。"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 2

    def test_正常系_30文字以上のメッセージはマージされない(self) -> None:
        """30文字以上のユーザーメッセージは常に新規チャンクになる."""
        long_question = (
            "これは30文字以上の長いユーザーメッセージで新しい質問を含んでいます"
        )
        assert len(long_question) >= 30  # テスト前提条件の確認
        lines = [
            _make_line(role="user", content="最初の質問"),
            _make_line(role="assistant", content="最初の回答"),
            _make_line(role="user", content=long_question),
            _make_line(role="assistant", content="次の回答"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 2

    def test_正常系_直前チャンクがない場合はマージしない(self) -> None:
        """最初のメッセージが短くても新規チャンクとして扱う."""
        lines = [
            _make_line(role="user", content="はい"),  # 短いが最初なのでマージ不可
            _make_line(role="assistant", content="何かお手伝いできますか？"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1


class TestEdgeCases:
    """エッジケースのテスト."""

    def test_エッジケース_空入力で空リスト(self) -> None:
        """空のリストを渡すと空リストが返る."""
        chunks = parse_transcript([])
        assert chunks == []

    def test_エッジケース_不正なJSONは無視される(self) -> None:
        """不正なJSON行は無視されスキップされる."""
        lines = [
            "this is not json",
            _make_line(role="user", content="有効な質問"),
            _make_line(role="assistant", content="有効な回答"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1

    def test_エッジケース_queue_operation行は無視される(self) -> None:
        """type=queue-operation の行はスキップされる."""
        lines = [
            json.dumps(
                {
                    "type": "queue-operation",
                    "operation": "dequeue",
                    "timestamp": "2026-03-24T00:00:00Z",
                    "sessionId": "test-session",
                }
            ),
            _make_line(role="user", content="質問"),
            _make_line(role="assistant", content="回答"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1

    def test_エッジケース_ツール結果行は無視される(self) -> None:
        """ツール結果（tool_result）の行は会話としてカウントしない."""
        lines = [
            _make_line(role="user", content="ファイルを読んでください"),
            _make_tool_result_line(content="file content here"),
            _make_line(role="assistant", content="ファイルの内容は..."),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1
        assert "tool_result" not in chunks[0].content
        assert "file content here" not in chunks[0].content

    def test_エッジケース_messageキーがない行は無視される(self) -> None:
        """message キーを持たない行は安全にスキップされる."""
        lines = [
            json.dumps({"isSidechain": False, "cwd": "/test"}),
            _make_line(role="user", content="質問"),
            _make_line(role="assistant", content="回答"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1

    def test_エッジケース_userのみでassistant回答がない場合(self) -> None:
        """user メッセージだけで終わる場合は回答なしのチャンクが生成される."""
        lines = [
            _make_line(role="user", content="回答がない質問"),
        ]
        chunks = parse_transcript(lines)
        # 末尾のuserメッセージもチャンクとして保持
        assert len(chunks) == 1
        assert "回答がない質問" in chunks[0].content

    def test_エッジケース_Chunkがdataclass属性を持つ(self) -> None:
        """Chunk オブジェクトが必要な属性を全て持つ."""
        lines = [
            _make_line(role="user", content="質問", session_id="s1"),
            _make_line(role="assistant", content="回答", session_id="s1"),
        ]
        chunks = parse_transcript(lines)
        assert len(chunks) == 1
        chunk = chunks[0]
        assert hasattr(chunk, "chunk_key")
        assert hasattr(chunk, "session_id")
        assert hasattr(chunk, "content")
        assert hasattr(chunk, "role")


# ---------------------------------------------------------------------------
# resolve_project テスト
# ---------------------------------------------------------------------------


class TestResolveProject:
    """resolve_project のテスト."""

    def test_正常系_worktreeパスが親プロジェクトに解決される(self) -> None:
        """worktree パスから親プロジェクト名が抽出される."""
        path = "/Users/user/Desktop/.worktrees/note-finance/feature-prj99"
        result = resolve_project(path)
        assert result == "note-finance"

    def test_正常系_通常のプロジェクトパスはそのまま返る(self) -> None:
        """worktree ではない通常パスは末尾ディレクトリ名を返す."""
        path = "/Users/user/Desktop/my-project"
        result = resolve_project(path)
        assert result == "my-project"

    def test_正常系_別のworktreeパターンも解決される(self) -> None:
        """異なるworktreeブランチ名でも正しく親プロジェクトを解決する."""
        path = "/Users/user/Desktop/.worktrees/finance/feature-branch"
        result = resolve_project(path)
        assert result == "finance"

    def test_エッジケース_空文字列で空文字列を返す(self) -> None:
        """空のパスの場合は空文字列を返す."""
        result = resolve_project("")
        assert result == ""

    def test_エッジケース_ルートパス(self) -> None:
        """ルートパスでもクラッシュしない."""
        result = resolve_project("/")
        assert isinstance(result, str)
