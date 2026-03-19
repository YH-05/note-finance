"""Integration tests for KgExporter.

実際のファイルシステムを使用して graph-queue JSON ファイルの出力を検証する。
Neo4j (port 7688) への接続確認テストも含む。

Notes
-----
- CI では ``@pytest.mark.integration`` により自動スキップされる。
- graph-queue JSON の出力テストは NEO4J_URI 等の設定不要で実行できる。
- Neo4j 接続テストは ``NEO4J_URI``, ``NEO4J_USERNAME``, ``NEO4J_PASSWORD``
  環境変数が必須。未設定ならスキップする。
"""

import json
import os
from pathlib import Path

import pytest

from youtube_transcript.exceptions import ChannelNotFoundError
from youtube_transcript.services.kg_exporter import KgExporter
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    Channel,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_channel(
    channel_id: str = "UCintegration001",
    title: str = "Integration Test Channel",
) -> Channel:
    """テスト用 Channel オブジェクトを生成する."""
    return Channel(
        channel_id=channel_id,
        title=title,
        uploads_playlist_id=f"UU{channel_id[2:]}",
        language_priority=["en"],
        enabled=True,
        created_at="2026-03-19T00:00:00+00:00",
        last_fetched=None,
        video_count=1,
    )


def _make_video(
    video_id: str = "testVideo001",
    channel_id: str = "UCintegration001",
    status: TranscriptStatus = TranscriptStatus.SUCCESS,
) -> Video:
    """テスト用 Video オブジェクトを生成する."""
    return Video(
        video_id=video_id,
        channel_id=channel_id,
        title="Integration Test Video",
        published="2026-03-19T00:00:00+00:00",
        description="A video used for integration testing.",
        transcript_status=status,
        transcript_language="en",
        fetched_at="2026-03-19T01:00:00+00:00",
    )


def _make_transcript(video_id: str = "testVideo001") -> TranscriptResult:
    """テスト用 TranscriptResult オブジェクトを生成する."""
    return TranscriptResult(
        video_id=video_id,
        language="en",
        entries=[
            TranscriptEntry(start=0.0, duration=3.0, text="Hello, this is a test."),
            TranscriptEntry(
                start=3.0, duration=2.0, text="Integration test transcript."
            ),
        ],
        fetched_at="2026-03-19T01:00:00+00:00",
    )


def _setup_storage(
    data_dir: Path, channel: Channel, video: Video, transcript: TranscriptResult
) -> None:
    """JSONStorage にテストデータをセットアップする."""
    storage = JSONStorage(data_dir)
    storage.save_channels([channel])
    storage.save_videos(channel.channel_id, [video])
    storage.save_transcript(channel.channel_id, transcript)


def _require_neo4j_env() -> tuple[str, str, str]:
    """Neo4j 接続に必要な環境変数を取得する。未設定ならスキップ."""
    uri = os.environ.get("NEO4J_URI", "")
    username = os.environ.get("NEO4J_USERNAME", "")
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not uri or not username or not password:
        pytest.skip("NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD not set")
    return uri, username, password


# ---------------------------------------------------------------------------
# KgExporter.export_video 統合テスト
# ---------------------------------------------------------------------------


class TestKgExporterExportVideoIntegration:
    """KgExporter.export_video() の統合テスト（実際のファイルシステムを使用）."""

    @pytest.mark.integration
    def test_正常系_動画ノードをgraph_queue_JSONにエクスポートできる(
        self,
        tmp_path: Path,
    ) -> None:
        """export_video() が graph-queue JSON ファイルを正しく生成できることを確認する."""
        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "graph-queue"

        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)

        video = _make_video()
        transcript = _make_transcript()

        output_path = exporter.export_video(video=video, transcript=transcript)

        # ファイルが生成されている
        assert output_path.exists()
        assert output_path.suffix == ".json"

        # JSON の内容を確認
        content = json.loads(output_path.read_text(encoding="utf-8"))

        # schema_version は "2.0"
        assert content["schema_version"] == "2.0"
        # command_source は "youtube_transcript"
        assert content["command_source"] == "youtube_transcript"
        # sources に動画情報が含まれている
        assert len(content["sources"]) == 1
        source = content["sources"][0]
        assert source["title"] == video.title
        assert video.video_id in source["url"]
        # chunks にトランスクリプト全文が含まれている
        assert len(content["chunks"]) == 1
        chunk = content["chunks"][0]
        assert "Hello, this is a test." in chunk["text"]

    @pytest.mark.integration
    def test_正常系_出力ディレクトリが自動作成される(
        self,
        tmp_path: Path,
    ) -> None:
        """queue_dir が存在しない場合でも自動生成されることを確認する."""
        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "nonexistent" / "graph-queue"

        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)

        video = _make_video(video_id="vid002")
        transcript = _make_transcript(video_id="vid002")

        output_path = exporter.export_video(video=video, transcript=transcript)

        # ディレクトリが自動作成されてファイルが生成されている
        assert output_path.exists()

    @pytest.mark.integration
    def test_正常系_graph_queue_IDが一意である(
        self,
        tmp_path: Path,
    ) -> None:
        """複数回 export_video() を呼んでも queue_id が衝突しないことを確認する."""
        import time

        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "graph-queue"
        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)

        video1 = _make_video(video_id="vid001")
        transcript1 = _make_transcript(video_id="vid001")
        path1 = exporter.export_video(video=video1, transcript=transcript1)

        # タイムスタンプが変わるよう少し待つ
        time.sleep(1.1)

        video2 = _make_video(video_id="vid002")
        transcript2 = _make_transcript(video_id="vid002")
        path2 = exporter.export_video(video=video2, transcript=transcript2)

        # ファイル名（queue_id）が異なる
        assert path1.name != path2.name
        assert path1.exists()
        assert path2.exists()


# ---------------------------------------------------------------------------
# KgExporter.export_channel 統合テスト
# ---------------------------------------------------------------------------


class TestKgExporterExportChannelIntegration:
    """KgExporter.export_channel() の統合テスト（実際のファイルシステムを使用）."""

    @pytest.mark.integration
    def test_正常系_チャンネルのSUCCESS動画をエクスポートできる(
        self,
        tmp_path: Path,
    ) -> None:
        """export_channel() がチャンネルの SUCCESS 動画を graph-queue JSON にエクスポートできる."""
        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "graph-queue"

        channel = _make_channel()
        video = _make_video(status=TranscriptStatus.SUCCESS)
        transcript = _make_transcript()

        _setup_storage(data_dir, channel, video, transcript)

        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)
        output_paths = exporter.export_channel(channel.channel_id)

        assert len(output_paths) == 1
        assert output_paths[0].exists()

        content = json.loads(output_paths[0].read_text(encoding="utf-8"))
        assert content["schema_version"] == "2.0"

    @pytest.mark.integration
    def test_正常系_PENDING動画はエクスポートされない(
        self,
        tmp_path: Path,
    ) -> None:
        """PENDING ステータスの動画は export_channel() でエクスポートされないことを確認する."""
        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "graph-queue"

        channel = _make_channel()
        video = _make_video(status=TranscriptStatus.PENDING)
        # PENDING なのでトランスクリプトは存在しないが、save_videos だけ行う
        storage = JSONStorage(data_dir)
        storage.save_channels([channel])
        storage.save_videos(channel.channel_id, [video])

        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)
        output_paths = exporter.export_channel(channel.channel_id)

        # PENDING 動画はエクスポートされない
        assert output_paths == []

    @pytest.mark.integration
    def test_異常系_存在しないチャンネルIDでChannelNotFoundError(
        self,
        tmp_path: Path,
    ) -> None:
        """存在しない channel_id で export_channel() を呼ぶと ChannelNotFoundError が発生する."""
        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "graph-queue"

        # ストレージを初期化するが、対象チャンネルは登録しない
        storage = JSONStorage(data_dir)
        storage.save_channels([])

        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)

        with pytest.raises(ChannelNotFoundError):
            exporter.export_channel("UCnonexistent")


# ---------------------------------------------------------------------------
# Neo4j 接続確認テスト
# ---------------------------------------------------------------------------


class TestNeo4jConnectionIntegration:
    """Neo4j (port 7688) への接続確認テスト.

    ``NEO4J_URI``, ``NEO4J_USERNAME``, ``NEO4J_PASSWORD`` が必須。
    """

    @pytest.mark.integration
    def test_正常系_Neo4j接続が確立できる(
        self,
        tmp_path: Path,
    ) -> None:
        """research-neo4j (port 7688) に接続できることを確認する."""
        uri, username, password = _require_neo4j_env()

        # neo4j ドライバーで接続テスト
        from neo4j import GraphDatabase  # type: ignore[import-untyped]

        driver = GraphDatabase.driver(uri, auth=(username, password))
        try:
            driver.verify_connectivity()
        finally:
            driver.close()

    @pytest.mark.integration
    def test_異常系_無効な接続情報でエラー(
        self,
        tmp_path: Path,
    ) -> None:
        """無効な接続情報で Neo4j ドライバーを使用すると接続エラーが発生することを確認する."""
        _require_neo4j_env()  # スキップ条件チェックのみ

        from neo4j import GraphDatabase  # type: ignore[import-untyped]
        from neo4j.exceptions import ServiceUnavailable  # type: ignore[import-untyped]

        # 無効なポートへの接続
        driver = GraphDatabase.driver(
            "bolt://localhost:19999",  # 存在しないポート
            auth=("invalid", "invalid"),
        )
        try:
            with pytest.raises((ServiceUnavailable, Exception)):
                driver.verify_connectivity()
        finally:
            driver.close()

    @pytest.mark.integration
    def test_正常系_graph_queue_JSONがNeo4jスキーマに準拠している(
        self,
        tmp_path: Path,
    ) -> None:
        """KgExporter が出力する graph-queue JSON が Neo4j 投入前提のスキーマを満たすことを確認する.

        Neo4j への実際の書き込みは行わず、JSON スキーマの構造を検証する。
        """
        _require_neo4j_env()  # スキップ条件チェックのみ

        data_dir = tmp_path / "youtube_transcript"
        queue_dir = tmp_path / "graph-queue"

        exporter = KgExporter(data_dir=data_dir, queue_dir=queue_dir)
        video = _make_video()
        transcript = _make_transcript()
        output_path = exporter.export_video(video=video, transcript=transcript)

        content = json.loads(output_path.read_text(encoding="utf-8"))

        # graph-queue v2.0 スキーマの必須フィールドを確認
        required_top_level = [
            "schema_version",
            "queue_id",
            "created_at",
            "command_source",
            "session_id",
            "batch_label",
            "sources",
            "topics",
            "claims",
            "facts",
            "entities",
            "chunks",
            "financial_datapoints",
            "fiscal_periods",
            "relations",
        ]
        for field in required_top_level:
            assert field in content, (
                f"必須フィールド '{field}' が graph-queue JSON に存在しません"
            )

        # relations の必須キーを確認
        required_relations = [
            "contains_chunk",
            "extracted_from_fact",
            "extracted_from_claim",
            "source_fact",
            "source_claim",
            "fact_entity",
            "claim_entity",
        ]
        for key in required_relations:
            assert key in content["relations"], (
                f"必須リレーション '{key}' が relations に存在しません"
            )
