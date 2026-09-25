from forkfix.forks import analyse, summarise


def node(id_, parent, steps, stop):
    return {"id": id_, "parent": parent, "born_at_step": 0, "steps": steps, "stop_reason": stop, "events": []}


def branching_mode():
    # 0 forks at step 3 into its own action (0.0) and two alternatives; 0.0 forks again.
    tree = [
        node("0", None, 3, "branched"),
        node("0.0", "0", 5, "branched"),
        node("0.1", "0", 9, "submitted"),
        node("0.2", "0", 6, "pruned"),
        node("0.0.0", "0.0", 8, "submitted"),
        node("0.0.1", "0.0", 7, "pruned"),
    ]
    candidates = [{"id": "0.1", "resolved": True}, {"id": "0.0.0", "resolved": False}]
    return {"tree": tree, "candidates": candidates, "selected_resolved": True}


def test_fork_outcomes_and_the_agents_own_path():
    a = analyse(branching_mode())
    forks = {f["node"]: f for f in a["forks"]}
    assert forks["0"]["children"] == {"0.0": "failed", "0.1": "passed", "0.2": "none"}
    assert forks["0"]["decisive"] and not forks["0"]["own_action_passed"]
    # 0.0's children: a failed patch and a pruned branch differ, but neither passed.
    assert forks["0.0"]["divergent"] and not forks["0.0"]["decisive"]
    assert a["own_path_leaf"] == "0.0.0" and a["own_path_passed"] is False


def test_children_are_ordered_numerically():
    mode = branching_mode()
    mode["tree"] += [node(f"0.{i}", "0", 4, "pruned") for i in range(3, 11)]
    assert list(analyse(mode)["forks"][0]["children"])[:3] == ["0.0", "0.1", "0.2"]
    assert list(analyse(mode)["forks"][0]["children"])[-1] == "0.10"


def test_summary_counts_wins_that_needed_an_alternative():
    linear = {"selected_resolved": False}
    records = {"t1": {"modes": {"branching": branching_mode(), "linear": linear}}}
    s = summarise(records, ["t1"])
    assert s["forks"] == 2 and s["decisive_forks"] == 1 and s["decisive_where_own_action_failed"] == 1
    assert s["wins_needing_an_alternative"] == ["t1"] and s["wins_where_own_path_also_passed"] == 0
