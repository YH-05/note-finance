"""Entry point for the pdf-pipeline CLI command."""

from __future__ import annotations

from pdf_pipeline.cli.main import cli


def main() -> None:
    """Run the pdf-pipeline CLI."""
    cli()


if __name__ == "__main__":
    main()
