"""Forgiving string-replace edits.

Small models copy code imprecisely: they paste the line numbers shown by ``view``, or get
the indentation of ``old_str`` slightly wrong. In the first real run that trapped an agent
in 18 failed edits. This module accepts an edit when it is unambiguous despite such
differences, and otherwise says where the closest text is. The target must still match
exactly one place in the file; nothing here guesses between candidates.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

VIEW_PREFIX = re.compile(r"^ *\d+  ")  # the numbering agent.view adds: f"{n:6d}  "


@dataclass(frozen=True)
class EditOutcome:
    text: str | None  # the new file content, or None if the edit was refused
    message: str


def _strip_view_numbers(block: str) -> str:
    lines = block.split("\n")
    numbered = [line for line in lines if line.strip()]
    if numbered and all(VIEW_PREFIX.match(line) for line in numbered):
        return "\n".join(VIEW_PREFIX.sub("", line, count=1) for line in lines)
    return block


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _first_code_line(lines: list[str]) -> str:
    return next((line for line in lines if line.strip()), "")


def _reindent(new_lines: list[str], old_base: str, file_base: str) -> list[str]:
    """Shift every line of new_str by the same amount, from old_str's base indent to the file's.

    A uniform shift keeps the block's internal structure (a dedented ``else:`` stays dedented),
    so it can only fix a block placed at the wrong depth, never change what the code means.
    """
    delta = len(file_base) - len(old_base)
    out = []
    for line in new_lines:
        if not line.strip():
            out.append(line)
        else:
            width = max(0, len(_indent(line)) + delta)
            out.append(" " * width + line.lstrip(" \t"))
    return out


def _trim_blank_edges(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _numbered(lines: list[str], first: int) -> str:
    return "\n".join(f"{n:6d}  {line}" for n, line in enumerate(lines, start=first))


def _best_windows(file_lines: list[str], old_lines: list[str]) -> tuple[int, float, float]:
    """(index, ratio) of the file window most like old_lines, plus the runner-up's ratio."""
    width = len(old_lines)
    target = "\n".join(line.strip() for line in old_lines)
    best, best_ratio, second = 0, -1.0, -1.0
    for i in range(max(1, len(file_lines) - width + 1)):
        matcher = difflib.SequenceMatcher(None, "\n".join(line.strip() for line in file_lines[i:i + width]), target)
        if matcher.quick_ratio() <= second:
            continue
        ratio = matcher.ratio()
        if ratio > best_ratio:
            best, best_ratio, second = i, ratio, best_ratio
        elif ratio > second:
            second = ratio
    return best, best_ratio, second


def closest_region(text: str, old: str) -> str:
    """The file lines most similar to old_str, numbered, to help the model retry."""
    file_lines, old_lines = text.split("\n"), _trim_blank_edges(old.split("\n"))
    if not old_lines or not file_lines:
        return ""
    best, _, _ = _best_windows(file_lines, old_lines)
    return _numbered(file_lines[best:best + len(old_lines)], best + 1)


# A near-identical region is a typo, not a different target. Used only when a caller opts in.
FUZZY_MATCH = 0.9
FUZZY_MARGIN = 0.8  # the runner-up must be clearly worse, so the target is unambiguous


def apply_edit(text: str, old: str, new: str, parses=lambda source: True, fuzzy: bool = False) -> EditOutcome:
    """Replace old with new in text. ``parses`` rejects results that do not compile.

    ``fuzzy`` also accepts one region that matches old_str almost exactly (a mistyped comment
    or token) when no other region comes close; real-issue runs measured about 15% of actions
    lost to such misses.
    """
    if not old.strip():
        return EditOutcome(None, "old_str is empty.")
    old, new = _strip_view_numbers(old), _strip_view_numbers(new)

    count = text.count(old)
    if count == 1:
        updated = text.replace(old, new)
        if parses(updated):
            return EditOutcome(updated, "")
        # The match was right but new_str's indentation was not: shift it to old_str's.
        old_lines, new_lines = old.split("\n"), new.split("\n")
        shifted = "\n".join(_reindent(new_lines, _indent(_first_code_line(new_lines)),
                                      _indent(_first_code_line(old_lines))))
        if shifted != new and parses(text.replace(old, shifted)):
            return EditOutcome(text.replace(old, shifted), "new_str was re-indented to match the code it replaces.")
        return EditOutcome(text.replace(old, new), "")  # the caller reports the syntax error
    if count > 1:
        lines = [text[: m.start()].count("\n") + 1 for m in re.finditer(re.escape(old), text)]
        return EditOutcome(None, f"old_str matches {count} times (lines {', '.join(map(str, lines[:8]))}); "
                                 "include more surrounding lines so it matches exactly once.")

    # No exact match: compare line by line, ignoring each line's surrounding whitespace.
    file_lines = text.split("\n")
    old_lines = _trim_blank_edges(old.split("\n"))
    key = [line.strip() for line in old_lines]
    matches = [i for i in range(len(file_lines) - len(key) + 1)
               if [line.strip() for line in file_lines[i:i + len(key)]] == key]
    if len(matches) == 1:
        i = matches[0]
        file_base = _indent(_first_code_line(file_lines[i:i + len(key)]))
        new_lines = _reindent(_trim_blank_edges(new.split("\n")), _indent(_first_code_line(old_lines)), file_base)
        updated = "\n".join(file_lines[:i] + new_lines + file_lines[i + len(key):])
        return EditOutcome(updated, f"old_str matched lines {i + 1}-{i + len(key)} after ignoring whitespace "
                                    "differences; new_str was indented to fit.")
    if len(matches) > 1:
        where = ", ".join(str(i + 1) for i in matches[:8])
        return EditOutcome(None, f"old_str matches {len(matches)} places when whitespace is ignored "
                                 f"(lines {where}); include more surrounding lines.")
    if fuzzy and old_lines:
        i, ratio, runner_up = _best_windows(file_lines, old_lines)
        if ratio >= FUZZY_MATCH and runner_up < FUZZY_MARGIN:
            width = len(old_lines)
            file_base = _indent(_first_code_line(file_lines[i:i + width]))
            new_lines = _reindent(_trim_blank_edges(new.split("\n")), _indent(_first_code_line(old_lines)), file_base)
            updated = "\n".join(file_lines[:i] + new_lines + file_lines[i + width:])
            return EditOutcome(updated, f"old_str was not exact; it was applied to the near-identical lines "
                                        f"{i + 1}-{i + width}. Check the result with view.")
    hint = closest_region(text, old)
    return EditOutcome(None, "old_str matches 0 times." + (f" The closest text is:\n{hint}" if hint else ""))
