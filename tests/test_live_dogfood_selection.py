import pytest

from scripts.hades_live_dogfood import CASES, cookie_from_file, select_cases


def test_live_selection_is_reproducible_for_rotating_sets():
    first = [case.name for case in select_cases(CASES, suite="rotating", sample=8, seed=17)]
    second = [case.name for case in select_cases(CASES, suite="rotating", sample=8, seed=17)]
    assert first == second
    assert len(first) >= 8
    assert first.index("contamination_assets") < first.index("contamination_general")


def test_fresh_selection_breaks_declared_continuation_groups():
    selected = select_cases(CASES, suite="all", sample=36, seed=1, session_mode="fresh")
    assert all(case.mode == "fresh" and case.group is None for case in selected)


def test_fresh_selection_keeps_group_establishers_not_followups():
    from scripts.hades_live_dogfood import Case

    cases = (
        Case("list", "list machines", "continuation", "assets", "assets"),
        Case("first", "first one", "continuation", "assets", "assets"),
        Case("general", "explain dns"),
    )
    selected = select_cases(cases, session_mode="fresh")
    assert [case.name for case in selected] == ["list", "general"]


def test_declared_selection_preserves_asset_and_continue_groups():
    selected = select_cases(CASES, suite="all", session_mode="declared")
    assets = [case for case in selected if case.group == "assets_reference"]
    continuation = [case for case in selected if case.group == "continuation"]
    assert [case.name for case in assets] == ["assets_list", "assets_reference"]
    assert [case.name for case in continuation] == ["continuation_start", "continuation_resume"]


def test_sampled_declared_selection_includes_preceding_continuation_prerequisite():
    selected = select_cases(CASES, suite="core", sample=6, seed=260826)
    names = [case.name for case in selected]
    assert names.index("assets_list") < names.index("assets_reference")
    assert names.index("continuation_start") < names.index("continuation_resume") if "continuation_resume" in names else True


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


@pytest.mark.parametrize(
    "prefix",
    ("memory_", "work_", "network_", "infra_", "assets_list", "assets_reference"),
)
def test_deterministic_cases_require_no_bounded_decision_index_or_approval(prefix):
    cases = [
        case for case in CASES
        if case.name.startswith(prefix)
        and case.family not in {"negative_near_miss", "security"}
    ]
    assert cases
    assert all(case.expect_bounded_decisions == 0 for case in cases)
    assert all(case.expect_tool_index_lookups == 0 for case in cases)
    assert all(case.expect_approvals == 0 for case in cases)


@pytest.mark.parametrize("bad", [0, -1])
def test_sample_must_be_positive(bad):
    with pytest.raises(ValueError, match="positive"):
        select_cases(CASES, sample=bad)


def test_cookie_file_reader_supports_netscape_and_plain_token(tmp_path):
    netscape = tmp_path / "cookies.txt"
    netscape.write_text("# Netscape HTTP Cookie File\n. localhost\tTRUE\t/\tFALSE\t0\todysseus_session\towner-token\n")
    assert cookie_from_file(str(netscape)) == "owner-token"

    plain = tmp_path / "token.txt"
    plain.write_text("owner-token\n")
    assert cookie_from_file(str(plain)) == "owner-token"


def test_live_result_exposes_bounded_decision_burden_without_raw_trace():
    from scripts.hades_live_dogfood import Case, assert_case

    result = {
        "answer_present": True,
        "bounded_action_decisions": 0,
        "internal_leak": False,
        "internal_error": False,
        "error": None,
    }
    assert assert_case(Case("read", "read", expect_bounded_decisions=0), result) == []
    result["bounded_action_decisions"] = 1
    assert "unexpected_bounded_decisions" in assert_case(
        Case("read", "read", expect_bounded_decisions=0), result,
    )
