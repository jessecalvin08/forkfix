from forkfix.tasks import (
    TEST_PATCH_FAILED, grading_script, hidden_tests_applied, is_resolved, parse_pytest_report, patched_files,
)

from fakes import make_task


def test_image_follows_swe_bench_docker_hub_naming():
    task = make_task(instance_id="pytest-dev__pytest-7373")
    assert task.image == "swebench/sweb.eval.x86_64.pytest-dev_1776_pytest-7373:latest"


def test_patched_files_lists_each_target_once():
    patch = "+++ b/a/x.py\n@@\n+++ b/a/y.py\n+++ b/a/x.py\n"
    assert patched_files(patch) == ["a/x.py", "a/y.py"]


def test_grading_matches_the_swe_bench_command_and_reads_logs_with_nul_bytes():
    script = grading_script(make_task())
    assert "git checkout abc123 -- tests/test_calc.py" in script
    assert f"(git apply /tmp/forkfix_test.patch || echo {TEST_PATCH_FAILED})" in script
    # Plain `pytest -rA`, as SWE-bench runs it: extra plugin flags change pytest's own test suite.
    assert "; pytest -rA tests/test_calc.py >" in script and "no:cacheprovider" not in script
    assert "grep -a -E" in script


def test_parse_pytest_report_strips_failure_messages():
    output = (
        "PASSED tests/test_calc.py::test_sub\n"
        "FAILED tests/test_calc.py::test_add - AssertionError: 3 != 4\n"
        "XFAIL tests/test_calc.py::test_odd[1-2]\n"
        "some other line\n"
    )
    assert parse_pytest_report(output) == {
        "tests/test_calc.py::test_sub": "PASSED",
        "tests/test_calc.py::test_add": "FAILED",
        "tests/test_calc.py::test_odd[1-2]": "XFAIL",
    }


def test_ids_with_spaces_are_truncated_like_the_swe_bench_dataset_records_them():
    # SWE-bench keeps the first token after the status; the dataset holds "...[NOT".
    statuses = parse_pytest_report("PASSED testing/test_mark.py::test_expr[NOT internal_err]\n")
    assert statuses == {"testing/test_mark.py::test_expr[NOT": "PASSED"}


def test_a_hidden_test_patch_that_fails_to_apply_is_detected():
    assert hidden_tests_applied("PASSED a::b\n")
    assert not hidden_tests_applied(f"{TEST_PATCH_FAILED}\nPASSED a::b\n")


def test_resolved_needs_every_fail_to_pass_and_pass_to_pass_test():
    task = make_task()
    both = {"tests/test_calc.py::test_add": "PASSED", "tests/test_calc.py::test_sub": "PASSED"}
    assert is_resolved(task, both)
    assert not is_resolved(task, {**both, "tests/test_calc.py::test_sub": "FAILED"})
    assert not is_resolved(task, {"tests/test_calc.py::test_add": "PASSED"})


def test_a_task_with_no_required_tests_is_never_resolved():
    assert not is_resolved(make_task(fail_to_pass=(), pass_to_pass=()), {})
