"""Shared test configuration for scripts tests.

BaseMapper テスト全般で使用できる共通フィクスチャを提供する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def yaml_schema_fixture(tmp_path: Path) -> Path:
    """BaseMapper テスト用の最小 YAML スキーマファイルを生成する。

    ``mappers.base._SCHEMA_YAML_PATH`` をモンキーパッチする際に使用する。

    Parameters
    ----------
    tmp_path : Path
        pytest が提供する一時ディレクトリ。

    Returns
    -------
    Path
        生成した knowledge-graph-schema.yaml のパス。
    """
    schema = {
        "version": "3.0",
        "consolidation_rules": {
            "entity_type": {
                "mapping": {
                    "company": "company",
                    "fintech": "company",
                    "technology": "technology",
                    "organization": "organization",
                    "central_bank": "organization",
                    "person": "person",
                    "index": "index",
                    "indicator": "indicator",
                    "metric": "indicator",
                    "instrument": "instrument",
                    "etf": "instrument",
                    "commodity": "commodity",
                    "country": "country",
                    "region": "country",
                    "sector": "sector",
                    "market": "sector",
                    "concept": "concept",
                    "regulation": "regulation",
                    "broker": "broker",
                    "product": "product",
                    "domain": "concept",
                }
            }
        },
        "enum_validations": {
            "entity_type": {
                "values": [
                    "company",
                    "technology",
                    "organization",
                    "person",
                    "index",
                    "indicator",
                    "instrument",
                    "commodity",
                    "country",
                    "sector",
                    "concept",
                    "regulation",
                    "broker",
                    "product",
                ]
            },
            "source_type": {"values": ["web", "news", "pdf", "original", "blog"]},
        },
        "source_type_normalization": {
            "mapping": {
                "web-research": "web",
                "annual_report": "pdf",
                "news_article": "news",
                "blog_post": "blog",
            }
        },
        "multilabel_types": {
            "entity_labels": {
                "labels": {
                    "Company": {"name_ja": "企業"},
                    "Technology": {"name_ja": "テクノロジー"},
                    "Organization": {"name_ja": "機関"},
                    "Person": {"name_ja": "人物"},
                    "MarketIndex": {"name_ja": "株価指数"},
                    "Indicator": {"name_ja": "経済指標"},
                    "Instrument": {"name_ja": "金融商品"},
                    "Commodity": {"name_ja": "コモディティ"},
                    "Country": {"name_ja": "国・地域"},
                    "Sector": {"name_ja": "セクター"},
                    "Concept": {"name_ja": "概念"},
                    "Regulation": {"name_ja": "規制・政策"},
                    "Broker": {"name_ja": "ブローカー"},
                    "Product": {"name_ja": "プロダクト"},
                }
            }
        },
    }
    yaml_path = tmp_path / "knowledge-graph-schema.yaml"
    yaml_path.write_text(yaml.dump(schema, allow_unicode=True), encoding="utf-8")
    return yaml_path
