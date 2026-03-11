"""Shared regex patterns for the pdf_pipeline.core package.

This module centralises compiled regular expressions that are used by
multiple modules inside ``pdf_pipeline.core``.  It is an internal helper
(indicated by the leading underscore) and should not be imported from
outside the package.

Constants
---------
_HEADING_PATTERN
    Compiled regex that matches ATX-style Markdown headings
    (one to six ``#`` characters followed by whitespace and heading text)
    at the start of a line.
"""

from __future__ import annotations

import re

# Matches ATX headings:  # Heading, ## Heading, …, ###### Heading
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
