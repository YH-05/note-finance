"""creator_enrichment Phase 3: ContentExtractor.

Anthropic API (claude-haiku-4-5-20251001) を使用して RawItem からコンテンツ分類・
Entity/Concept 抽出・リレーション検出を行う。

entity-extraction-prompt-v2.md テンプレートに基づき、1 RawItem あたり
1 API 呼び出しで全4タスクを実行する。

Usage
-----
::

    extractor = ContentExtractor(client=anthropic_client)
    result = extractor.extract_single(item=raw_item, genre="career")
    cycle_data = extractor.extract_batch(items=raw_items, genre="career")
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from creator_enrichment.config import ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL
from creator_enrichment.types import CycleData, ExtractionResult, RawItem
from creator_enrichment.utils import strip_json_codeblock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
_SLEEP_INTERVAL = 1
"""API 呼び出し間のスリープ秒数."""

_CONTENT_TRUNCATE_LIMIT = 4000
"""プロンプトに埋め込む外部コンテンツの最大文字数."""

_VALID_CONTENT_TYPES = frozenset({"Fact", "Tip", "Story"})
"""LLM 出力で許可される content_type."""

_VALID_ENTITY_TYPES = frozenset({"platform", "company", "person", "organization"})
"""LLM 出力で許可される entity_type."""


# ---------------------------------------------------------------------------
# プロンプトテンプレート
# ---------------------------------------------------------------------------
_EXTRACTION_PROMPT = """\
あなたはコンテンツ分析とナレッジグラフ構築の専門家です。
以下のテキストを分析し、分類・Entity抽出・Concept抽出・リレーション検出を行ってください。

## 入力テキスト

タイトル: {title}
ソースURL: {source_url}
言語: ja
ジャンル: {genre}

本文:
---
{content}
---

## タスク1: コンテンツ分類

以下の3タイプのいずれかに分類してください。

**Fact（事実・データ）**: 統計データや数値、調査結果や公式発表の引用、客観的な事実や現状の説明が主体
**Tip（ハウツー・ノウハウ）**: 手順やステップの説明、推奨事項やベストプラクティスの提示、ツールや方法の紹介・比較
**Story（体験談・事例）**: 個人の体験や経験の記述、事例紹介やケーススタディ、時系列での出来事の記述

## タスク2: Entity 抽出（固有名詞）

テキストから具体的な固有名詞を抽出してください。
entity_type は platform / company / person / organization の4種のみ。
正規化ルール: platform/company は公式英語表記、person は日本人は漢字・外国人はアルファベット。
各コンテンツから 0〜5 個の Entity を抽出。

## タスク3: Concept 抽出（ドメイン概念）

テキストから一般的なドメイン概念を抽出し、以下の14カテゴリのいずれかに分類してください。
カテゴリ: MonetizationMethod, AcquisitionChannel, Skill, Audience, RevenueModel, SuccessMetric, ContentFormat, Regulation, Milestone, PersuasionTechnique, EmotionalHook, CopyFramework, Objection, Transformation
各コンテンツから 1〜5 個の Concept を抽出。

## タスク4: SERVES_AS 関係と Concept 間リレーション検出

Entity が Concept に対してどのような役割を果たしているかを検出してください。
また、Concept 間に ENABLES / REQUIRES / COMPETES_WITH 関係があれば検出してください。

## 出力形式

以下の JSON 形式で出力してください。

```json
{{
  "content_type": "Fact | Tip | Story",
  "title": "元のタイトル",
  "body": "コンテンツの要約（200-500字）",
  "source_url": "{source_url}",
  "source_type": "web",
  "language": "ja",
  "entities": [
    {{"name": "正規化済みEntity名", "entity_type": "platform | company | person | organization"}}
  ],
  "concepts": [
    {{"name": "Concept名", "category": "ConceptCategory名", "new_category": false}}
  ],
  "serves_as": [
    {{"entity_name": "Entity名", "concept_name": "Concept名", "context": "役割の説明"}}
  ],
  "concept_relations": [
    {{"from_concept": "Concept名", "to_concept": "Concept名", "rel_type": "ENABLES | REQUIRES | COMPETES_WITH"}}
  ]
}}
```
"""


# ---------------------------------------------------------------------------
# ContentExtractor
# ---------------------------------------------------------------------------
class ContentExtractor:
    """Anthropic API を使用してコンテンツ分類・Entity/Concept 抽出を行う.

    Parameters
    ----------
    client : object
        ``messages.create()`` メソッドを持つ Anthropic クライアント
        （ダックタイピング: anthropic.Anthropic 互換であれば何でも可）
    """

    def __init__(self, client: object) -> None:
        self._client = client
        logger.info("ContentExtractor initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_single(self, *, item: RawItem, genre: str) -> ExtractionResult:
        """1 件の RawItem からコンテンツ分類・抽出を行う.

        Parameters
        ----------
        item : RawItem
            抽出対象の検索結果アイテム
        genre : str
            対象ジャンル（career / beauty-romance / spiritual）

        Returns
        -------
        ExtractionResult
            抽出結果（content_type, entities, concepts 等を含む）

        Raises
        ------
        ValueError
            レスポンスが空、JSON パース失敗、またはスキーマ不正の場合
        """
        # コンテンツをトランケーション（プロンプトインジェクション軽減）
        safe_content = item["content"][:_CONTENT_TRUNCATE_LIMIT]

        prompt = _EXTRACTION_PROMPT.format(
            title=item["title"],
            source_url=item["url"],
            genre=genre,
            content=safe_content,
        )

        logger.debug(
            "Calling API: title=%s, genre=%s",
            item["title"],
            genre,
        )

        response = self._client.messages.create(  # type: ignore[union-attr]
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text

        if not response_text or not response_text.strip():
            raise ValueError(f"Empty response from API for item: {item['title']}")

        cleaned = strip_json_codeblock(response_text)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON response for item: {item['title']}"
            ) from e

        # スキーマ検証: content_type
        ct = parsed.get("content_type", "Fact")
        if ct not in _VALID_CONTENT_TYPES:
            logger.warning(
                "Invalid content_type=%s, falling back to Fact", ct
            )
            parsed["content_type"] = "Fact"

        # スキーマ検証: entity_type
        for ent in parsed.get("entities", []):
            if ent.get("entity_type") not in _VALID_ENTITY_TYPES:
                logger.warning(
                    "Filtering invalid entity_type=%s for entity=%s",
                    ent.get("entity_type"),
                    ent.get("name"),
                )
        parsed["entities"] = [
            e for e in parsed.get("entities", [])
            if e.get("entity_type") in _VALID_ENTITY_TYPES
        ]

        logger.info(
            "Extraction completed: title=%s, content_type=%s",
            item["title"],
            parsed.get("content_type", "unknown"),
        )

        return parsed  # type: ignore[return-value]

    def extract_batch(self, *, items: list[RawItem], genre: str) -> CycleData:
        """複数の RawItem をバッチ処理し CycleData に集約する.

        1 RawItem あたり 1 API 呼び出しを行い、呼び出し間に
        1 秒のスリープを挟む（速度制限考慮）。

        個別アイテムの抽出失敗はログに記録してスキップし、
        他のアイテムの処理を継続する。

        Parameters
        ----------
        items : list[RawItem]
            抽出対象の RawItem リスト
        genre : str
            対象ジャンル

        Returns
        -------
        CycleData
            集約された抽出結果
        """
        cycle_id = f"cycle-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        logger.info(
            "Batch extraction started: cycle_id=%s, genre=%s, item_count=%d",
            cycle_id,
            genre,
            len(items),
        )

        sources: list[dict[str, str]] = []
        facts: list[dict[str, object]] = []
        tips: list[dict[str, object]] = []
        stories: list[dict[str, object]] = []
        entities: list[dict[str, str]] = []
        concepts: list[dict[str, object]] = []
        serves_as: list[dict[str, str]] = []
        concept_relations: list[dict[str, str]] = []

        for i, item in enumerate(items):
            if i > 0:
                time.sleep(_SLEEP_INTERVAL)

            try:
                extracted = self.extract_single(item=item, genre=genre)
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(
                    "Skipping item due to extraction error: title=%s, error=%s",
                    item["title"],
                    str(e),
                )
                continue

            # sources の収集
            sources.append({"url": item["url"], "title": item["title"]})

            # content_type に基づく分類
            content_type = extracted.get("content_type", "Fact")
            content_entry: dict[str, object] = {
                "text": extracted.get("body", ""),
                "source_url": extracted.get("source_url", item["url"]),
            }

            if content_type == "Fact":
                facts.append(content_entry)
            elif content_type == "Tip":
                tips.append(content_entry)
            elif content_type == "Story":
                stories.append(content_entry)
            else:
                # 不明なタイプは Fact にフォールバック
                logger.warning(
                    "Unknown content_type=%s, falling back to Fact",
                    content_type,
                )
                facts.append(content_entry)

            # entities, concepts, serves_as, concept_relations の集約
            entities.extend(extracted.get("entities", []))
            concepts.extend(extracted.get("concepts", []))
            serves_as.extend(extracted.get("serves_as", []))
            concept_relations.extend(extracted.get("concept_relations", []))

        logger.info(
            "Batch extraction completed: cycle_id=%s, "
            "facts=%d, tips=%d, stories=%d, entities=%d",
            cycle_id,
            len(facts),
            len(tips),
            len(stories),
            len(entities),
        )

        return CycleData(
            genre=genre,
            cycle_id=cycle_id,
            sources=sources,
            facts=facts,
            tips=tips,
            stories=stories,
            entities=entities,
            concepts=concepts,
            serves_as=serves_as,
            concept_relations=concept_relations,
        )
