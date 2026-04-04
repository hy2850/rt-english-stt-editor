from __future__ import annotations


def format_for_insert(
    text: str,
    *,
    separator: str = "\n",
    add_terminal_punctuation: bool = True,
) -> str:
    formatted = text.strip()
    if not formatted:
        return ""

    if add_terminal_punctuation and formatted[-1] not in ".?!":
        formatted = f"{formatted}."

    return f"{formatted}{separator}"
