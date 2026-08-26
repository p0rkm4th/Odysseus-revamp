import pytest

from scripts.hades_live_dogfood import CASES, select_cases


def test_live_selection_is_reproducible_for_rotating_sets():
    first = [case.name for case in select_cases(CASES, suite="rotating", sample=8, seed=17)]
    second = [case.name for case in select_cases(CASES, suite="rotating", sample=8, seed=17)]
    assert first == second
    assert len(first) == 8


def test_fresh_selection_breaks_declared_continuation_groups():
    selected = select_cases(CASES, suite="all", sample=36, seed=1, session_mode="fresh")
    assert all(case.mode == "fresh" and case.group is None for case in selected)


def test_declared_selection_preserves_asset_and_continue_groups():
    selected = select_cases(CASES, suite="all", session_mode="declared")
    assets = [case for case in selected if case.group == "assets_reference"]
    continuation = [case for case in selected if case.group == "continuation"]
    assert [case.name for case in assets] == ["assets_list", "assets_reference"]
    assert [case.name for case in continuation] == ["continuation_start", "continuation_resume"]


def test_security_suite_contains_no_general_answer_cases():
    selected = select_cases(CASES, suite="security")
    assert selected
    assert all(case.family == "security" for case in selected)


def test_core_and_held_out_suites_are_disjoint_and_nonempty():
    core = {case.name for case in select_cases(CASES, suite="core")}
    held_out = {case.name for case in select_cases(CASES, suite="held_out")}
    assert core
    assert held_out
    assert core.isdisjoint(held_out)
    assert core | held_out == {case.name for case in CASES}


@pytest.mark.parametrize("bad", [0, -1])
def test_sample_must_be_positive(bad):
    with pytest.raises(ValueError, match="positive"):
        select_cases(CASES, sample=bad)
