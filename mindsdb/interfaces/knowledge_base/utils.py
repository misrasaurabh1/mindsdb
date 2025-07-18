"""Utilities for knowledge base operations."""

import hashlib
from functools import lru_cache


def generate_document_id(content: str, content_column: str = None, provided_id: str = None) -> str:
    """
    Generate a deterministic document ID from content.
    If provided_id exists, returns it directly.
    For generated IDs, uses a short hash of just the content.

    Args:
        content: The content string
        content_column: Name of the content column (not used in ID generation, kept for backward compatibility)
        provided_id: Optional user-provided ID
    Returns:
        Deterministic document ID (either provided_id or a 16-char hash of content)
    """
    if provided_id is not None:
        return provided_id

    # Generate a shorter 16-character hash based only on content, caching for speed
    return _short_md5_digest(content)


@lru_cache(maxsize=8192)
def _short_md5_digest(text: str) -> str:
    # Use utf-8 encoding with surrogatepass for fastest encode & allow edge unicode
    md5 = hashlib.md5(text.encode("utf-8", "surrogatepass"))
    return md5.hexdigest()[:16]
