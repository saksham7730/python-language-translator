"""Split long text into API-sized chunks with a generator (US-10).

Translation APIs limit how much text one request may contain (Google: 5000 characters,
MyMemory: 500). chunk_text() cuts the text at the most natural point that fits:
  1. at line breaks (keeps paragraphs together),
  2. else at sentence ends ( . ! ? and the Hindi danda । ),
  3. else at spaces, and only as a last resort in the middle of a word.

It is a GENERATOR (uses `yield`): it hands out one chunk at a time instead of building
a full list in memory, and the caller can start translating the first chunk right away.
"""
import re

SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def _hard_split(piece, max_chars):
    """Last resort: cut a too-long piece at spaces, or mid-word if there are none."""
    while len(piece) > max_chars:
        cut = piece.rfind(" ", 0, max_chars)
        cut = cut + 1 if cut > 0 else max_chars
        yield piece[:cut]
        piece = piece[cut:]
    if piece:
        yield piece


def _units(text, max_chars):
    """Yield small pieces of text (lines, sentences or slices) that each fit in max_chars.

    Every character of the input is kept, including line breaks, so ''.join(units) == text.
    """
    for line in text.splitlines(keepends=True):
        if len(line) <= max_chars:
            yield line
            continue
        # Line too long: split into sentences, keeping the spaces after each one
        start = 0
        for match in SENTENCE_END.finditer(line):
            yield from _hard_split(line[start:match.end()], max_chars)
            start = match.end()
        yield from _hard_split(line[start:], max_chars)


def chunk_text(text, max_chars):
    """Yield chunks of at most max_chars characters; ''.join(chunks) gives back the original text."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")
    buffer = ""
    for unit in _units(text, max_chars):
        if buffer and len(buffer) + len(unit) > max_chars:
            yield buffer           # the buffer is full: hand it out and start a new one
            buffer = ""
        buffer += unit
    if buffer:
        yield buffer
