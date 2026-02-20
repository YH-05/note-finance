.PHONY: format lint typecheck test check-all clean

format:
	uv run ruff format src/ tests/

lint:
	uv run ruff check src/ tests/ --fix

typecheck:
	uv run pyright src/ tests/

test:
	uv run pytest tests/ -v

check-all: format lint typecheck test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null; true
