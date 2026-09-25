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
