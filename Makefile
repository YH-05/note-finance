.PHONY: format lint typecheck test check-all clean kg-quality

format:
	uv run ruff format src/ tests/

lint:
	uv run ruff check src/ tests/ --fix

typecheck:
	uv run pyright src/ tests/

test:
	uv run pytest tests/ -v

check-all: format lint typecheck test

kg-quality:
	uv run python scripts/kg_quality_metrics.py \
		--save-snapshot \
		--compare latest \
		--alert \
		--report data/processed/kg_quality/report_$$(date +%Y%m%d).md

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null; true
