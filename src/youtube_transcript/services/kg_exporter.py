"""KgExporter: ナレッジグラフエクスポーター.

YouTube トランスクリプトデータを save-to-graph スキル向けの
graph-queue JSON 形式に変換し、research-neo4j（port 7688）への
投入準備を行う。

Architecture
------------
- ``export_video``: 1動画のトランスクリプトを graph-queue JSON にエクスポート
- ``export_channel``: チャンネルの全 SUCCESS 動画を一括エクスポート

graph-queue フォーマット仕様は .claude/skills/save-to-graph/guide.md を参照。
schema_version: "2.0" で出力する。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import ChannelNotFoundError
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    TranscriptResult,
    TranscriptStatus,
    Video,
)

logger = get_logger(__name__)

# graph-queue 出力先ディレクトリ（.tmp/graph-queue/youtube_transcript/）
_GRAPH_QUEUE_SUBDIR = "youtube_transcript"

# command_source 識別子
_COMMAND_SOURCE = "youtube_transcript"


class KgExporter:
    """YouTube トランスクリプトを graph-queue JSON にエクスポートするクラス.

    TranscriptResult と Video メタデータを組み合わせて、
    save-to-graph スキルが処理できる graph-queue フォーマット（v2.0）を生成する。

    Parameters
    ----------
    data_dir : Path
        youtube_transcript データのルートディレクトリ。
    queue_dir : Path | None
        graph-queue 出力先ディレクトリ。None の場合は
        ``data_dir.parent.parent.parent / ".tmp" / "graph-queue"`` を使用。

    Examples
    --------
    >>> from pathlib import Path
    >>> from youtube_transcript.services.kg_exporter import KgExporter
    >>> exporter = KgExporter(data_dir=Path("data/raw/youtube_transcript"))
    >>> output_paths = exporter.export_channel("UCabc123")
    >>> print(f"Exported {len(output_paths)} files")
    """

    def __init__(
        self,
        data_dir: Path,
        queue_dir: Path | None = None,
    ) -> None:
        """KgExporter を初期化する.

        Parameters
        ----------
        data_dir : Path
            youtube_transcript データのルートディレクトリ。
        queue_dir : Path | None
            graph-queue 出力先ルートディレクトリ。

        Raises
        ------
        ValueError
            data_dir が Path オブジェクトでない場合。
        """
        if not isinstance(data_dir, Path):  # type: ignore[reportUnnecessaryIsInstance]
            logger.error(
                "Invalid data_dir type",
                data_dir=str(data_dir),
                expected_type="Path",
                actual_type=type(data_dir).__name__,
            )
            raise ValueError(f"data_dir must be a Path object, got {type(data_dir)}")

        self.data_dir = data_dir
        self._storage = JSONStorage(data_dir)

        # デフォルトの queue_dir: プロジェクトルートの .tmp/graph-queue/
        if queue_dir is None:
            # data/raw/youtube_transcript → project_root/.tmp/graph-queue
            # data_dir は data/raw/youtube_transcript なので 3 レベル上がプロジェクトルート
            self.queue_dir = data_dir.parent.parent.parent / ".tmp" / "graph-queue"
        else:
            self.queue_dir = queue_dir

        logger.debug(
            "KgExporter initialized",
            data_dir=str(data_dir),
            queue_dir=str(self.queue_dir),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_video(
        self,
        video: Video,
        transcript: TranscriptResult,
    ) -> Path:
        """1動画のトランスクリプトを graph-queue JSON にエクスポートする.

        Parameters
        ----------
        video : Video
            動画メタデータ（タイトル、published 等）。
        transcript : TranscriptResult
            エクスポートするトランスクリプト。

        Returns
        -------
        Path
            生成した graph-queue JSON ファイルのパス。

        Examples
        --------
        >>> path = exporter.export_video(video=video, transcript=transcript)
        >>> print(path.name)  # gq-20260319210000-a1b2.json
        """
        now = datetime.now(UTC)
        timestamp_str = now.strftime("%Y%m%d%H%M%S")
        ts_hash = hashlib.sha256(timestamp_str.encode()).hexdigest()[:4]
        queue_id = f"gq-{timestamp_str}-{ts_hash}"

        # Source ID: UUID5(NAMESPACE_URL, youtube:{video_id})
        source_url = f"https://www.youtube.com/watch?v={video.video_id}"
        source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))

        # Chunk: plain text 全体を1チャンクとして扱う
        plain_text = transcript.to_plain_text()
        chunk_id = f"{source_id[:8]}_chunk_0"

        graph_queue: dict[str, object] = {
            "schema_version": "2.0",
            "queue_id": queue_id,
            "created_at": now.isoformat(),
            "command_source": _COMMAND_SOURCE,
            "session_id": f"youtube-transcript-{timestamp_str}",
            "batch_label": "youtube_transcript",
            "sources": [
                {
                    "source_id": source_id,
                    "url": source_url,
                    "title": video.title,
                    "published": video.published,
                    "feed_source": f"YouTube/{video.channel_id}",
                }
            ],
            "topics": [],
            "claims": [],
            "facts": [],
            "entities": [],
            "chunks": [
                {
                    "chunk_id": chunk_id,
                    "chunk_index": 0,
                    "section_title": video.title,
                    "text": plain_text,
                    "source_id": source_id,
                }
            ],
            "financial_datapoints": [],
            "fiscal_periods": [],
            "relations": {
                "contains_chunk": [{"source_id": source_id, "chunk_id": chunk_id}],
                "extracted_from_fact": [],
                "extracted_from_claim": [],
                "source_fact": [],
                "source_claim": [],
                "fact_entity": [],
                "claim_entity": [],
                "has_datapoint": [],
                "for_period": [],
                "datapoint_entity": [],
            },
        }

        # 出力ディレクトリ作成
        output_dir = self.queue_dir / _GRAPH_QUEUE_SUBDIR
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{queue_id}.json"
        output_path.write_text(
            json.dumps(graph_queue, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "Exported video to graph-queue",
            video_id=video.video_id,
            queue_id=queue_id,
            output_path=str(output_path),
        )

        return output_path

    def export_channel(
        self,
        channel_id: str,
        video_id: str | None = None,
    ) -> list[Path]:
        """チャンネルの SUCCESS 動画トランスクリプトを graph-queue JSON に一括エクスポートする.

        Parameters
        ----------
        channel_id : str
            対象の YouTube チャンネル ID。
        video_id : str | None
            特定の動画 ID を指定する場合。None の場合は全 SUCCESS 動画を対象とする。

        Returns
        -------
        list[Path]
            生成した graph-queue JSON ファイルのパスリスト。

        Raises
        ------
        ChannelNotFoundError
            指定した channel_id がストレージに存在しない場合。

        Examples
        --------
        >>> paths = exporter.export_channel("UCabc123")
        >>> print(f"Exported {len(paths)} files")
        """
        # チャンネルの存在確認
        channels = self._storage.load_channels()
        channel = next((ch for ch in channels if ch.channel_id == channel_id), None)
        if channel is None:
            logger.error("Channel not found", channel_id=channel_id)
            raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

        all_videos: list[Video] = self._storage.load_videos(channel_id)

        # video_id でフィルタリング
        if video_id is not None:
            all_videos = [v for v in all_videos if v.video_id == video_id]

        # SUCCESS 動画のみ抽出
        success_videos = [
            v for v in all_videos if v.transcript_status == TranscriptStatus.SUCCESS
        ]

        logger.info(
            "export_channel started",
            channel_id=channel_id,
            video_id_filter=video_id,
            total_videos=len(all_videos),
            success_videos=len(success_videos),
        )

        output_paths: list[Path] = []

        for video in success_videos:
            transcript = self._storage.load_transcript(channel_id, video.video_id)
            if transcript is None:
                logger.warning(
                    "Transcript file not found for SUCCESS video; skipping",
                    channel_id=channel_id,
                    video_id=video.video_id,
                )
                continue

            try:
                path = self.export_video(video=video, transcript=transcript)
                output_paths.append(path)
            except Exception:
                logger.exception(
                    "Failed to export video; skipping",
                    channel_id=channel_id,
                    video_id=video.video_id,
                )
                continue

        logger.info(
            "export_channel completed",
            channel_id=channel_id,
            exported=len(output_paths),
            skipped=len(success_videos) - len(output_paths),
        )

        return output_paths
