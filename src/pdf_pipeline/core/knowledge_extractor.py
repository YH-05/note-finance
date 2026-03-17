"""KnowledgeExtractor: LLM-based Entity/Fact/Claim extraction from text chunks.

Extracts structured knowledge (entities, facts, claims) from text chunks
using an LLM provider chain. Failed extractions return empty results
(graceful degradation) rather than raising exceptions.

Classes
-------
KnowledgeExtractor
    Extracts Entity/Fact/Claim from text chunks via LLM.

Examples
--------
>>> from unittest.mock import MagicMock
>>> provider_chain = MagicMock()
>>> provider_chain.extract_knowledge.return_value = '{"chunk_index": 0, "entities": []}'
>>> extractor = KnowledgeExtractor(provider_chain=provider_chain)
>>> isinstance(extractor, KnowledgeExtractor)
True
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from pdf_pipeline._logging import get_logger
from pdf_pipeline.schemas.extraction import (
    ChunkExtractionResult,
    DocumentExtractionResult,
)

if TYPE_CHECKING:
    from pdf_pipeline.services.provider_chain import ProviderChain

logger = get_logger(__name__, module="knowledge_extractor")

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
Extract entities, facts, claims, and financial data points from the following financial text as JSON.

Output format (must be valid JSON, no explanation):
{
  "chunk_index": <int>,
  "section_title": "<string or null>",
  "entities": [
    {
      "name": "<entity name>",
      "entity_type": "<company|index|sector|indicator|currency|commodity|person|organization|country|instrument>",
      "ticker": "<ticker or null>",
      "aliases": []
    }
  ],
  "facts": [
    {
      "content": "<factual statement>",
      "fact_type": "<statistic|event|data_point|quote|policy_action|economic_indicator|regulatory|corporate_action>",
      "as_of_date": "<date or null>",
      "about_entities": ["<entity name>"]
    }
  ],
  "claims": [
    {
      "content": "<opinion/prediction/recommendation>",
      "claim_type": "<opinion|prediction|recommendation|analysis|assumption|guidance|risk_assessment|policy_stance|sector_view|forecast>",
      "sentiment": "<bullish|bearish|neutral|mixed or null>",
      "magnitude": "<strong|moderate|slight or null>",
      "target_price": "<number or null>",
      "rating": "<Buy|Hold|Sell|Overweight|Underweight or null>",
      "time_horizon": "<e.g. 12M|FY26|long-term or null>",
      "about_entities": ["<entity name>"]
    }
  ],
  "financial_datapoints": [
    {
      "metric_name": "<e.g. Revenue|EBITDA|Net Income>",
      "value": <number>,
      "unit": "<e.g. USD mn|IDR bn|%|x>",
      "is_estimate": <true|false>,
      "currency": "<ISO 4217 code or null>",
      "period_label": "<e.g. FY2025|4Q25|1H26 or null>",
      "about_entities": ["<entity name>"]
    }
  ],
  "stances": [
    {
      "author_name": "<analyst or institution name>",
      "author_type": "<person|sell_side|buy_side|consultant|media|self>",
      "organization": "<organization name or null>",
      "entity_name": "<target entity name>",
      "rating": "<Buy|Hold|Sell|Overweight|Underweight or null>",
      "sentiment": "<bullish|bearish|neutral|mixed or null>",
      "target_price": <number or null>,
      "target_price_currency": "<ISO 4217 code or null>",
      "as_of_date": "<date or null>",
      "based_on_claims": ["<claim content string>"]
    }
  ],
  "causal_links": [
    {
      "from_type": "<fact|claim|datapoint>",
      "from_content": "<exact content string of the cause node from facts/claims/financial_datapoints above>",
      "to_type": "<fact|claim|datapoint>",
      "to_content": "<exact content string of the effect node from facts/claims/financial_datapoints above>",
      "mechanism": "<description of how/why the cause leads to the effect, or null>",
      "confidence": "<high|medium|low or null>"
    }
  ],
  "questions": [
    {
      "content": "<question describing a knowledge gap>",
      "question_type": "<data_gap|contradiction|prediction_test|assumption_check|consensus_divergence>",
      "priority": "<high|medium|low or null>",
      "about_entities": ["<entity name>"],
      "motivated_by_contents": ["<exact content string from facts/claims above that motivated this question>"]
    }
  ]
}

Rules:
- Output ONLY valid JSON. No explanation, commentary, or code fences.
- Extract ALL entities mentioned (companies, indices, sectors, indicators, currencies, commodities, persons, organizations, countries, instruments).
- Separate facts (verifiable data) from claims (opinions/predictions).
- Use entity names consistently in about_entities references.
- For claims: set magnitude to indicate conviction strength, include target_price/rating/time_horizon when available.
- For financial_datapoints: extract structured numerical data from tables and text. Set is_estimate to true for forecasts.
- For stances: extract analyst investment stances (rating + target price + sentiment) when an analyst or institution expresses a view on a specific entity. Include author_name (analyst/institution) and entity_name (target). Use based_on_claims to link stance to relevant claim content strings.
- For causal_links: identify cause-effect relationships between facts, claims, and financial data points within this chunk. Use exact content strings from the extracted nodes above for from_content/to_content. For datapoints, use metric_name as the content key.
- For questions: identify knowledge gaps in 5 categories:
  - data_gap: important information missing from this report (e.g., segment breakdown, competitive comparison)
  - contradiction: claims that conflict with general consensus or other sources
  - prediction_test: quantitative predictions that can be verified later (e.g., specific revenue targets, price forecasts)
  - assumption_check: assumptions that need verification (e.g., growth rate assumptions, market size estimates)
  - consensus_divergence: rating or target price divergence among multiple analysts on the same entity
  Use exact content strings from facts/claims above for motivated_by_contents. Set priority based on impact on investment decisions.

Text:
"""


# ---------------------------------------------------------------------------
# KnowledgeExtractor class
# ---------------------------------------------------------------------------


_DEFAULT_MAX_WORKERS = 5


class KnowledgeExtractor:
    """Extract Entity/Fact/Claim from text chunks using an LLM provider chain.

    Uses graceful degradation: failed extractions return empty results
    rather than stopping the pipeline.

    Parameters
    ----------
    provider_chain : ProviderChain
        LLM provider chain for knowledge extraction calls.
    max_workers : int
        Maximum concurrent LLM calls for parallel chunk extraction.
        Defaults to 5.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> chain = MagicMock()
    >>> extractor = KnowledgeExtractor(provider_chain=chain)
    >>> extractor.provider_chain is chain
    True
    """

    def __init__(
        self,
        provider_chain: ProviderChain,
        *,
        max_workers: int = _DEFAULT_MAX_WORKERS,
    ) -> None:
        self.provider_chain = provider_chain
        self._max_workers = max_workers
        logger.debug(
            "KnowledgeExtractor initialized",
            max_workers=max_workers,
        )

    def extract_from_chunks(
        self,
        *,
        chunks: list[dict[str, Any]],
        source_hash: str,
    ) -> DocumentExtractionResult:
        """Extract knowledge from all chunks in a document.

        Parameters
        ----------
        chunks : list[dict[str, Any]]
            Chunk dicts from the chunker (must have ``chunk_index`` and
            ``content`` keys).
        source_hash : str
            SHA-256 hash of the source PDF.

        Returns
        -------
        DocumentExtractionResult
            Aggregated extraction results for all chunks.
        """
        chunk_count = len(chunks)
        logger.info(
            "Knowledge extraction started",
            chunk_count=chunk_count,
            source_hash=source_hash,
        )

        if chunk_count <= 1:
            # Single chunk: no parallelism overhead
            results = [
                self._extract_single(c, chunk_index=c.get("chunk_index", 0))
                for c in chunks
            ]
        else:
            # Parallel extraction with bounded concurrency
            workers = min(self._max_workers, chunk_count)
            logger.debug(
                "Parallel extraction",
                workers=workers,
                chunk_count=chunk_count,
            )
            indexed_results: dict[int, ChunkExtractionResult] = {}
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._extract_single,
                        chunk,
                        chunk_index=chunk.get("chunk_index", i),
                    ): i
                    for i, chunk in enumerate(chunks)
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    indexed_results[idx] = future.result()
            results = [indexed_results[i] for i in range(chunk_count)]

        doc_result = DocumentExtractionResult(
            source_hash=source_hash,
            chunks=results,
        )

        e = f = cl = 0
        for c in results:
            e += len(c.entities)
            f += len(c.facts)
            cl += len(c.claims)

        logger.info(
            "Knowledge extraction completed",
            source_hash=source_hash,
            total_entities=e,
            total_facts=f,
            total_claims=cl,
        )

        return doc_result

    def _extract_single(
        self,
        chunk: dict[str, Any],
        *,
        chunk_index: int,
    ) -> ChunkExtractionResult:
        """Extract knowledge from a single chunk.

        On LLM failure or invalid JSON, returns an empty result
        (graceful degradation).

        Parameters
        ----------
        chunk : dict[str, Any]
            Chunk dict with ``content`` and optionally ``section_title``.
        chunk_index : int
            Zero-based chunk index.

        Returns
        -------
        ChunkExtractionResult
            Extraction result, possibly empty on failure.
        """
        content = chunk.get("content", "")
        section_title = chunk.get("section_title")

        if not content.strip():
            logger.debug(
                "Skipping empty chunk",
                chunk_index=chunk_index,
            )
            return ChunkExtractionResult(
                chunk_index=chunk_index,
                section_title=section_title,
            )

        try:
            prompt = _EXTRACTION_PROMPT + content
            raw_json = self.provider_chain.extract_knowledge(prompt)
            parsed = json.loads(raw_json)

            # Ensure chunk_index and section_title are set
            parsed["chunk_index"] = chunk_index
            if section_title is not None:
                parsed["section_title"] = section_title

            return ChunkExtractionResult.model_validate(parsed)

        except Exception as exc:
            logger.warning(
                "Knowledge extraction failed for chunk, returning empty result",
                chunk_index=chunk_index,
                error=str(exc),
            )
            return ChunkExtractionResult(
                chunk_index=chunk_index,
                section_title=section_title,
            )
