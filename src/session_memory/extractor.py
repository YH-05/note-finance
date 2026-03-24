"""Sonnet tool_use による構造化抽出エンジン.

会話チャンクから entities / topics / decisions を同時抽出する。
``tool_choice`` を ``extract_chunk_metadata`` に強制し、
``ChunkExtraction.model_json_schema()`` を ``input_schema`` として使用する。

抽出フロー:
1. ルールベース事前検出（キーワードマッチ）
2. Sonnet tool_use 抽出（API呼び出し）
3. 結果マージ（重複排除・confidence優先）
4. confidence フィルタリング（>= 0.7: 自動リンク / < 0.7: embedding補完 / < 0.3: 棄却）

並列実行:
- デフォルト 10 並列（asyncio.Semaphore）
- rate_limit_error 検出時に 5 並列へフォールバック
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from pydantic import BaseModel, Field

from session_memory._logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
"""デフォルトの Sonnet モデル名."""

_DEFAULT_MAX_CONCURRENCY = 10
"""デフォルトの最大並列実行数."""

_FALLBACK_CONCURRENCY = 5
"""rate limit 時のフォールバック並列数."""

_CONFIDENCE_DISCARD_THRESHOLD = 0.3
"""この値未満の confidence は棄却."""

_CONFIDENCE_AUTO_LINK_THRESHOLD = 0.7
"""この値以上の confidence は自動リンク対象."""

_RULE_BASED_CONFIDENCE = 0.5
"""ルールベース検出のデフォルト confidence."""

_MAX_RETRIES = 3
"""API呼び出しの最大リトライ回数."""

# ---------------------------------------------------------------------------
# ルールベース検出パターン
# ---------------------------------------------------------------------------

_ENTITY_PATTERNS: list[tuple[str, str]] = [
    (r"(?<![A-Za-z])Pydantic(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])FastAPI(?![A-Za-z])", "framework"),
    (r"(?<![A-Za-z])Django(?![A-Za-z])", "framework"),
    (r"(?<![A-Za-z])Flask(?![A-Za-z])", "framework"),
    (r"(?<![A-Za-z])Python(?![A-Za-z])", "language"),
    (r"(?<![A-Za-z])TypeScript(?![A-Za-z])", "language"),
    (r"(?<![A-Za-z])Rust(?![A-Za-z])", "language"),
    (r"(?<![A-Za-z])JavaScript(?![A-Za-z])", "language"),
    (r"(?<![A-Za-z])React(?![A-Za-z])", "framework"),
    (r"(?<![A-Za-z])Vue(?![A-Za-z])", "framework"),
    (r"(?<![A-Za-z])Next\.js(?![A-Za-z])", "framework"),
    (r"(?<![A-Za-z])Neo4j(?![A-Za-z0-9])", "database"),
    (r"(?<![A-Za-z])PostgreSQL(?![A-Za-z])", "database"),
    (r"(?<![A-Za-z])SQLite(?![A-Za-z])", "database"),
    (r"(?<![A-Za-z])Redis(?![A-Za-z])", "database"),
    (r"(?<![A-Za-z])Docker(?![A-Za-z])", "tool"),
    (r"(?<![A-Za-z])Kubernetes(?![A-Za-z])", "tool"),
    (r"(?<![A-Za-z])GitHub(?![A-Za-z])", "platform"),
    (r"(?<![A-Za-z])AWS(?![A-Za-z])", "platform"),
    (r"(?<![A-Za-z])GCP(?![A-Za-z])", "platform"),
    (r"(?<![A-Za-z])Azure(?![A-Za-z])", "platform"),
    (r"(?<![A-Za-z])OpenAI(?![A-Za-z])", "organization"),
    (r"(?<![A-Za-z])Anthropic(?![A-Za-z])", "organization"),
    (r"(?<![A-Za-z])pytest(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])numpy(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])pandas(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])scikit-learn(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])TensorFlow(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])PyTorch(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])structlog(?![A-Za-z])", "library"),
    (r"(?<![A-Za-z])httpx(?![A-Za-z])", "library"),
]
"""エンティティ検出用の正規表現パターン（名前, entity_type）.

AIDEV-NOTE: ``\\b`` は Python の ``re`` モジュールで日本語文字を ``\\w`` として
扱うため、「Pydanticと」のような日本語隣接パターンで境界が発火しない。
ASCII 文字の lookahead/lookbehind で代替する。
"""

_DECISION_KEYWORDS: list[str] = [
    "決定",
    "採用",
    "決めた",
    "決めました",
    "することにした",
    "することにしました",
    "に移行",
    "を選択",
    "を選定",
    "方針として",
    "結論として",
]
"""決定事項検出キーワード."""

_TOPIC_PATTERNS: list[str] = [
    r"機械学習",
    r"ディープラーニング",
    r"データ(?:処理|分析|前処理|バリデーション|モデリング)",
    r"API(?:設計|サーバー|開発)",
    r"テスト(?:戦略|自動化|駆動)",
    r"パフォーマンス(?:改善|最適化|チューニング)",
    r"セキュリティ(?:対策|検証|監査)",
    r"アーキテクチャ(?:設計|パターン)",
    r"デプロイ(?:メント|戦略|パイプライン)",
    r"CI/CD",
    r"リファクタリング",
    r"型(?:ヒント|チェック|安全)",
    r"ナレッジグラフ",
    r"自然言語処理",
    r"ベクトル(?:検索|DB)",
]
"""トピック検出用の正規表現パターン."""


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    """抽出されたエンティティ.

    Parameters
    ----------
    name : str
        エンティティ名（例: "Pydantic", "FastAPI"）
    entity_type : str
        エンティティ種別（例: "library", "framework", "language"）
    confidence : float
        抽出の確信度（0.0 - 1.0）
    """

    name: str = Field(..., description="エンティティ名")
    entity_type: str = Field(default="unknown", description="エンティティ種別")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="抽出の確信度（0.0 - 1.0）",
    )


class ExtractedTopic(BaseModel):
    """抽出されたトピック.

    Parameters
    ----------
    name : str
        トピック名（例: "データバリデーション"）
    confidence : float
        抽出の確信度（0.0 - 1.0）
    """

    name: str = Field(..., description="トピック名")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="抽出の確信度（0.0 - 1.0）",
    )


class ExtractedDecision(BaseModel):
    """抽出された決定事項.

    Parameters
    ----------
    summary : str
        決定事項の要約
    rationale : str
        決定の理由・根拠
    confidence : float
        抽出の確信度（0.0 - 1.0）
    """

    summary: str = Field(..., description="決定事項の要約")
    rationale: str = Field(default="", description="決定の理由・根拠")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="抽出の確信度（0.0 - 1.0）",
    )


class ChunkExtraction(BaseModel):
    """チャンクからの構造化抽出結果.

    entities / topics / decisions を同時に保持する。
    ``model_json_schema()`` を Sonnet tool_use の ``input_schema`` として使用する。

    Parameters
    ----------
    entities : list[ExtractedEntity]
        抽出されたエンティティ一覧
    topics : list[ExtractedTopic]
        抽出されたトピック一覧
    decisions : list[ExtractedDecision]
        抽出された決定事項一覧
    """

    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="抽出されたエンティティ一覧"
    )
    topics: list[ExtractedTopic] = Field(
        default_factory=list, description="抽出されたトピック一覧"
    )
    decisions: list[ExtractedDecision] = Field(
        default_factory=list, description="抽出された決定事項一覧"
    )


# ---------------------------------------------------------------------------
# ルールベース事前検出
# ---------------------------------------------------------------------------


def rule_based_predetect(text: str) -> ChunkExtraction:
    """ルールベースでチャンクテキストからメタデータを事前検出する.

    正規表現パターンによるキーワードマッチで、
    エンティティ・トピック・決定事項を低 confidence で検出する。

    Parameters
    ----------
    text : str
        チャンクテキスト

    Returns
    -------
    ChunkExtraction
        ルールベース検出結果（confidence は _RULE_BASED_CONFIDENCE）
    """
    if not text.strip():
        return ChunkExtraction()

    entities = _detect_entities(text)
    topics = _detect_topics(text)
    decisions = _detect_decisions(text)

    logger.debug(
        "Rule-based predetect completed",
        entity_count=len(entities),
        topic_count=len(topics),
        decision_count=len(decisions),
    )

    return ChunkExtraction(
        entities=entities,
        topics=topics,
        decisions=decisions,
    )


def _detect_entities(text: str) -> list[ExtractedEntity]:
    """テキストからエンティティをルールベースで検出する.

    Parameters
    ----------
    text : str
        検索対象テキスト

    Returns
    -------
    list[ExtractedEntity]
        検出されたエンティティリスト
    """
    entities: list[ExtractedEntity] = []
    seen_names: set[str] = set()

    for pattern, entity_type in _ENTITY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(0)
            if name.lower() not in seen_names:
                seen_names.add(name.lower())
                entities.append(
                    ExtractedEntity(
                        name=name,
                        entity_type=entity_type,
                        confidence=_RULE_BASED_CONFIDENCE,
                    )
                )

    return entities


def _detect_topics(text: str) -> list[ExtractedTopic]:
    """テキストからトピックをルールベースで検出する.

    Parameters
    ----------
    text : str
        検索対象テキスト

    Returns
    -------
    list[ExtractedTopic]
        検出されたトピックリスト
    """
    topics: list[ExtractedTopic] = []
    seen_names: set[str] = set()

    for pattern in _TOPIC_PATTERNS:
        match = re.search(pattern, text)
        if match:
            name = match.group(0)
            if name not in seen_names:
                seen_names.add(name)
                topics.append(
                    ExtractedTopic(
                        name=name,
                        confidence=_RULE_BASED_CONFIDENCE,
                    )
                )

    return topics


def _detect_decisions(text: str) -> list[ExtractedDecision]:
    """テキストから決定事項をルールベースで検出する.

    決定キーワードを含む文を抽出し、決定事項として返す。

    Parameters
    ----------
    text : str
        検索対象テキスト

    Returns
    -------
    list[ExtractedDecision]
        検出された決定事項リスト
    """
    decisions: list[ExtractedDecision] = []

    # 文に分割（句点区切り）
    sentences = re.split(r"[。\n]", text)

    for raw_sentence in sentences:
        stripped = raw_sentence.strip()
        if not stripped:
            continue

        for keyword in _DECISION_KEYWORDS:
            if keyword in stripped:
                decisions.append(
                    ExtractedDecision(
                        summary=stripped[:100],  # 最大100文字
                        rationale="",
                        confidence=_RULE_BASED_CONFIDENCE,
                    )
                )
                break  # 同じ文に複数キーワードがあっても1回だけ

    return decisions


# ---------------------------------------------------------------------------
# Sonnet tool_use 抽出
# ---------------------------------------------------------------------------


def _build_tool_definition() -> dict[str, Any]:
    """Sonnet tool_use のツール定義を構築する.

    ``ChunkExtraction.model_json_schema()`` を ``input_schema`` に使用する。

    Returns
    -------
    dict[str, Any]
        Anthropic API のツール定義
    """
    return {
        "name": "extract_chunk_metadata",
        "description": (
            "会話チャンクからエンティティ（ライブラリ、フレームワーク、言語等）、"
            "トピック（議論テーマ）、決定事項（採用した技術、方針等）を構造化抽出する。"
            "各項目に confidence（確信度 0.0-1.0）を付与すること。"
        ),
        "input_schema": ChunkExtraction.model_json_schema(),
    }


async def _call_sonnet(
    text: str,
    *,
    client: Any,
    model: str = _DEFAULT_MODEL,
) -> ChunkExtraction:
    """Sonnet API を呼び出して構造化抽出を実行する.

    Parameters
    ----------
    text : str
        抽出対象のチャンクテキスト
    client : Any
        Anthropic AsyncClient
    model : str
        使用するモデル名

    Returns
    -------
    ChunkExtraction
        Sonnet による抽出結果

    Raises
    ------
    Exception
        API呼び出しに失敗した場合
    """
    tool_def = _build_tool_definition()

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[tool_def],
        tool_choice={"type": "tool", "name": "extract_chunk_metadata"},
        messages=[
            {
                "role": "user",
                "content": (
                    "以下の会話チャンクからメタデータを抽出してください。\n\n"
                    f"```\n{text}\n```"
                ),
            }
        ],
    )

    # tool_use ブロックからインプットを取得
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            tool_input = block.input
            if isinstance(tool_input, dict):
                return ChunkExtraction.model_validate(tool_input)

    logger.warning("No tool_use block found in Sonnet response")
    return ChunkExtraction()


# ---------------------------------------------------------------------------
# confidence フィルタリング
# ---------------------------------------------------------------------------


def _filter_by_confidence(extraction: ChunkExtraction) -> ChunkExtraction:
    """confidence に基づいてフィルタリングする.

    - >= 0.7: 自動リンク対象（保持）
    - 0.3 <= x < 0.7: embedding 補完対象（保持）
    - < 0.3: 棄却

    Parameters
    ----------
    extraction : ChunkExtraction
        フィルタリング前の抽出結果

    Returns
    -------
    ChunkExtraction
        フィルタリング後の抽出結果
    """
    filtered_entities = [
        e for e in extraction.entities if e.confidence >= _CONFIDENCE_DISCARD_THRESHOLD
    ]
    filtered_topics = [
        t for t in extraction.topics if t.confidence >= _CONFIDENCE_DISCARD_THRESHOLD
    ]
    filtered_decisions = [
        d for d in extraction.decisions if d.confidence >= _CONFIDENCE_DISCARD_THRESHOLD
    ]

    discarded = (
        len(extraction.entities)
        - len(filtered_entities)
        + len(extraction.topics)
        - len(filtered_topics)
        + len(extraction.decisions)
        - len(filtered_decisions)
    )

    if discarded > 0:
        logger.debug(
            "Confidence filtering applied",
            discarded_count=discarded,
            threshold=_CONFIDENCE_DISCARD_THRESHOLD,
        )

    return ChunkExtraction(
        entities=filtered_entities,
        topics=filtered_topics,
        decisions=filtered_decisions,
    )


# ---------------------------------------------------------------------------
# マージ
# ---------------------------------------------------------------------------


def _merge_extractions(
    rule_based: ChunkExtraction,
    sonnet: ChunkExtraction,
) -> ChunkExtraction:
    """ルールベースと Sonnet の抽出結果をマージする.

    重複エンティティは confidence の高い方を優先する。

    Parameters
    ----------
    rule_based : ChunkExtraction
        ルールベース検出結果
    sonnet : ChunkExtraction
        Sonnet 抽出結果

    Returns
    -------
    ChunkExtraction
        マージ後の抽出結果
    """
    # エンティティ: name (case-insensitive) で重複排除、confidence 高い方を優先
    entity_map: dict[str, ExtractedEntity] = {}
    for entity in rule_based.entities:
        key = entity.name.lower()
        entity_map[key] = entity
    for entity in sonnet.entities:
        key = entity.name.lower()
        if key not in entity_map or entity.confidence > entity_map[key].confidence:
            entity_map[key] = entity
    merged_entities = list(entity_map.values())

    # トピック: name で重複排除
    topic_map: dict[str, ExtractedTopic] = {}
    for topic in rule_based.topics:
        topic_map[topic.name] = topic
    for topic in sonnet.topics:
        if (
            topic.name not in topic_map
            or topic.confidence > topic_map[topic.name].confidence
        ):
            topic_map[topic.name] = topic
    merged_topics = list(topic_map.values())

    # 決定事項: summary で重複排除
    decision_map: dict[str, ExtractedDecision] = {}
    for decision in rule_based.decisions:
        decision_map[decision.summary] = decision
    for decision in sonnet.decisions:
        if (
            decision.summary not in decision_map
            or decision.confidence > decision_map[decision.summary].confidence
        ):
            decision_map[decision.summary] = decision
    merged_decisions = list(decision_map.values())

    logger.debug(
        "Extractions merged",
        entity_count=len(merged_entities),
        topic_count=len(merged_topics),
        decision_count=len(merged_decisions),
    )

    return ChunkExtraction(
        entities=merged_entities,
        topics=merged_topics,
        decisions=merged_decisions,
    )


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


async def extract_chunk(
    text: str,
    *,
    client: Any,
    model: str = _DEFAULT_MODEL,
) -> ChunkExtraction:
    """単一チャンクから構造化メタデータを抽出する.

    1. ルールベース事前検出
    2. Sonnet tool_use 抽出
    3. 結果マージ
    4. confidence フィルタリング

    Parameters
    ----------
    text : str
        チャンクテキスト
    client : Any
        Anthropic AsyncClient
    model : str
        使用するモデル名（デフォルト: claude-sonnet-4-20250514）

    Returns
    -------
    ChunkExtraction
        抽出結果（confidence < 0.3 は棄却済み）
    """
    logger.debug("extract_chunk started", text_length=len(text))

    # Step 1: ルールベース事前検出
    rule_result = rule_based_predetect(text)

    # Step 2: Sonnet tool_use 抽出
    try:
        sonnet_result = await _call_sonnet(text, client=client, model=model)
    except Exception:
        logger.warning(
            "Sonnet extraction failed, using rule-based result only",
            exc_info=True,
        )
        return _filter_by_confidence(rule_result)

    # Step 3: マージ
    merged = _merge_extractions(rule_result, sonnet_result)

    # Step 4: confidence フィルタリング
    filtered = _filter_by_confidence(merged)

    logger.info(
        "extract_chunk completed",
        entity_count=len(filtered.entities),
        topic_count=len(filtered.topics),
        decision_count=len(filtered.decisions),
    )

    return filtered


async def extract_chunks_batch(
    texts: list[str],
    *,
    client: Any,
    model: str = _DEFAULT_MODEL,
    max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
) -> list[ChunkExtraction]:
    """複数チャンクを並列で構造化抽出する.

    ``asyncio.Semaphore`` で並列実行数を制御する。
    rate_limit_error 検出時にフォールバック並列数に削減してリトライする。

    Parameters
    ----------
    texts : list[str]
        チャンクテキストリスト
    client : Any
        Anthropic AsyncClient
    model : str
        使用するモデル名
    max_concurrency : int
        最大並列実行数（デフォルト: 10、rate limit 時に 5 へフォールバック）

    Returns
    -------
    list[ChunkExtraction]
        各チャンクの抽出結果（入力と同じ順序）
    """
    if not texts:
        return []

    logger.info(
        "extract_chunks_batch started",
        chunk_count=len(texts),
        max_concurrency=max_concurrency,
    )

    semaphore = asyncio.Semaphore(max_concurrency)
    rate_limited = False

    async def _extract_with_semaphore(text: str, index: int) -> ChunkExtraction:
        nonlocal rate_limited
        async with semaphore:
            for attempt in range(_MAX_RETRIES):
                try:
                    return await extract_chunk(text, client=client, model=model)
                except Exception as e:
                    error_msg = str(e)
                    if "rate_limit" in error_msg.lower() or "429" in error_msg:
                        if not rate_limited:
                            rate_limited = True
                            logger.warning(
                                "Rate limit detected, reducing concurrency",
                                new_concurrency=_FALLBACK_CONCURRENCY,
                            )
                        # 指数バックオフ
                        await asyncio.sleep(2**attempt)
                        continue
                    logger.warning(
                        "Extraction failed for chunk",
                        index=index,
                        attempt=attempt + 1,
                        error=error_msg,
                    )
                    if attempt == _MAX_RETRIES - 1:
                        # 最終リトライ失敗: ルールベース結果のみ返す
                        return rule_based_predetect(text)
                    await asyncio.sleep(1)

            return rule_based_predetect(text)

    tasks = [_extract_with_semaphore(text, i) for i, text in enumerate(texts)]
    results = await asyncio.gather(*tasks)

    logger.info(
        "extract_chunks_batch completed",
        chunk_count=len(texts),
        result_count=len(results),
    )

    return list(results)


__all__ = [
    "ChunkExtraction",
    "ExtractedDecision",
    "ExtractedEntity",
    "ExtractedTopic",
    "extract_chunk",
    "extract_chunks_batch",
    "rule_based_predetect",
]
