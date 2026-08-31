import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hades_test_impact", ROOT / "scripts" / "hades_test_impact.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_recipe_renderer_stays_at_coherent_slice_lane():
    result = MODULE.analyze(["src/result_renderers/recipe.py"])

    assert result["recommended_lane"] == "B"
    assert result["escalations"]["semantic"] is False


def test_shared_policy_change_escalates_without_running_release_lane_by_default():
    result = MODULE.analyze(["src/policy.py"])

    assert result["recommended_lane"] == "C"
    assert result["escalations"]["broad_authority"] is True


def test_docs_only_change_uses_edit_lane():
    result = MODULE.analyze(["specs/HADES_V1_CONVERGENCE_SPRINT.md"])

    assert result["recommended_lane"] == "A"
    assert result["impact_labels"] == ["non_executable"]


def test_retriever_change_escalates_semantic_but_not_authority_checks():
    result = MODULE.analyze(["src/action_retriever.py"])

    assert result["recommended_lane"] == "B"
    assert result["escalations"] == {
        "semantic": True,
        "broad_authority": False,
        "browser": False,
    }


def test_impact_reports_feature_and_capability_surfaces():
    result = MODULE.analyze([
        "src/domain_resolvers/recipe.py",
        "src/capability_registry.py",
    ])

    assert result["affected_modules"] == ["recipes"]
    assert result["affected_capabilities"] == ["*"]


def test_committed_diff_mode_is_explicit_and_does_not_use_dirty_worktree(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Completed:
            stdout = "src/domain_resolvers/recipe.py\n"

        return Completed()

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    assert MODULE.changed_paths("base-sha", "head-sha") == ["src/domain_resolvers/recipe.py"]
    assert calls == [["git", "diff", "--name-only", "base-sha", "head-sha"]]
