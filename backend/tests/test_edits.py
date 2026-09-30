from forkfix.edits import apply_edit

SOURCE = (
    "def check(item):\n"
    "    if item.ready:\n"
    "        result = evaluate(item)\n"
    "        return result\n"
    "    return None\n"
)


def parses(source):
    try:
        compile(source, "x.py", "exec")
        return True
    except SyntaxError:
        return False


def test_an_exact_unique_match_is_replaced():
    out = apply_edit(SOURCE, "result = evaluate(item)", "result = evaluate(item, cache=False)", parses)
    assert "evaluate(item, cache=False)" in out.text and out.message == ""


def test_line_numbers_pasted_from_view_are_ignored():
    old = "     3          result = evaluate(item)\n     4          return result"
    new = "     3          return evaluate(item)"
    out = apply_edit(SOURCE, old, new, parses)
    assert out.text == SOURCE.replace("        result = evaluate(item)\n        return result", "        return evaluate(item)")


def test_wrong_indentation_in_old_str_still_matches_and_new_str_is_shifted_to_fit():
    old = "result = evaluate(item)\nreturn result"          # model dropped the 8-space indent
    new = "if item.cached:\n    return item.cached\nreturn evaluate(item)"
    out = apply_edit(SOURCE, old, new, parses)
    assert "        if item.cached:\n            return item.cached\n        return evaluate(item)" in out.text
    assert "ignoring whitespace" in out.message and parses(out.text)


def test_a_block_pasted_at_the_wrong_depth_is_shifted_as_a_whole():
    out = apply_edit(SOURCE, "        return result", "return result or 0", parses)
    assert "        return result or 0" in out.text and "re-indented" in out.message


def test_internally_inconsistent_indentation_is_not_silently_repaired():
    out = apply_edit(SOURCE, "        return result", "        total = result\n       return total", parses)
    assert not parses(out.text)  # handed back so the caller reports the syntax error


def test_ambiguous_matches_are_refused_with_their_line_numbers():
    out = apply_edit("x = 1\ny = 2\nx = 1\n", "x = 1", "x = 3", parses)
    assert out.text is None and "matches 2 times (lines 1, 3)" in out.message


def test_a_miss_reports_the_closest_numbered_lines():
    out = apply_edit(SOURCE, "result = evalute(item)", "result = 1", parses)
    assert out.text is None and "matches 0 times" in out.message
    assert "     3          result = evaluate(item)" in out.message


def test_empty_old_str_is_refused():
    assert apply_edit(SOURCE, "  \n", "x", parses).text is None


# --- fuzzy mode (real-issue runs only) ---

CODE = "def load(payload):\n    try:\n        return loads(payload)  # type: ignore[arg-type]\n    except Exception:\n        raise\n"


def test_fuzzy_mode_applies_a_near_identical_single_region_and_default_mode_does_not():
    old = "        return loads(payload)  # type: ignore[arg]"  # a mistyped trailing comment
    new = "        return loads(payload, **kwargs)  # type: ignore[arg-type]"
    assert apply_edit(CODE, old, new).text is None  # benchmark behaviour is unchanged
    fuzzy = apply_edit(CODE, old, new, fuzzy=True)
    assert fuzzy.text is not None and "loads(payload, **kwargs)" in fuzzy.text and "near-identical lines 3-3" in fuzzy.message
    assert fuzzy.text.count("def load") == 1 and "except Exception" in fuzzy.text


def test_fuzzy_mode_refuses_unrelated_or_ambiguous_targets():
    assert apply_edit(CODE, "def something_else():\n    pass", "x", fuzzy=True).text is None
    twin = CODE + "\n" + CODE.replace("def load", "def load2")  # two near-identical regions: ambiguous
    assert apply_edit(twin, "        return loads(payload)  # type: ignore[arg]", "y", fuzzy=True).text is None
