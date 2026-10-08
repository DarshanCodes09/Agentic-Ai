"""
Text cleaner service.

Standardizes extracted document text by stripping unnecessary control characters,
collapsing excessive whitespace, and standardizing newlines without altering academic semantics.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean extracted text while preserving original academic content.

    Operations:
      1. Normalize CRLF and CR to LF
      2. Filter out non-printable control characters (except \\n and \\t)
      3. Collapse horizontal whitespace (spaces, tabs) to single spaces
      4. Collapse excessive consecutive blank lines (more than 2 newlines -> 2)
      5. Strip leading and trailing whitespace
    """
    if not text:
        return ""

    # 1. Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip control characters other than standard whitespace (\t, \n)
    # Control characters in range \x00-\x08, \x0b-\x0c, \x0e-\x1f, \x7f
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 3. Collapse multiple horizontal whitespace within lines
    lines = []
    for line in text.split("\n"):
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned_line)

    text = "\n".join(lines)

    # 4. Collapse 3 or more consecutive newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Final strip
    return text.strip()
