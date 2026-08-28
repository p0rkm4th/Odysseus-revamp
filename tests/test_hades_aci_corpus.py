from benchmarks.hades_aci_corpus import CORPUS, corpus_summary


def test_frozen_aci_corpus_has_development_heldout_and_canary_splits():
    summary = corpus_summary()
    assert summary["case_count"] == 120
    assert summary["development_count"] == 96
    assert summary["held_out_count"] == 24
    assert summary["canary_count"] == 12
    assert len({case["id"] for case in CORPUS}) == 120


def test_corpus_expected_trajectories_keep_authority_out_of_model_burden():
    for case in CORPUS:
        expected = case["expected_trajectory"]
        assert "policy" in expected["framework"]
        assert "approval" in expected["framework"]
        assert "arbitrary_tool_id" in expected["must_not"]

