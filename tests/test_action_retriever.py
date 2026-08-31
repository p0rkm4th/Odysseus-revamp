from src.action_retriever import ActionRetriever
from src.capability_registry import ActionSpec, CapabilitySpec
from src.module_manager import ModuleManager, ModuleSpec


def _catalog():
    return {
        "recipe.manage": CapabilitySpec(
            "recipe.manage",
            {"scale": ActionSpec("scale"), "add": ActionSpec("add")},
            "Change or save owner recipes and ingredients.",
        ),
        "service.read": CapabilitySpec(
            "service.read",
            {"status": ActionSpec("status")},
            "Inspect whether a configured service is healthy or running.",
        ),
    }


def _manager(*, recipes=True):
    return ModuleManager(
        {
            "recipes": ModuleSpec("recipes", ("recipe.manage",)),
            "services": ModuleSpec("services", ("service.read",)),
        },
        enabled_modules={"recipes" if recipes else "services", "services"},
    )


def test_retriever_returns_canonical_high_recall_candidates():
    retriever = ActionRetriever(_catalog(), module_manager=_manager())
    candidates = retriever.retrieve("could you scale the recipe", top_k=3)

    assert candidates
    assert candidates[0].canonical_id == "recipe.manage.scale"
    assert "recipe" in candidates[0].matched_terms


def test_disabled_module_actions_never_enter_index_or_candidates():
    retriever = ActionRetriever(_catalog(), module_manager=_manager(recipes=False))

    assert retriever.indexed_action_count == 1
    assert retriever.retrieve("scale the recipe") == ()


def test_unsupported_request_is_empty_instead_of_nearest_mutation():
    retriever = ActionRetriever(_catalog(), module_manager=_manager())

    assert retriever.retrieve("record a deworming treatment for goat 14") == ()


def test_candidate_limit_is_bounded():
    retriever = ActionRetriever(_catalog(), module_manager=_manager())

    assert len(retriever.retrieve("recipe service", top_k=1)) == 1
