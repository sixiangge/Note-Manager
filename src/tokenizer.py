"""Shared tokenization rules for indexing and querying."""

from __future__ import annotations

import re

import jieba


_ASCII_TERM_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9])"
)


def tokenize(text: str) -> list[str]:
    """Tokenize text, excluding punctuation and preserving mixed terms."""
    if not text:
        return []

    tokens = [
        token
        for raw_token in jieba.cut_for_search(text)
        if (token := raw_token.strip()) and any(char.isalnum() for char in token)
    ]
    # Jieba splits terms such as ``E-R模型`` into E / - / R / 模型. Keep the
    # full spelling too, so an exact query can match the indexed terminology.
    for match in _ASCII_TERM_RE.finditer(text):
        suffix = text[match.end():]
        if not suffix or not "\u3400" <= suffix[0] <= "\u9fff":
            continue
        chinese_token = next(jieba.cut(suffix), "").strip()
        if chinese_token and all("\u3400" <= char <= "\u9fff" for char in chinese_token):
            tokens.append(match.group(0) + chinese_token)
    return tokens


__all__ = ["tokenize"]
