"""Compositional semantic predicates for harmless canonical reads.

This module is a derived intent projection, not a capability registry.  It
recognizes subject, ownership, and read semantics before provider inference so
ordinary paraphrases converge on the existing DomainContracts.
"""

from __future__ import annotations

import difflib
import re


_READ_REQUEST = re.compile(
    r"^(?:what|what's|whats|which|where|who|how\s+many|show|list|tell|whatcha|describe|summarize|give|provide|"
    r"review|display|remind|anything|do\s+i|have\s+i|how\s+much|you\s+know)\b",
    re.IGNORECASE,
)
_OWNER_SELF = re.compile(
    r"\b(?:about|on|bout)\s+(?:me|myself)\b|"
    r"\bwho\s+am\s+i(?:\s+to\s+you)?\b|"
    r"\bmy\s+(?:profile|lore|background|deal|story)\b",
    re.IGNORECASE,
)
_MEMORY_KNOWLEDGE = re.compile(
    r"\b(?:remember(?:ed|ing)?|memor(?:y|ies)|know(?:n)?|learn(?:ed|t)|"
    r"information|profile|rundown)\b",
    re.IGNORECASE,
)
_MEMORY_STORE_QUERY = re.compile(
    r"\b(?:what\s+(?:do|have)\s+you|anything\s+you|show\s+(?:me\s+)?what\s+you)\b"
    r".*\b(?:saved|stored|retained|kept)\b",
    re.IGNORECASE,
)
_WORK_SUBJECT = re.compile(
    r"\b(?:work|working|workload|"
    r"on\s+my\s+plate|got\s+(?:going|on)|keeping\s+me\s+busy|"
    r"doing(?:\s+(?:right\s+now|rn))?|"
    r"currently\s+in\s+progress|unfinished|active\s+projects?|"
    r"where(?:'d|\s+did)\s+(?:we|i)\s+leave\s+off|"
    r"outstanding\s+work|open\s+work)\b",
    re.IGNORECASE,
)
_WORK_OWNER = re.compile(
    r"\b(?:my|me|we|i(?:'m|\s+am)?|i\s+have|have\s+i|i(?:'ve)?\s+got)\b",
    re.IGNORECASE,
)
_ASSET_SUBJECT = re.compile(
    r"\b(?:it\s+assets?|assets?|tech(?:nical)?|computers?|machines?|hardware|"
    r"computational\s+(?:assets?|hardware)|boxes?|gear|"
    r"physical\s+(?:machines?|boxes|hosts?)|equipment|servers?|"
    r"gpus?|graphics\s+cards?|processors?|cpus?|ram|memory|storage|"
    r"motherboards?|nvme|ssds?|hard\s+drives?)\b",
    re.IGNORECASE,
)
_ASSET_MODEL = re.compile(
    r"\b(?:rtx|gtx|quadro|tesla|radeon|arc)\s*\d{3,5}s?\b|\b\d{4}s?\b",
    re.IGNORECASE,
)
_ASSET_OWNER = re.compile(
    r"\b(?:my|mah|mine|i\s+(?:actually\s+)?own|do\s+i(?:\s+actually)?\s+own|do\s+i\s+(?:have|got)|have\s+i|"
    r"i(?:'ve|\s+do)?\s+got|registered|recorded\s+for\s+me|known\s+to\s+me)\b",
    re.IGNORECASE,
)
_NETWORK_SUBJECT = re.compile(r"\b(?:network|lan|connection|connected)\b", re.IGNORECASE)
_OWNER_NETWORK = re.compile(
    r"\b(?:my|our|ours)\s+network\b|\bnetwork\s+(?:i(?:'m|\s+am)|we(?:'re|\s+are))\s+on\b",
    re.IGNORECASE,
)
_NETWORK_CONTEXT_DETAIL = re.compile(
    r"\b(?:default\s+route|interface\s+(?:carrying|has|is)|"
    r"network\s+context|subnet|where\s+am\s+i\s+connected)\b",
    re.IGNORECASE,
)
_HOUSEHOLD_SUBJECT = re.compile(
    r"\b(?:household|pantry|kitchen|freezer|fridge|refrigerator|cabinet|"
    r"groceries|grocery|shopping|stock|inventory|food|ingredients?)\b",
    re.IGNORECASE,
)
_HOUSEHOLD_STATE = re.compile(
    r"\b(?:about\s+to\s+expire|expir(?:e|ing|y)|run(?:ning)?\s+out|"
    r"ran\s+out|low\s+on|in\s+the\s+(?:freezer|fridge|refrigerator|pantry)|"
    r"how\s+(?:much|many)\s+.+\s+do\s+(?:i|we)\s+have|"
    r"what\s+did\s+(?:i|we)\s+run\s+out\s+of)",
    re.IGNORECASE,
)
_RECIPE_READ = re.compile(
    r"\b(?:what|which|show|list|find|search)\b.*\brecipes?\b|"
    r"\brecipes?\b.*\b(?:do\s+(?:i|we)\s+have|saved|stored|on\s+file)\b",
    re.IGNORECASE,
)
_RECIPE_COOKING_HISTORY = re.compile(
    r"\b(?:which|what)\s+recipes?\s+(?:did|have)\s+(?:i|we)\s+(?:cook|make|prepare)\b|"
    r"\b(?:what|which)\s+(?:did|have)\s+(?:i|we)\s+(?:cook|make|prepare)\b.*\b(?:last|yesterday|earlier|recently)\b",
    re.IGNORECASE,
)
_RECIPE_COVERAGE = re.compile(
    r"\b(?:can\s+i\s+make|do\s+i\s+have\s+everything|pantry\s+coverage|"
    r"missing\s+ingredients?)\b.*\b(?:recipe|meal|chili|dinner|dish)\b|"
    r"\b(?:check|show)\b.*\b(?:pantry\s+coverage|missing\s+ingredients?)\b",
    re.IGNORECASE,
)
_RECIPE_PANTRY_COVERAGE = re.compile(
    r"\b(?:can|could)\s+(?:i|we)\s+(?:make|cook|fix|whip\s+up|throw\s+together)\b"
    r".{0,80}\b(?:with|w|from)\b.{0,50}\b(?:what|whatever)\s+(?:i|we)\s+(?:have|got)\b|"
    r"\bwhat\s+can\s+(?:i|we)\s+(?:make|cook|fix|whip\s+up|throw\s+together)\b"
    r".{0,50}\b(?:with|w|from)\b.{0,50}\b(?:what|whatever)\s+(?:i|we)\s+(?:have|got)\b|"
    r"\banything\s+(?:i|we)\s+can\s+(?:make|cook|fix)\b.{0,50}\b(?:with|w|from)\b"
    r".{0,50}\b(?:what|whatever)\s+(?:i|we)\s+(?:have|got)\b",
    re.IGNORECASE,
)
_RECIPE_SCALE = re.compile(
    r"\b(?:scale|resize|adjust)\b.{0,40}\b(?:to\s+)?(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+servings?\b",
    re.IGNORECASE,
)
_RECIPE_SHOPPING_FOLLOWUP = re.compile(
    r"\bwhat\s+(?:do\s+)?i\s+need\s+to\s+buy\s+for\s+(?:this|that|it)\b|"
    r"\bwhat\s+ingredients?\s+do\s+i\s+need\s+for\s+(?:this|that|it)\b",
    re.IGNORECASE,
)
_RECIPE_NAMED_DETAIL = re.compile(
    r"^(?:reload[.!?]\s*)?what(?:'s|\s+is)\s+in\s+(?:the\s+)?[A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*)+\s*\??$",
)
_SERVING_NUMBER = re.compile(
    r"\b(?:to\s+)?(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+servings?\b",
    re.IGNORECASE,
)
_HOST_INSPECTION = re.compile(
    r"\b(?:inspect|check|show|read|explore|scan)\s+(?:me\s+)?"
    r"(?:(?:the|this|current|local|my|your)\s+){0,2}"
    r"(?:host|system|hardware|computational\s+assets?)\b|"
    r"\btell\s+me\s+about\s+(?:(?:the|this|current|local|my|your)\s+){0,2}"
    r"(?:host|system|hardware|computational\s+assets?)\b",
    re.IGNORECASE,
)
_CURRENT_STATE = re.compile(
    r"\b(?:current(?:ly)?|right\s+now|now|network\s+context|am\s+i\s+on|connected\s+to|"
    r"where\s+am\s+i\s+connected)\b",
    re.IGNORECASE,
)
_INFRASTRUCTURE_STATUS = re.compile(
    r"\b(?:(?:what(?:'s|s|\s+is)?)\s+running(?:\s+(?:in|on)\s+\w+)?|"
    r"what\s+services?\s+(?:(?:are|is)\s+)?(?:up|alive|down|unhealthy|failing)|"
    r"anything\s+(?:un)?healthy|what(?:'s|\s+is)\s+up|"
    r"what\s+services?\s+(?:(?:are|is)\s+)?(?:up|alive)|"
    r"(?:are|is)\s+(?:my\s+)?services?\s+(?:up|alive)|"
    r"(?:is|are)\s+(?:everything|the\s+stack)\s+(?:healthy|up|okay|ok|good)|"
    r"anything\s+(?:wrong|broken|dead|down|unhealthy|failing)|"
    r"what(?:'s|s|\s+is)?(?:\s+(?:the|hell|damn|is|actually|currently)){0,4}\s+"
    r"(?:dead|broken|busted|down)|"
    r"(?:how(?:'s|s|\s+is)?)\s+(?:hades|the\s+stack|everything)\s+"
    r"(?:doing|looking|running|holding\s+up)|"
    r"(?:are|is)\s+(?:we|everything)\s+(?:good|fine|okay|ok)|"
    r"how(?:'s|s|\s+is)\s+the\s+stack)\b",
    re.IGNORECASE,
)
_GENERAL_EXPLANATION = re.compile(
    r"\b(?:why|explain|what\s+(?:is|are|does)|how\s+does|"
    r"difference\s+between|versus|tell\s+me\s+about\s+(?:the\s+)?"
    r"(?:memory|network))\b",
    re.IGNORECASE,
)

# Discourse markers are semantic noise, not routing vocabulary.  Normalize a
# bounded prefix so ordinary conversation ("alright, what am I working on?")
# reaches the same predicates as the terse form without adding sentence-specific
# routes.
_DISCOURSE_PREFIX = re.compile(
    r"^(?:(?:okay|ok|alright|so|like|uh|um|well|anyway|hey|yo)\b[\s,]*)+",
    re.IGNORECASE,
)

# Owner language often contains a single dropped, transposed, or duplicated
# character (for example ``outsanding``).  Normalize only words that belong to
# this module's routing vocabulary; arbitrary item names, hostnames, and
# recipe text must remain unchanged.  This keeps typo tolerance compositional
# instead of accumulating one regex per observed prompt.
_FUZZY_ROUTING_WORDS = frozenset({
    "about", "active", "assets", "computers", "connected", "current",
    "expire", "food", "freezer", "got", "have", "household", "ingredient",
    "ingredients", "kitchen", "machine", "machines", "memory", "network",
    "outstanding", "pantry", "project", "projects", "recipe", "recipes",
    "remember", "storage", "tasks", "work", "working", "currently",
})


def _normalize_routing_typos(value: str) -> str:
    """Correct bounded edit-distance slips in known routing vocabulary."""
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) < 5 or token in _FUZZY_ROUTING_WORDS:
            return token
        candidates = [word for word in _FUZZY_ROUTING_WORDS if abs(len(token) - len(word)) <= 2]
        best = max(
            candidates,
            key=lambda word: difflib.SequenceMatcher(None, token, word).ratio(),
            default=None,
        )
        if best is not None and difflib.SequenceMatcher(None, token, best).ratio() >= 0.84:
            return best
        return token

    return re.sub(r"\b[a-z][a-z'-]*\b", replace, value)


def _normalized(text: str) -> str:
    value = str(text or "").strip().casefold().replace("’", "'")
    # Small, domain-neutral spelling normalization keeps ordinary keyboard
    # slips from changing the semantic class.  This is intentionally a token
    # normalization layer, not a list of benchmark sentences.
    tokens = {
        "abotu": "about", "abt": "about", "bout": "about",
        "yuo": "you", "teh": "the", "wht": "what", "whts": "whats",
    }
    value = re.sub(r"\b[^\s]+\b", lambda match: tokens.get(match.group(0), match.group(0)), value)
    value = re.sub(r"\s+", " ", value).strip(" .?!")
    value = _DISCOURSE_PREFIX.sub("", value).strip(" .?!")
    return _normalize_routing_typos(value)


def is_recipe_pantry_coverage_query(text: str) -> bool:
    """Recognize a recipe feasibility request expressed through pantry language."""
    query = _normalized(text)
    return bool(_RECIPE_COVERAGE.search(query) or _RECIPE_PANTRY_COVERAGE.search(query))


def is_recipe_pantry_candidates_query(text: str) -> bool:
    """Recognize pantry feasibility requests that do not name one recipe."""
    query = _normalized(text)
    return bool(_RECIPE_PANTRY_COVERAGE.search(query)) and not bool(
        re.search(r"\b(?:this|that|the|a|one|named)\s+(?:recipe|meal|dish)\b", query)
    )


def deterministic_read_concept(text: str) -> str | None:
    """Return an existing DomainContract concept for an unambiguous read."""
    query = _normalized(text)
    if _RECIPE_NAMED_DETAIL.search(str(text or "").strip()):
        return "RECIPE"
    # Operational health questions also commonly begin with ``are``/``is``
    # ("Are my services alive?", "Is anything unhealthy?").  Let the
    # already-composed infrastructure predicate admit those forms without
    # broadening ordinary ``is ...`` questions into canonical reads.
    if not query or (
        not _READ_REQUEST.search(query)
        and not _INFRASTRUCTURE_STATUS.search(query)
        and not _RECIPE_READ.search(query)
        and not is_recipe_pantry_coverage_query(query)
        and not _RECIPE_SCALE.search(query)
        and not _RECIPE_SHOPPING_FOLLOWUP.search(query)
        and not _HOST_INSPECTION.search(query)
        and not (
            _NETWORK_SUBJECT.search(query)
            and re.search(r"\b(?:current(?:ly)?|now|figure\s+it\s+out|explore)\b", query)
        )
        and not (
            _ASSET_SUBJECT.search(query)
            and _ASSET_OWNER.search(query)
            and re.search(r"\b(?:tell\s+me|what|which|where|show|how\s+many)\b", query)
        )
        and not (_HOUSEHOLD_SUBJECT.search(query) or _HOUSEHOLD_STATE.search(query))
    ):
        return None
    if re.search(r"\bwhat\s+should\s+(?:you|i)\s+remember\b", query):
        return None
    if _MEMORY_STORE_QUERY.search(query) and not re.search(
        r"\b(?:file|files|document|documents|secret|secrets|password|passwords)\b",
        query,
    ):
        return "MEMORY"
    if _RECIPE_COOKING_HISTORY.search(query):
        return "RECIPE"
    if _RECIPE_SHOPPING_FOLLOWUP.search(query):
        return "RECIPE"
    # Expiry/stock state is an inventory question even when the phrase starts
    # with the generic "what is" interrogative.
    if is_recipe_pantry_coverage_query(query) and not re.search(
        r"\b(?:what\s+is|how\s+does|explain|define)\b", query,
    ):
        return "RECIPE"
    if _RECIPE_SCALE.search(query) and re.search(r"\b(?:recipe|meal|dish|servings?)\b", query):
        return "RECIPE"
    if _RECIPE_READ.search(query) and not re.search(
        r"\b(?:what\s+is|how\s+does|explain|define)\b", query,
    ):
        return "RECIPE"
    if _HOUSEHOLD_STATE.search(query) and not re.search(
        r"\b(?:explain|define|how\s+does)\b", query,
    ) and not (
        # A property/count question about owner hardware can match the broad
        # ``how much/many ... do I have`` inventory predicate.  Preserve the
        # canonical asset owner when the object is RAM/GPU/storage/etc.; this
        # is semantic precedence, not another phrase route.
        (_ASSET_SUBJECT.search(query) or _ASSET_MODEL.search(query))
        and _ASSET_OWNER.search(query)
        and re.search(r"\b(?:what|which|where|show|list|how\s+many|how\s+much)\b", query)
    ):
        return "HOUSEHOLD_ITEM"
    # A noun such as "memory" or "network" is not by itself an owner-state
    # read. Explanations and definitions belong on the general-model floor
    # unless the turn also carries an explicit owner/current-state subject.
    if _GENERAL_EXPLANATION.search(query) and not _INFRASTRUCTURE_STATUS.search(query) and not (
        _OWNER_SELF.search(query)
        or re.search(r"\b(?:my|mine|our|ours|we|i\s+am|i'm|right\s+now|current(?:ly)?)\b", query)
        or re.search(r"\bwe\b.{0,20}\bworking\b", query)
    ):
        return None

    # Explicit owner-knowledge predicates outrank narrower nouns: "what do
    # you remember about my work" asks Memory what it retains, not Work state.
    if _MEMORY_KNOWLEDGE.search(query) and (
        _OWNER_SELF.search(query) or re.search(r"\babout\s+my\b", query)
    ):
        return "MEMORY"
    if (
        _OWNER_SELF.search(query)
        and (_MEMORY_KNOWLEDGE.search(query) or re.search(r"\bgot\s+on\s+(?:me|myself)\b", query))
    ):
        return "MEMORY"
    if (
        _WORK_SUBJECT.search(query)
        and (
            _WORK_OWNER.search(query)
            or re.search(r"\bwhere(?:'d|\s+did)\s+(?:we|i)\s+leave\s+off\b", query)
            or re.search(r"\bprojects?\b", query)
            or re.search(r"\b(?:currently|right\s+now|in\s+progress)\b", query)
        )
        and not re.search(r"\b(?:projects?|tasks?|goals?|commitments?|runs?|missions?|watches?)\b", query)
    ):
        return "WORK"
    # Household reads are owner-state projections over the existing inventory
    # service.  The state predicate covers natural omissions such as
    # "how much milk do we have" and "what is about to expire" without
    # promoting ordinary food definitions or recipe advice into inventory
    # reads.
    if (
        (_HOUSEHOLD_SUBJECT.search(query) or _HOUSEHOLD_STATE.search(query))
        and not re.search(r"\b(?:what\s+is|what's|how\s+does|explain|define)\b.*\b(?:recipe|ingredient|food|kitchen)\b", query)
        and not (
            (_ASSET_SUBJECT.search(query) or _ASSET_MODEL.search(query))
            and _ASSET_OWNER.search(query)
            and re.search(r"\b(?:what|which|where|show|list|how\s+many|how\s+much)\b", query)
        )
    ):
        return "HOUSEHOLD_ITEM"
    if re.search(r"\b(?:review|show|list|summarize)\b.*\b(?:outstanding|open|active)\s+work\b", query):
        return "WORK"
    if re.search(r"\bwhat(?:'s|s|\s+is)?\s+(?:outstanding|open|active)\b", query):
        return "WORK"
    if (
        _WORK_SUBJECT.search(query)
        and re.search(r"\bprojects?\b", query)
        and re.search(r"\b(?:current(?:ly)?|active|progress|going|have|got)\b", query)
    ):
        return "WORK"
    # Owner-scoped collection language refers to the canonical asset catalog;
    # it must win over the broader host-observation vocabulary.  Explicit
    # owner hardware requests such as "tell me about my hardware" therefore
    # remain asset reads, while a later host-inspection branch still handles
    # "inspect this host" and "scan the current system".
    if (_ASSET_SUBJECT.search(query) or _ASSET_MODEL.search(query)) and _ASSET_OWNER.search(query):
        return "TECHNICAL_ASSET"
    if (
        (_ASSET_SUBJECT.search(query) or _ASSET_MODEL.search(query))
        and _ASSET_OWNER.search(query)
        and re.search(r"\b(?:tell\s+me|what|which|where|show|how\s+many)\b", query)
    ):
        return "TECHNICAL_ASSET"
    # Conversational collection questions can omit the possessive after an
    # owner context (for example, "what kinda computers?"). This is still a
    # read-only projection and never selects a host or grants execution.
    if (
        _ASSET_SUBJECT.search(query)
        and _READ_REQUEST.search(query)
        and not re.search(r"\b(?:network|lan|devices?\s+look|look\s+like\s+servers?)\b", query)
        and not re.search(r"\b(?:buy|purchase|recommend|suggest|should\s+i|worth)\b", query)
        and not re.search(r"\b(?:how\s+do|what\s+is|define|explain)\b", query)
    ):
        return "TECHNICAL_ASSET"
    # A hardware exploration request is a bounded host observation, not an
    # arbitrary scan or shell request.  Keep this ahead of the remaining
    # generic asset fallback so "scan your hardware" reaches inspect_host.
    if _HOST_INSPECTION.search(query) and re.search(
        r"\b(?:hardware|computational\s+assets?|system|host)\b",
        query,
    ) and re.search(r"\b(?:explore|inspect|check|scan|tell\s+me\s+about)\b", query) and not re.search(
        r"\b(?:network|lan|subnet|service|daemon)\b", query,
    ):
        return "HOMELAB_HOST"
    if _HOST_INSPECTION.search(query) and not re.search(
        r"\b(?:network|lan|subnet|scan|discover|service|daemon)\b", query,
    ):
        return "HOMELAB_HOST"
    if (
        re.search(r"\b(?:network|lan|wifi|wi-fi|connection|connected)\b", query)
        or _NETWORK_CONTEXT_DETAIL.search(query)
    ) and (
        _CURRENT_STATE.search(query)
        or _OWNER_NETWORK.search(query)
        or re.search(r"\bwhere(?:'s|\s+is)\s+(?:hades|this\s+machine)\s+connected\b", query)
        or _NETWORK_CONTEXT_DETAIL.search(query)
        or re.search(r"\b(?:figure\s+it\s+out|explore)\b", query)
    ):
        return "NETWORK"
    # Operational status questions share the existing harmless service-status
    # Action.  Keep this narrow enough that ordinary explanations such as
    # "what is a service?" remain general-model questions.
    if (
        _INFRASTRUCTURE_STATUS.search(query)
        and re.search(r"\b(?:remote|ssh|over\s+ssh|via\s+ssh)\b", query)
        and re.search(r"\b(?:host|server|machine|system)\b", query)
    ):
        return "HOMELAB_HOST"
    if _INFRASTRUCTURE_STATUS.search(query):
        return "SERVICE"
    # A broad self-description request with no narrower subject is an
    # owner-self-knowledge read.  This covers "tell me about me" compositionally
    # (read/report verb + owner-self subject), without matching arbitrary
    # "tell me about <entity>" requests.
    if _OWNER_SELF.search(query):
        return "MEMORY"
    return None


def deterministic_read_view(text: str, concept: str | None) -> str | None:
    """Return a semantic view over an existing DomainContract, when evident."""
    query = _normalized(text)
    if concept == "NETWORK" and _CURRENT_STATE.search(query):
        return "context"
    if concept == "NETWORK" and _NETWORK_CONTEXT_DETAIL.search(query):
        return "context"
    if concept == "NETWORK" and re.search(r"\bwhere(?:'s|\s+is)\s+(?:hades|this\s+machine)\s+connected\b", query):
        return "context"
    if concept == "WORK" and re.search(r"\b(?:attention|on\s+my\s+plate|needs?\s+attention)\b", query):
        return "attention"
    return None


def deterministic_recipe_servings(text: str) -> str | None:
    """Return a normalized serving target for an explicit recipe scaling read."""
    match = _SERVING_NUMBER.search(_normalized(text))
    if not match:
        return None
    words = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12",
    }
    return words.get(match.group(1).casefold(), match.group(1))
