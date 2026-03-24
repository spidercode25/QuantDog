from __future__ import annotations

import html
import re


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def to_plain_text(value: object) -> str:
    """Convert rich/HTML-like content into plain readable text."""
    text = str(value or "")
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _WS_RE.sub(" ", text).strip()
    return text
