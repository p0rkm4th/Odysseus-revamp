"""Small, high-recall retrieval over enabled canonical ActionSpecs.

Retrieval is deliberately only candidate generation.  It never selects an
executor, grants authority, or treats a nearest match as success.  The
runtime may pass the returned candidates to a bounded model decision, or
return ``NO_APPLICABLE_ACTION`` when the catalog has no plausible match.

The first implementation is dependency-free lexical retrieval.  Keeping the
index in-process makes it cheap for the V1 catalog and leaves room for an
optional compact embedding scorer without introducing another service or
semantic authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Iterable, Mapping

from src.capability_registry import ActionSpec, CapabilitySpec
from src.module_manager import ModuleManager, default_module_manager


_TOKEN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    "a an and are can do for from have i is me my of on please show the to "
    "what was with you".split()
)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in _TOKEN.findall(value.casefold()) if token not in _STOP_WORDS)


@dataclass(frozen=True)
class ActionCandidate:
    """A canonical action and retrieval evidence, with no execution authority."""

    capability_id: str
    action_id: str
    score: float
    matched_terms: tuple[str, ...]

    @property
    def canonical_id(self) -> str:
        return f"{self.capability_id}.{self.action_id}"


@dataclass(frozen=True)
class _ActionDocument:
    capability_id: str
    action_id: str
    spec: ActionSpec
    terms: tuple[str, ...]
    term_frequency: Mapping[str, int]


class ActionRetriever:
    """Retrieve a bounded candidate neighborhood from enabled actions."""

    def __init__(
        self,
        capabilities: Mapping[str, CapabilitySpec],
        *,
        module_manager: ModuleManager | None = None,
    ) -> None:
        self._modules = module_manager or default_module_manager()
        enabled = self._modules.enabled_capability_ids()
        self._documents = tuple(
            _ActionDocument(
                capability_id=capability_id,
                action_id=action_id,
                spec=spec,
                terms=_tokens(
                    f"{capability_id} {action_id} {capability.description} "
                    f"{' '.join(spec.effects)} {' '.join(spec.writes)}"
                ),
                term_frequency=Counter(
                    _tokens(
                        f"{capability_id} {action_id} {capability.description} "
                        f"{' '.join(spec.effects)} {' '.join(spec.writes)}"
                    )
                ),
            )
            for capability_id, capability in capabilities.items()
            if capability_id in enabled
            for action_id, spec in capability.actions.items()
            if spec.known
        )
        document_frequency = Counter(
            term for document in self._documents for term in set(document.terms)
        )
        self._idf = {
            term: math.log((1 + len(self._documents)) / (1 + count)) + 1.0
            for term, count in document_frequency.items()
        }

    @classmethod
    def from_default_registry(cls, module_manager: ModuleManager | None = None) -> "ActionRetriever":
        from src.capability_registry import CAPABILITY_REGISTRY

        return cls(CAPABILITY_REGISTRY, module_manager=module_manager)

    @property
    def indexed_action_count(self) -> int:
        return len(self._documents)

    def retrieve(self, query: str, *, top_k: int = 5, min_score: float = 0.0) -> tuple[ActionCandidate, ...]:
        """Return at most ``top_k`` enabled actions with positive evidence.

        An empty result is meaningful: callers must represent it as a
        capability gap/clarification, never substitute the nearest action.
        ``min_score`` is intentionally caller-controlled so evaluation can
        inspect the full positive candidate set without changing policy.
        """
        if top_k < 1:
            return ()
        query_terms = Counter(_tokens(query))
        if not query_terms:
            return ()
        scored: list[ActionCandidate] = []
        for document in self._documents:
            overlap = set(query_terms) & set(document.term_frequency)
            if not overlap:
                continue
            score = sum(self._idf.get(term, 1.0) * query_terms[term] for term in overlap)
            # Prefer a compact exact action/capability signal without making
            # domain labels an execution gate.
            exact_terms = set(_tokens(query)) & set(_tokens(document.action_id))
            score += 0.5 * len(exact_terms)
            if score < min_score:
                continue
            scored.append(ActionCandidate(
                capability_id=document.capability_id,
                action_id=document.action_id,
                score=score,
                matched_terms=tuple(sorted(overlap)),
            ))
        scored.sort(key=lambda candidate: (-candidate.score, candidate.canonical_id))
        return tuple(scored[:top_k])


__all__ = ["ActionCandidate", "ActionRetriever"]
