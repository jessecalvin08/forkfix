import subprocess
import shutil

import pytest

from forkfix.repo import (FAILED, OK, RepoError, SetupResult, parse_issue_url, parse_setup, real_task,
                          setup_script)

REF = parse_issue_url("https://github.com/pallets/click/issues/2789")


def test_issue_urls_are_parsed_and_anything_else_is_refused():
    assert (REF.owner, REF.repo, REF.number, REF.slug) == ("pallets", "click", 2789, "pallets/click")
    assert REF.clone_url == "https://github.com/pallets/click.git"
    for bad in ("https://github.com/pallets/click/pull/1", "https://evil.example/a/b/issues/1",
                "https://github.com/pallets/click/issues/1; rm -rf /", "pallets/click#1"):
        with pytest.raises(RepoError):
            parse_issue_url(bad)


def test_setup_script_pins_the_commit_and_quotes_what_it_runs():
    script = setup_script(REF, "0123abc")
    assert "git clone -q https://github.com/pallets/click.git /testbed" in script
    assert "git checkout -q 0123abc" in script and OK in script
    assert "git checkout" not in setup_script(REF)
    with pytest.raises(RepoError):
        setup_script(REF, "abc; curl evil")  # not a hex sha


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_setup_script_is_valid_shell():
    assert subprocess.run(["bash", "-n"], input=setup_script(REF, "abc1234"), text=True).returncode == 0


def test_setup_output_is_read_from_its_markers():
    good = f"installed with: pip install -q -e .\ncommit: {'a' * 40}\ncollected: 412 tests collected in 1.2s\n{OK}\n"
    assert parse_setup(good) == SetupResult(True, "a" * 40, 412)
    assert parse_setup(f"{FAILED}: clone\n") == SetupResult(False, message="clone")
    # Marker-deselected suites print "N/TOTAL tests collected (M deselected)": N is what will run.
    assert parse_setup(f"commit: {'a' * 40}\ncollected: 2266/33266 tests collected (31000 deselected) in 1s\n{OK}\n").collected == 2266
    # A project whose pytest config decorates the summary line: "==== 383 tests collected in 0.2s ====".
    assert parse_setup(f"commit: {'a' * 40}\ncollected: ========= 383 tests collected in 0.16s =========\n{OK}\n").collected == 383
    # pip exits 0 for an undefined extra, so all the usual extras must be requested in one install.
    assert "'.[test,tests,testing,dev]'" in setup_script(REF)
    assert "pip install -q --group" in setup_script(REF)  # test deps declared as PEP 735 dependency groups
    assert not parse_setup("killed").ok  # no marker: a timeout or crash
    empty = parse_setup(f"commit: {'b' * 40}\ncollected: no tests ran in 0.1s\n{OK}\n")
    assert not empty.ok and "collected no tests" in empty.message


def test_a_real_task_has_no_hidden_tests_and_asks_for_a_reproduction_first():
    task = real_task(REF, "Title", "Body", "c" * 40)
    assert task.instance_id == "pallets__click-2789" and task.problem_statement == "Title\n\nBody"
    assert task.repro_first and task.gold_patch == "" and task.fail_to_pass == ()
    assert task.activate.startswith("source /opt/venv/bin/activate")


def test_parse_setup_ignores_terminal_colour_codes_around_the_collect_summary():
    esc = chr(27)
    line = f"{esc}[32m{esc}[32m856 tests collected{esc}[0m{esc}[32m in 0.18s{esc}[0m{esc}[0m"
    out = parse_setup("commit: " + "a" * 40 + chr(10) + "collected: " + line + chr(10) + "FORKFIX_SETUP_OK")
    assert out.ok and out.collected == 856
