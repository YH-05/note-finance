"""Global test configuration."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent

# emit_graph_queue は emit_research_queue にリネーム済み。旧テストは collect 時にスキップ
collect_ignore = [
    "scripts/test_emit_graph_queue.py",
    "scripts/test_e2e_graph_pipeline.py",
    "scripts/test_e2e_kg_v21_all_waves.py",
    "scripts/test_e2e_pdf_extraction.py",
    "scripts/test_e2e_save_to_article_graph.py",
    "pdf_pipeline/unit/test_emit_graph_queue_pdf.py",
]


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest before test collection.

    This hook runs before test collection, ensuring paths are set up correctly.
    """
    # Add src/ to Python path for package imports in CI environment
    src_path = project_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Add .claude/agents to Python path for finance_news_collector module
    agents_path = project_root / ".claude" / "agents"
    if agents_path.exists() and str(agents_path) not in sys.path:
        sys.path.insert(0, str(agents_path))


@pytest.fixture
def fixed_datetime() -> datetime:
    """Fixed datetime for reproducible tests.

    Returns
    -------
    datetime
        A fixed UTC datetime (2026-02-01T12:00:00Z).
    """
    return datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
