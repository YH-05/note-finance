"""KG Accuracy 評価モジュール — LLM-as-Judge。

Fact/Claim ノードを抽出し、3軸（Factual Correctness / Source Grounding /
Temporal Validity）で LLM 評価を行う。

Usage
-----
::

    # kg_quality_metrics.py から呼び出される
    from kg_accuracy_judge import evaluate_accuracy
    result = evaluate_accuracy(session, sample_size=20)
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime as dt
from datetime import timezone
from pathlib import Path
from typing import Any

try:
    from quants.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------


@dataclass
class AccuracyEvaluation:
    """1件の Fact/Claim に対する評価結果。"""

    fact_id: str
    factual_correctness: float
    source_grounding: float
    temporal_validity: float
    overall: float
    reasoning: str


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

DEFAULT_CACHE_PATH = Path("data/processed/kg_quality/accuracy_cache.json")
CACHE_TTL_DAYS = 30


def _content_hash(content: str) -> str:
    """SHA-256 ハッシュの先頭16文字を返す。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _load_cache(cache_path: Path) -> dict[str, Any]:
    """キャッシュ JSON を読み込む。"""
    if cache_path.exists():
        try:
            with cache_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Cache file corrupt, starting fresh")
    return {}


def _save_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    """キャッシュ JSON を保存する。"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _is_cache_valid(entry: dict[str, Any], ttl_days: int = CACHE_TTL_DAYS) -> bool:
    """キャッシュエントリの有効期限を確認する。"""
    evaluated_at = entry.get("evaluated_at", "")
    if not evaluated_at:
        return False
    try:
        eval_dt = dt.fromisoformat(evaluated_at)
        if eval_dt.tzinfo is None:
            eval_dt = eval_dt.replace(tzinfo=timezone.utc)
        age_days = (dt.now(tz=timezone.utc) - eval_dt).days
        return age_days < ttl_days
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Neo4j Sampling
# ---------------------------------------------------------------------------


def sample_facts(session: Any, sample_size: int = 20) -> list[dict[str, Any]]:
    """Fact/Claim ノードをサンプリングし Source コンテキストと JOIN で取得する。

    Parameters
    ----------
    session
        Neo4j セッション。
    sample_size : int
        サンプルサイズ。

    Returns
    -------
    list[dict[str, Any]]
        サンプリングされた Fact/Claim データ。
    """
    query = """
    MATCH (f)
    WHERE NOT 'Memory' IN labels(f)
    AND (f:Fact OR f:Claim)
    AND f.content IS NOT NULL
    OPTIONAL MATCH (f)<-[:STATES_FACT|MAKES_CLAIM]-(c:Chunk)
    OPTIONAL MATCH (c)<-[:CONTAINS_CHUNK]-(s:Source)
    RETURN
        coalesce(f.fact_id, f.claim_id, elementId(f)) AS fact_id,
        f.content AS content,
        labels(f) AS node_labels,
        s.title AS source_title,
        s.url AS source_url,
        toString(s.fetched_at) AS source_fetched_at
    """
    result = session.run(query)
    all_facts = result.data()
    logger.info("Total Fact/Claim nodes: %d", len(all_facts))

    if not all_facts:
        return []

    # 決定論的サンプリング（同日同サンプル）
    date_seed = dt.now(tz=timezone.utc).strftime("%Y%m%d")
    rng = random.Random(date_seed)
    actual_size = min(sample_size, len(all_facts))
    sampled = rng.sample(all_facts, actual_size)

    logger.info("Sampled %d facts for accuracy evaluation", len(sampled))
    return sampled


# ---------------------------------------------------------------------------
# LLM Evaluation
# ---------------------------------------------------------------------------

EVALUATION_PROMPT = """あなたは KG（知識グラフ）の品質評価者です。
以下の Fact/Claim を3つの観点で評価してください。

## 評価対象
- Content: {content}
- Source: {source_title} ({source_url})
- Fetched: {source_fetched_at}

## 評価観点（各 0.0-1.0）
1. **Factual Correctness** (事実正確性): 内容が事実として正しいか
2. **Source Grounding** (ソース根拠): Source との整合性があるか
3. **Temporal Validity** (時間妥当性): 情報が現在も有効か

## 出力形式（JSON のみ）
```json
{{
    "factual_correctness": 0.8,
    "source_grounding": 0.7,
    "temporal_validity": 0.6,
    "reasoning": "評価理由を1-2文で"
}}
```"""


def evaluate_single(fact: dict[str, Any], client: Any) -> AccuracyEvaluation:
    """1件の Fact/Claim を LLM で評価する。

    Parameters
    ----------
    fact : dict[str, Any]
        Fact/Claim データ。
    client
        Anthropic クライアント。

    Returns
    -------
    AccuracyEvaluation
        評価結果。
    """
    prompt = EVALUATION_PROMPT.format(
        content=fact.get("content", ""),
        source_title=fact.get("source_title", "N/A"),
        source_url=fact.get("source_url", "N/A"),
        source_fetched_at=fact.get("source_fetched_at", "N/A"),
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text
    # JSON ブロックを抽出
    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        parsed = json.loads(response_text[json_start:json_end])
    else:
        logger.warning("Could not parse JSON from LLM response, using defaults")
        parsed = {
            "factual_correctness": 0.5,
            "source_grounding": 0.5,
            "temporal_validity": 0.5,
            "reasoning": "Parse error",
        }

    fc = float(parsed.get("factual_correctness", 0.5))
    sg = float(parsed.get("source_grounding", 0.5))
    tv = float(parsed.get("temporal_validity", 0.5))
    # 加重平均: 40% / 30% / 30%
    overall = fc * 0.4 + sg * 0.3 + tv * 0.3

    return AccuracyEvaluation(
        fact_id=fact.get("fact_id", ""),
        factual_correctness=round(fc, 3),
        source_grounding=round(sg, 3),
        temporal_validity=round(tv, 3),
        overall=round(overall, 3),
        reasoning=parsed.get("reasoning", ""),
    )


def evaluate_batch(
    facts: list[dict[str, Any]],
    client: Any,
    *,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> list[AccuracyEvaluation]:
    """バッチ評価（キャッシュ利用）。

    Parameters
    ----------
    facts : list[dict[str, Any]]
        評価対象の Fact/Claim リスト。
    client
        Anthropic クライアント。
    cache_path : Path
        キャッシュファイルパス。

    Returns
    -------
    list[AccuracyEvaluation]
        評価結果リスト。
    """
    cache = _load_cache(cache_path)
    evaluations: list[AccuracyEvaluation] = []
    api_calls = 0

    for fact in facts:
        content = fact.get("content", "")
        cache_key = _content_hash(content)

        # キャッシュヒット
        if cache_key in cache and _is_cache_valid(cache[cache_key]):
            cached = cache[cache_key]
            evaluations.append(
                AccuracyEvaluation(
                    fact_id=fact.get("fact_id", ""),
                    factual_correctness=cached["factual_correctness"],
                    source_grounding=cached["source_grounding"],
                    temporal_validity=cached["temporal_validity"],
                    overall=cached["overall"],
                    reasoning=cached.get("reasoning", "(cached)"),
                )
            )
            continue

        # API 呼び出し
        try:
            evaluation = evaluate_single(fact, client)
            evaluations.append(evaluation)
            api_calls += 1

            # キャッシュ保存
            cache[cache_key] = {
                **asdict(evaluation),
                "evaluated_at": dt.now(tz=timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error("LLM evaluation failed for fact: %s", e)
            evaluations.append(
                AccuracyEvaluation(
                    fact_id=fact.get("fact_id", ""),
                    factual_correctness=0.5,
                    source_grounding=0.5,
                    temporal_validity=0.5,
                    overall=0.5,
                    reasoning=f"Evaluation error: {e}",
                )
            )

    _save_cache(cache_path, cache)
    logger.info(
        "Accuracy evaluation: %d total, %d API calls, %d cached",
        len(evaluations),
        api_calls,
        len(evaluations) - api_calls,
    )
    return evaluations


# ---------------------------------------------------------------------------
# Integration with kg_quality_metrics.py
# ---------------------------------------------------------------------------


def evaluate_accuracy(
    session: Any,
    *,
    sample_size: int = 20,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> Any:
    """accuracy カテゴリの計測結果を返す。

    kg_quality_metrics.py の measure_accuracy() を置き換える。

    Parameters
    ----------
    session
        Neo4j セッション。
    sample_size : int
        サンプルサイズ。
    cache_path : Path
        キャッシュファイルパス。

    Returns
    -------
    CategoryResult
        ``"accuracy"`` カテゴリの計測結果。
    """
    # 遅延インポートで循環参照を回避
    from kg_quality_metrics import CategoryResult, MetricValue, evaluate_status

    facts = sample_facts(session, sample_size)

    if not facts:
        logger.warning("No Fact/Claim nodes found for accuracy evaluation")
        return CategoryResult(
            name="accuracy",
            score=0.0,
            metrics=[MetricValue(value=0.0, unit="ratio", status="red")],
        )

    try:
        import anthropic

        client = anthropic.Anthropic()
    except (ImportError, Exception) as e:
        logger.error("Anthropic client not available: %s", e)
        return CategoryResult(
            name="accuracy",
            score=0.0,
            metrics=[
                MetricValue(value=0.0, unit="ratio", status="yellow", stub=True)
            ],
        )

    evaluations = evaluate_batch(facts, client, cache_path=cache_path)

    if not evaluations:
        return CategoryResult(
            name="accuracy",
            score=0.0,
            metrics=[MetricValue(value=0.0, unit="ratio", status="red")],
        )

    avg_fc = sum(e.factual_correctness for e in evaluations) / len(evaluations)
    avg_sg = sum(e.source_grounding for e in evaluations) / len(evaluations)
    avg_tv = sum(e.temporal_validity for e in evaluations) / len(evaluations)

    metrics = [
        MetricValue(
            value=round(avg_fc, 4),
            unit="ratio",
            status=evaluate_status("claim_evidence_ratio", avg_fc),
        ),
        MetricValue(
            value=round(avg_sg, 4),
            unit="ratio",
            status=evaluate_status("claim_evidence_ratio", avg_sg),
        ),
        MetricValue(
            value=round(avg_tv, 4),
            unit="ratio",
            status=evaluate_status("claim_evidence_ratio", avg_tv),
        ),
    ]

    score = round(
        sum(
            100.0 if m.status == "green" else 50.0 if m.status == "yellow" else 0.0
            for m in metrics
        )
        / len(metrics),
        1,
    )

    logger.info(
        "Accuracy: factual=%.4f, grounding=%.4f, temporal=%.4f, score=%.1f",
        avg_fc,
        avg_sg,
        avg_tv,
        score,
    )
    return CategoryResult(name="accuracy", score=score, metrics=metrics)
