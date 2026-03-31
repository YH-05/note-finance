"""Shared test configuration for scripts tests.

BaseMapper テスト全般で使用できる共通フィクスチャを提供する。
ontology_loader 経由で ontology.yaml を参照する新方式に対応。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def yaml_schema_fixture(tmp_path: Path) -> Path:
    """BaseMapper テスト用の最小 ontology.yaml スキーマファイルを生成する。

    ontology_loader の ``_DEFAULT_ONTOLOGY_PATH`` をモンキーパッチする際に使用する。

    Parameters
    ----------
    tmp_path : Path
        pytest が提供する一時ディレクトリ。

    Returns
    -------
    Path
        生成した ontology.yaml のパス。
    """
    schema = {
        "entity_classification_nodes": [
            {
                "label": "EntityType",
                "canonical_values": [
                    {"key": "company", "consolidates": ["fintech"]},
                    {"key": "technology", "consolidates": []},
                    {"key": "organization", "consolidates": ["central_bank"]},
                    {"key": "person", "consolidates": []},
                    {"key": "index", "consolidates": []},
                    {"key": "indicator", "consolidates": ["metric"]},
                    {"key": "instrument", "consolidates": ["etf"]},
                    {"key": "commodity", "consolidates": []},
                    {"key": "country", "consolidates": ["region"]},
                    {"key": "sector", "consolidates": ["market"]},
                    {"key": "concept", "consolidates": ["domain"]},
                    {"key": "regulation", "consolidates": []},
                    {"key": "broker", "consolidates": []},
                    {"key": "product", "consolidates": []},
                ],
            }
        ],
        "source_classification_nodes": [
            {
                "label": "SourceType",
                "canonical_values": ["web", "news", "pdf", "original", "blog"],
            }
        ],
    }
    yaml_path = tmp_path / "ontology.yaml"
    yaml_path.write_text(yaml.dump(schema, allow_unicode=True), encoding="utf-8")
    return yaml_path
