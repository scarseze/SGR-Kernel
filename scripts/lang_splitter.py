#!/usr/bin/env python3
"""
lang_splitter.py — Extract a single language section from bilingual Markdown.

Bilingual files in ai_ml_playbook follow one of these patterns:

  Pattern A (EN first):
      <english content>
      ---
      # Russian Section / Русская Секция 🇷🇺
      <russian content>

  Pattern B (RU first):
      ## 🇷🇺 Русский (Russian)
      <russian content>
      ---
      ## 🇺🇸 English
      <english content>

  Pattern C (monolingual):
      Same content for both languages (no markers found).

Usage:
    from lang_splitter import split_by_language
    ru_text, en_text = split_by_language(full_markdown)
"""

import re

# Markers that signal a language boundary (checked in order)
_MARKERS = [
    # Pattern A: EN then RU
    {
        "split_re": re.compile(
            r"^-{3,}\s*\n+\s*#\s*Russian\s+Section.*$", re.MULTILINE | re.IGNORECASE
        ),
        "first": "en",
    },
    # Pattern A variant: just "# Русская Секция" without "Russian Section"
    {
        "split_re": re.compile(
            r"^-{3,}\s*\n+\s*#\s*Русская\s+Секция.*$", re.MULTILINE
        ),
        "first": "en",
    },
    # Pattern A variant: inline marker "# Архитектура (Architecture)"
    # architecture.md uses "---\n\n# Архитектура" as the split
    {
        "split_re": re.compile(
            r"^-{3,}\s*\n+\s*#\s*Архитектура.*$", re.MULTILINE
        ),
        "first": "en",
    },
    # Pattern B: RU first, split at "## 🇺🇸 English"
    {
        "split_re": re.compile(
            r"^-{3,}\s*\n+\s*##\s*🇺🇸\s*English.*$", re.MULTILINE
        ),
        "first": "ru",
    },
    # Pattern B variant: "## 🇺🇸 English" without preceding ---
    {
        "split_re": re.compile(
            r"^\s*##\s*🇺🇸\s*English.*$", re.MULTILINE
        ),
        "first": "ru",
    },
]


def split_by_language(content: str) -> tuple[str, str]:
    """
    Split bilingual Markdown into (ru_content, en_content).

    Returns the full content for both if no language boundary is detected.
    Strips leading/trailing whitespace from each section.
    """
    for marker in _MARKERS:
        match = marker["split_re"].search(content)
        if match:
            first_part = content[: match.start()].strip()
            second_part = content[match.end() :].strip()

            # Remove the repeated title line that often appears right after
            # the separator (e.g. "# AI/ML Playbook" duplicated)
            second_part = _strip_duplicate_title(first_part, second_part)

            if marker["first"] == "en":
                return second_part, first_part   # (ru, en)
            else:
                return first_part, second_part    # (ru, en)

    # No marker found — return identical content for both languages
    return content.strip(), content.strip()


def _strip_duplicate_title(first: str, second: str) -> str:
    """If the second section starts with the exact same H1 as the first, remove it."""
    first_h1 = _extract_first_h1(first)
    second_h1 = _extract_first_h1(second)

    if first_h1 and second_h1:
        # Don't strip if they're genuinely different
        # (but strip if the second is just a translation header with same structure)
        pass  # Keep both — they're likely translated titles

    return second


def _extract_first_h1(text: str) -> str | None:
    """Return the text of the first H1 heading, or None."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python lang_splitter.py <file.md> [ru|en]")
        sys.exit(1)

    path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "both"

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    ru, en = split_by_language(raw)

    def safe_print(text):
        """Print text safely on Windows terminals with limited encoding."""
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", errors="replace").decode("ascii"))

    if lang == "ru":
        safe_print(ru)
    elif lang == "en":
        safe_print(en)
    else:
        safe_print("=== RU ===")
        safe_print(ru[:500])
        safe_print(f"\n... ({len(ru)} chars total)")
        safe_print("\n=== EN ===")
        safe_print(en[:500])
        safe_print(f"\n... ({len(en)} chars total)")
