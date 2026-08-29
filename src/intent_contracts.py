"""Bounded semantic intent frames and projections onto canonical ActionSpecs.

This is a resolver layer, not an executor or a second capability registry.
Natural-language classification may be imperfect; the returned contract must
still resolve through the existing Capability -> ActionSpec -> ToolBinding
chain before a tool can run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import ipaddress
import json
import logging
import re
from typing import Any, Mapping

from src.capability_registry import ActionSpec, capability_for_id
from src.tool_bindings import binding_for_tool
from src.deterministic_reads import deterministic_read_concept, deterministic_read_view, deterministic_recipe_servings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecipeDraft:
    """Validated, untrusted recipe proposal before canonical persistence.

    This is deliberately a small transport schema.  It is not a recipe store
    and it cannot create state; the InventoryService remains the authority for
    validation, persistence, and readback.
    """

    name: str
    servings: int | float
    ingredients: tuple[dict[str, Any], ...]
    instructions: str
    source_url: str | None = None
    provenance: str = "owner_text"

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "add",
            "name": self.name,
            "servings": self.servings,
            "ingredients": [dict(item) for item in self.ingredients],
            "instructions": self.instructions,
            "provenance": self.provenance,
        }
        if self.source_url:
            payload["source_url"] = self.source_url
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RecipeDraft":
        """Validate a proposed draft before it reaches the recipe owner."""
        if not isinstance(payload, Mapping):
            raise ValueError("recipe draft must be an object")
        name = str(payload.get("name") or "").strip()
        instructions = str(payload.get("instructions") or "").strip()
        ingredients = payload.get("ingredients")
        if not name or len(name) > 200 or not instructions or not isinstance(ingredients, list):
            raise ValueError("recipe draft requires a name, ingredients, and instructions")
        if not 1 <= len(ingredients) <= 200:
            raise ValueError("recipe draft must contain 1-200 ingredients")
        normalized: list[dict[str, Any]] = []
        for item in ingredients:
            if not isinstance(item, Mapping):
                raise ValueError("recipe ingredients must be objects")
            item_name = str(item.get("name") or "").strip()
            unit = str(item.get("unit") or "").strip().lower()
            if not item_name or not unit:
                raise ValueError("each recipe ingredient needs a name and unit")
            try:
                quantity = float(item.get("quantity"))
            except (TypeError, ValueError) as exc:
                raise ValueError("each recipe ingredient needs a numeric quantity") from exc
            if quantity <= 0:
                raise ValueError("recipe ingredient quantities must be positive")
            normalized.append({"name": item_name[:200], "quantity": quantity, "unit": unit[:40],
                               "optional": bool(item.get("optional", False))})
        try:
            servings = float(payload.get("servings", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("recipe servings must be numeric") from exc
        if servings <= 0:
            raise ValueError("recipe servings must be positive")
        if servings.is_integer():
            servings = int(servings)
        source_url = str(payload.get("source_url") or "").strip() or None
        if source_url and not re.match(r"^https?://", source_url, re.IGNORECASE):
            raise ValueError("recipe source_url must use http or https")
        return cls(name[:200], servings, tuple(normalized), instructions[:20000],
                   source_url, str(payload.get("provenance") or "owner_import")[:80])


def _recipe_section(text: str, header: str, next_header: str | None = None) -> str | None:
    boundary = rf"\b{header}\s*:\s*"
    tail = rf"(?=\s+\b{next_header}\s*:\s*|\Z)" if next_header else r"\Z"
    match = re.search(boundary + rf"(?P<body>.+?){tail}", text, re.IGNORECASE | re.DOTALL)
    return match.group("body").strip() if match else None


def _recipe_name(text: str) -> str | None:
    patterns = (
        # Natural owner wording: "as \"Name\":" or "called Name".
        r"\bas\s+[\"'](?P<name>[^\"']{1,200})[\"']\s*:",
        r"\bfor\s+the\s+name\s*,?\s*use\s+[\"'](?P<name>[^\"']{1,200})[\"']",
        r"\b(?:called|named)\s+[\"']?(?P<name>[^\"'\n:.]{1,200})[\"']?\s*[:.]",
        # Existing compact form: "recipe: Name. Ingredients: ...".
        r"\brecipe\b(?:\s+(?:to\s+)?(?:my\s+)?recipes?)?\s*:\s*"
        r"(?P<name>.+?)(?=\.\s*ingredients\s*:|\s+ingredients\s*:|\n\s*ingredients\s*:)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            name = " ".join(match.group("name").strip().strip("\"'").split())
            if name:
                return name[:200]
    return None


def _recipe_ingredients(section: str) -> list[dict[str, Any]] | None:
    unit_words = (
        r"teaspoons?|tsp|tablespoons?|tbsp|cups?|ounces?|oz|pounds?|lbs?|"
        r"grams?|g|kilograms?|kg|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l|"
        r"cloves?|cans?|packages?|slices?|pieces?"
    )
    # Newline-separated recipe lists are the normal long-paste shape.  Keep
    # comma/semicolon splitting for the compact owner acceptance shape.
    raw_lines = [line.strip() for line in section.splitlines() if line.strip()]
    if len(raw_lines) <= 1:
        raw_lines = re.split(r",|\s*;\s*|\s+and\s+(?=\d+(?:\.\d+)?\s)", section)
    ingredients: list[dict[str, Any]] = []
    for raw in raw_lines:
        item = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", raw).strip().strip(".")
        # Common recipe sites use Unicode vulgar fractions and a mixed form
        # such as ``1½ cups``. Normalize those presentation forms before the
        # conservative quantity parser; this does not invent an amount.
        fraction_values = {"¼": ".25", "½": ".5", "¾": ".75", "⅓": ".333333", "⅔": ".666667", "⅛": ".125", "⅜": ".375", "⅝": ".625", "⅞": ".875"}
        for glyph, value in fraction_values.items():
            item = item.replace(glyph, value if item[:1].isdigit() else value)
        item = re.sub(r"\bof\s+", "", item, count=1, flags=re.IGNORECASE)
        match = re.match(
            rf"(?P<quantity>\d+(?:\.\d+)?|\.\d+|\d+\s*/\s*\d+)\s*"
            rf"(?:(?P<unit>{unit_words})\.?\s+)?(?P<name>.+)$",
            item, re.IGNORECASE,
        )
        if not match:
            return None
        quantity_text = match.group("quantity").replace(" ", "")
        if "/" in quantity_text:
            numerator, denominator = quantity_text.split("/", 1)
            quantity: float = float(numerator) / float(denominator)
        else:
            quantity = float(quantity_text)
        ingredients.append({
            "name": match.group("name").strip(),
            "quantity": quantity,
            "unit": (match.group("unit") or "each").strip().lower(),
        })
    return ingredients[:200] or None


def recipe_create_draft(query: str) -> RecipeDraft | None:
    """Extract and validate an explicit owner recipe draft.

    The extractor accepts both compact and pasted sectioned recipes. It is
    intentionally conservative: missing/ambiguous ingredients or instructions
    produce no effectful payload rather than a guessed recipe.
    """
    text = str(query or "").strip()
    if not text:
        return None
    name = _recipe_name(text)
    ingredients_text = _recipe_section(text, "ingredients", "instructions")
    instructions = _recipe_section(text, "instructions")
    if not name or not ingredients_text or not instructions:
        return None
    ingredients = _recipe_ingredients(ingredients_text)
    if not ingredients or not instructions.strip():
        return None
    servings_match = re.search(r"\b(?:serves?|servings?)\s*[:]?\s*(\d+(?:\.\d+)?)", text, re.I)
    servings: int | float = float(servings_match.group(1)) if servings_match else 1
    if isinstance(servings, float) and servings.is_integer():
        servings = int(servings)
    url_match = re.search(r"https?://[^\s)>]+", text, re.I)
    return RecipeDraft(
        name=name,
        servings=servings,
        ingredients=tuple(ingredients),
        instructions=instructions.strip()[:20000],
        source_url=url_match.group(0).rstrip(".,") if url_match else None,
    )


def recipe_import_draft(
    source_text: str | None,
    *,
    source_url: str | None = None,
    requested_name: str | None = None,
) -> RecipeDraft | None:
    """Prepare a RecipeDraft from bounded untrusted text or schema.org JSON-LD.

    Fetching is intentionally not done here.  Callers may supply evidence from
    the existing public-fetch tool, but only this validated draft may proceed
    to the effectful recipe owner.
    """
    text = str(source_text or "").strip()
    draft = recipe_create_draft(text) if text else None
    if draft is None:
        json_text = text
        structured_marker = re.search(r"<!--\s*RECIPE_JSONLD:(?P<body>.*?)\s*-->", text, re.I | re.S)
        if structured_marker:
            json_text = structured_marker.group("body").strip()
        script = re.search(
            r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
            text, re.IGNORECASE | re.DOTALL,
        )
        if script and not structured_marker:
            json_text = script.group("body").strip()
        if json_text.startswith("```"):
            lines = json_text.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                json_text = "\n".join(lines[1:-1]).strip()
        if not json_text.startswith(("{", "[")):
            json_text = ""
        try:
            value: Any = json.loads(json_text) if json_text else None
        except (TypeError, ValueError):
            value = None
        # A bounded vision extractor may return the validated draft shape
        # rather than schema.org JSON-LD.  Treat it exactly like any other
        # untrusted proposal: RecipeDraft.from_payload is the gate and no
        # persistence occurs here.
        if isinstance(value, Mapping) and "ingredients" in value and "instructions" in value:
            try:
                draft = RecipeDraft.from_payload(value)
            except (TypeError, ValueError):
                draft = None
            if draft:
                if source_url:
                    draft = replace(draft, source_url=str(source_url).strip(), provenance="import_evidence")
                if requested_name and str(requested_name).strip():
                    draft = replace(draft, name=str(requested_name).strip()[:200])
                return draft
        candidates = value if isinstance(value, list) else [value]
        if isinstance(value, Mapping) and isinstance(value.get("@graph"), list):
            candidates.extend(value["@graph"])
        recipe = next((item for item in candidates if isinstance(item, Mapping) and (
            item.get("@type") == "Recipe" or "Recipe" in (item.get("@type") or [])
        )), None)
        if recipe:
            raw_ingredients = recipe.get("recipeIngredient")
            raw_instructions = recipe.get("recipeInstructions")
            if isinstance(raw_ingredients, list) and isinstance(raw_instructions, list):
                raw_instructions = "\n".join(
                    str(item.get("text") if isinstance(item, Mapping) else item).strip()
                    for item in raw_instructions
                )
            ingredients: list[dict[str, Any]] = []
            if isinstance(raw_ingredients, list):
                for item in raw_ingredients:
                    parsed = _recipe_ingredients(str(item))
                    if parsed and len(parsed) == 1:
                        ingredients.extend(parsed)
                    else:
                        ingredients = []
                        break
            if recipe.get("name") and ingredients and str(raw_instructions or "").strip():
                yield_text = str(recipe.get("recipeYield") or "1")
                servings_match = re.search(r"\d+(?:\.\d+)?", yield_text)
                servings: int | float = float(servings_match.group(0)) if servings_match else 1
                if isinstance(servings, float) and servings.is_integer():
                    servings = int(servings)
                draft = RecipeDraft(
                    name=str(recipe["name"]).strip()[:200], servings=servings,
                    ingredients=tuple(ingredients[:200]), instructions=str(raw_instructions).strip()[:20000],
                    provenance="schema_org_jsonld",
                )
    if draft and source_url:
        draft = replace(draft, source_url=str(source_url).strip(), provenance="import_evidence")
    if draft and requested_name and str(requested_name).strip():
        draft = replace(draft, name=str(requested_name).strip()[:200])
    return draft


def recipe_import_review(source_text: str | None, *, source_url: str | None = None) -> dict[str, Any]:
    """Describe why an untrusted recipe source needs human review.

    This is a bounded diagnostic projection only. It deliberately does not
    return a persistence-ready draft, so incomplete source evidence cannot
    reach InventoryService as a mutation.
    """
    text = str(source_text or "").strip()
    json_text = text
    marker = re.search(r"<!--\s*RECIPE_JSONLD:(?P<body>.*?)\s*-->", text, re.I | re.S)
    script = re.search(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
        text, re.I | re.S,
    )
    if marker:
        json_text = marker.group("body").strip()
    elif script:
        json_text = script.group("body").strip()
    try:
        value: Any = json.loads(json_text) if json_text.startswith(("{", "[")) else None
    except (TypeError, ValueError):
        value = None
    candidates = value if isinstance(value, list) else [value]
    if isinstance(value, Mapping) and isinstance(value.get("@graph"), list):
        candidates.extend(value["@graph"])
    recipe = next((item for item in candidates if isinstance(item, Mapping) and (
        item.get("@type") == "Recipe" or "Recipe" in (item.get("@type") or [])
    )), None)
    if not recipe:
        return {"status": "NEEDS_REVIEW", "source_url": source_url, "missing_fields": ["verified recipe structure"]}
    ingredients = recipe.get("recipeIngredient") if isinstance(recipe.get("recipeIngredient"), list) else []
    missing = [str(item)[:200] for item in ingredients if not _recipe_ingredients(str(item))]
    if not recipe.get("name"):
        missing.insert(0, "recipe name")
    if not recipe.get("recipeInstructions"):
        missing.append("instructions")
    return {
        "status": "NEEDS_REVIEW", "source_url": source_url,
        "name": str(recipe.get("name") or "")[:200],
        "ingredient_count": len(ingredients), "missing_fields": missing[:20],
    }


def recipe_create_payload(query: str) -> dict[str, Any] | None:
    draft = recipe_create_draft(query)
    return draft.as_payload() if draft else None


def recipe_requested_name(query: str) -> str | None:
    """Extract an explicit owner naming override for an import proposal."""
    return _recipe_name(str(query or ""))


def recipe_source_url(query: str) -> str | None:
    """Extract the bounded public source URL from a recipe request."""
    match = re.search(r"https?://[^\s)>]+", str(query or ""), re.IGNORECASE)
    return match.group(0).rstrip(".,") if match else None


def inventory_add_item_payload(query: str) -> dict[str, Any] | None:
    """Extract explicit item quantity for the canonical inventory CREATE."""
    text = str(query or "").strip()
    match = re.search(
        r"\badd\s+(?P<quantity>\d+(?:\.\d+)?)\s+(?P<name>.+?)"
        r"(?:\s+to\s+(?:the\s+)?(?P<area>pantry|refrigerator|fridge|freezer|cabinet|kitchen))?\s*\.?$",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    name = re.sub(
        r"\b(?:synthetic|cans?|bottles?|boxes?|items?)\b", " ",
        match.group("name"), flags=re.IGNORECASE,
    )
    name = re.sub(r"\s+", " ", name).strip(" .\"'")
    name = re.sub(r"^of\s+", "", name, flags=re.IGNORECASE).strip()
    if not name:
        return None
    return {
        "action": "add_item", "name": name[:200], "domain": "kitchen",
        "item_kind": "ingredient", "default_unit": "each",
        "initial_quantity": float(match.group("quantity")),
        "initial_unit": "each",
        "category": (match.group("area") or "").casefold() or None,
    }


def inventory_consume_stock_payload(query: str) -> dict[str, Any] | None:
    """Extract an explicit household consumption request for the owner Action.

    This is bounded argument extraction after the semantic household mutation
    contract has been selected. It does not resolve identity: the executor
    resolves ``item_name`` against the authenticated owner's canonical state.
    """
    text = str(query or "").strip()
    match = re.search(
        r"\b(?:use|consume|used|consumed)\s+"
        r"(?:(?P<quantity>\d+(?:\.\d+)?)|(?P<word>one|a|an|two|three|four|five))\s+"
        r"(?P<name>.+?)\s*\.?$", text, re.IGNORECASE,
    )
    if not match:
        return None
    word_quantities = {"one": 1.0, "a": 1.0, "an": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0}
    quantity = float(match.group("quantity")) if match.group("quantity") else word_quantities[match.group("word").casefold()]
    name = re.sub(
        r"\s+from\s+(?:the\s+)?(?:pantry|kitchen|freezer|refrigerator|fridge)\s*$", "",
        match.group("name"), flags=re.IGNORECASE,
    )
    name = re.sub(r"\s+", " ", name).strip(" .\"'")
    if not name or quantity <= 0:
        return None
    return {"action": "consume_stock", "item_name": name[:200], "quantity": quantity, "unit": "each"}


# Operational domain metadata used by prompt/capability projections.  These
# flags describe cognition requirements only; policy and execution remain
# owned by the canonical Action path.
DOMAIN_POLICIES = {
    "shell_exec": {"hard": True, "action_required": True},
    "operations": {"hard": True, "action_required": True},
    "network_ops": {"hard": True, "action_required": True},
    "storage_ops": {"hard": True, "action_required": True},
    "system_ops": {"hard": True, "action_required": True},
    "container_ops": {"hard": True, "action_required": True},
    "remote_ops": {"hard": True, "action_required": True},
    "security_audit": {"hard": True, "action_required": True},
    "pentest_ops": {"hard": True, "action_required": True},
    "osint": {"hard": False, "action_required": False},
    "asset_inventory": {"hard": False, "action_required": False},
    "homelab": {"hard": True, "action_required": True},
}
HARD_TOOL_DOMAINS = frozenset(
    name for name, policy in DOMAIN_POLICIES.items() if policy.get("hard")
)
DETERMINISTIC_TOOL_DOMAINS = HARD_TOOL_DOMAINS | frozenset({"osint", "asset_inventory"})
SPECIALIZED_OPERATIONAL_DOMAINS = frozenset({
    "network_ops", "storage_ops", "system_ops", "container_ops", "remote_ops",
    "security_audit", "pentest_ops",
})


_ADMIN_INTENT_KEYWORDS = (
    "session", "sessions", "chat", "chats", "conversation", "conversations",
    "delete", "fork", "truncate", "archive", "rename", "endpoint", "endpoints",
    "api key", "webhook", "webhooks", "token", "tokens", "mcp", "server", "skill",
    "skills", "task", "tasks", "schedule", "cron", "setting", "settings", "preference",
    "configure", "config", "setup", "manage", "admin", "pipeline", "second opinion",
    "list models", "switch model", "change model", "theme", "create theme", "document",
    "documents", "doc", "docs", "library", "tidy", "note", "notes", "todo", "todos",
    "reminder", "reminders",
)


def detect_admin_intent(messages: list[dict]) -> bool:
    """Return whether the latest user turn contains admin intent evidence."""
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
            )
        content_lower = str(content).lower()
        return any(keyword in content_lower for keyword in _ADMIN_INTENT_KEYWORDS)
    return False


def looks_like_explicit_skill_request(text: str) -> bool:
    """Return whether a turn explicitly asks to inspect/manage Skills."""
    query = str(text or "").strip().lower()
    if not query:
        return False
    words = set(re.findall(r"[a-z0-9_-]+", query))
    if not ({"skill", "skills"} & words):
        return False
    verbs = {
        "list", "show", "view", "open", "read", "search", "find", "inspect",
        "manage", "add", "create", "edit", "update", "patch", "publish",
        "delete", "remove",
    }
    return bool(words & verbs) or "my skill" in query or query.startswith(
        ("what skills do i", "which skills do i")
    )


def suppress_automatic_skills(
    text: str,
    intent: Mapping[str, object],
    *,
    explicit_memory_query,
) -> bool:
    """Suppress procedural Skill context for clearly non-procedural turns."""
    raw = str(text or "").strip()
    if bool(intent.get("explicit_memory_query")) or explicit_memory_query(raw):
        return True
    if not raw or bool(_LOW_SIGNAL_RE.match(raw)) or is_casual_low_signal(raw):
        return True
    query = raw.lower()
    if query.startswith(("write ", "draft ", "compose ", "create ")) and any(
        term in query for term in ("fictional", "fiction", "story", "poem", "novel", "screenplay")
    ):
        return True
    if query.startswith((
        "what is wrong ", "what is causing ", "what is failing ", "what is broken ",
        "why does my ", "why does this ", "why can my ", "why can this ",
        "explain why my ", "explain why this ",
    )):
        return False
    if query.startswith((
        "what is ", "what are ", "why do ", "why does ", "why can ",
        "explain why ", "summarize the concept ",
    )):
        return True
    if query.startswith("what does ") and " mean" in query:
        return True
    if query.startswith("explain what ") and " mean" in query:
        return True
    return query.startswith("explain how ") and (" work" in query or " works" in query)


_LOW_SIGNAL_RE = re.compile(r"^[\W_]*$", re.UNICODE)
_CASUAL_OPENING_RE = re.compile(
    r"^\s*(?:h+i+|hey+|hello+|yo+|sup+|what'?s up|wass?up|hiya|howdy|"
    r"lol|lmao|haha+|hehe+|thanks?|thank you|ty|idk|dunno|meh|bruh|bro)\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_CASUAL_BLOCKLIST_RE = re.compile(
    r"\b(?:cookbook|serve|serving|launch|start|vllm|sglang|llama\.?cpp|ollama|"
    r"download|model|email|document|doc|note|calendar|task|search|web|research|"
    r"file|folder|repo|git|settings?|endpoint|api|token|mcp)\b",
    re.IGNORECASE,
)


def is_casual_low_signal(text: str) -> bool:
    """Return whether a short greeting/slang turn lacks task signal.

    This is bounded intent evidence only. It prevents stale context from being
    hydrated for casual turns; it does not select, authorize, or execute an
    action.
    """
    s = str(text or "").strip()
    m = _CASUAL_OPENING_RE.match(s)
    if not m:
        return False
    tail = m.group("tail") or ""
    if _CASUAL_BLOCKLIST_RE.search(tail):
        return False
    tail_words = re.findall(r"[A-Za-z0-9_'-]+", tail)
    return len(tail_words) <= 2


# Semantic target evidence used by ACI/domain projection. This identifies a
# machine target without selecting a tool, scope, or executor.
_LOCAL_COMPUTER_REFERENCE_RE = re.compile(
    r"\b(?:on|from|in|using|with)\s+(?:this|my|the)\s+(?:computer|machine|pc|laptop|device|system)\b"
    r"|\b(?:local|host)\s+(?:computer|machine|files?|system)\b",
    re.IGNORECASE,
)
_NAMED_COMPUTER_REFERENCE_RE = re.compile(
    r"\b(?:on|from)\s+(?!this\b|my\b|the\b|a\b|an\b)(?:[a-z][a-z0-9_.-]{1,31})\b",
    re.IGNORECASE,
)
_COMPUTER_ACTION_CONTEXT_RE = re.compile(
    r"\b(?:run|execute|inspect|check|connect|ssh|scan|probe|ping|reach|"
    r"host|server|machine|computer|network|service|status|logs?)\b",
    re.IGNORECASE,
)


def looks_like_local_computer_request(text: str) -> bool:
    """Return whether text explicitly targets a local or named computer.

    This is intent evidence only; downstream ACI and policy still decide
    target identity, capability, scope, and execution authority.
    """
    text = str(text or "")
    if not text.strip():
        return False
    if _LOCAL_COMPUTER_REFERENCE_RE.search(text):
        return True
    return bool(
        _NAMED_COMPUTER_REFERENCE_RE.search(text)
        and _COMPUTER_ACTION_CONTEXT_RE.search(text)
    )


_WORKSPACE_CODE_ACTION_RE = re.compile(
    r"\b(?:fix|debug|implement|add|remove|change|update|refactor|wire|hook|"
    r"test|verify|run|build|lint|compile|commit|branch|merge|review|"
    r"download|save|rename|move|copy|extract|convert|open|inspect|read)\b",
    re.IGNORECASE,
)
_WORKSPACE_CODE_TARGET_RE = re.compile(
    r"\b(?:repo|project|codebase|app|frontend|backend|ui|css|js|javascript|"
    r"typescript|python|route|api|component|module|function|class|file|test|"
    r"bug|error|traceback|regression|failing|failure|branch|commit|folder|"
    r"directory|path|movie|video|subtitle|subtitles|srt|vtt|ass|ffmpeg)\b"
    r"|(?:~?/[^\"'\s`<>]+)",
    re.IGNORECASE,
)
_EXPLICIT_WORKSPACE_REFERENCE_RE = re.compile(
    r"\b(?:in|inside|within|from|this|current|active)\s+(?:the\s+)?workspace\b"
    r"|\b(?:this|current|active)\s+(?:workspace|repo|project)\b",
    re.IGNORECASE,
)


def looks_like_workspace_coding_request(text: str) -> bool:
    """Return whether text contains bounded workspace coding intent evidence."""
    text = str(text or "")
    if not text.strip():
        return False
    if re.search(r"\b(?:pull request|pr|diff|patch)\b", text, re.IGNORECASE):
        return True
    return bool(_WORKSPACE_CODE_ACTION_RE.search(text) and _WORKSPACE_CODE_TARGET_RE.search(text))


def explicitly_references_missing_workspace(text: str, workspace: str | None) -> bool:
    """Return whether a turn requires a workspace that has not been bound."""
    if workspace:
        return False
    text = str(text or "")
    if not text.strip():
        return False
    return bool(_EXPLICIT_WORKSPACE_REFERENCE_RE.search(text))


def looks_like_notes_request(text: str) -> bool:
    """Return whether a turn has notes, reminders, or checklist intent evidence."""
    query = str(text or "").lower()
    if re.search(r"\b(notes?|todos?|to-?do|checklists?|reminders?)\b", query):
        return True
    if re.search(
        r"\b(?:take|jot|write down|add|create|make)\b.{0,80}"
        r"\b(?:note|todo|to-?do|checklist|reminder)\b",
        query,
    ):
        return True
    return bool(
        re.search(r"\b(?:buy|pick ?up|pickup)\b", query)
        and not re.search(r"\b(?:calendar|event|meeting|appointment|schedule)\b", query)
    )


def looks_like_notes_calendar_followup(text: str) -> bool:
    """Return whether a turn refers to changing an existing note/calendar item."""
    query = str(text or "").lower()
    return bool(
        re.search(
            r"\b(?:now\s+)?(?:delete|remove|cancel|update|change|move|edit)\b"
            r".{0,80}\b(?:it|that|this|event|appointment|meeting|note|reminder|task)\b",
            query,
        )
        or re.search(r"\b(?:delete|remove|cancel)\s+(?:it|that|this)\b", query)
    )

def normalize_operational_intent_evidence(intent, query: str):
    # Fuse operational intent from action + object + scope evidence.
    # Existing classifier domains remain evidence, but do not erase adjacent
    # capabilities needed to perform the same task.
    if not isinstance(intent, dict):
        return intent

    import difflib

    q = str(query or "").lower()
    tokens = re.findall(r"[a-z0-9_.:/-]+", q)

    def phrase(*patterns):
        return any(re.search(p, q) for p in patterns)

    def fuzzy(words, cutoff=0.82):
        for tok in tokens:
            if len(tok) < 5:
                continue
            for word in words:
                if abs(len(tok) - len(word)) > 3:
                    continue
                if difflib.SequenceMatcher(None, tok, word).ratio() >= cutoff:
                    return True
        return False

    explanatory_only = phrase(
        r"\b(?:explain|define|what\s+is|what\s+are|teach\s+me|how\s+does)\b"
    ) and not phrase(
        r"\b(?:my|our|your|current|this)\b.{0,36}"
        r"\b(?:host|machine|system|network|lan|subnet|container|disk|service)\b"
    )

    action = phrase(
        r"\b(?:discover|discovery|inspect|check|scan|map|inventory|enumerate|"
        r"diagnose|troubleshoot|debug|audit|probe|test|verify|measure|monitor|"
        r"find|identify|determine|investigate|analyze|analyse|deep\s+dive|explore|"
        r"figure(?:\s+it)?\s+out|look\s+into|run|execute|install|collect|show|list)\b"
    ) or fuzzy({
        "discover", "discovery", "inspect", "scan", "inventory", "enumerate",
        "diagnose", "troubleshoot", "investigate", "analyze", "identify",
    })

    current_state_ask = phrase(
        r"\b(?:what(?:'s|\s+is)?|show\s+me|tell\s+me)\b.{0,40}"
        r"\b(?:my|our|your|current|this)\b"
    )

    domains = set(intent.get("domains") or set())
    before = set(domains)
    evidence = {}

    # ----- Network ---------------------------------------------------------
    net_core = phrase(
        r"\b(?:network|lan|vlan|subnet|cidr|gateway|router|switch|routing|route|"
        r"arp|neighbor|neighbour|dns|dhcp|mac\s+address|interface|open\s+ports?)\b"
    ) or fuzzy({"network", "subnet", "gateway", "routing", "discovery"})

    net_tool = phrase(
        r"\b(?:nmap|ping|traceroute|tracepath|arping|netstat|ss|iproute2|"
        r"tcpdump|dig|nslookup)\b"
    )

    net_entities = phrase(r"\b(?:hosts?|devices?|servers?)\b")

    local_scope = phrase(
        r"\b(?:local|internal|private|home|homelab)\s+(?:network|lan|subnet)\b",
        r"\b(?:our|my|your|current|this)\s+(?:network|lan|subnet)\b",
        r"\bdirectly\s+connected\b",
        r"\b(?:network|lan|subnet)\b.{0,32}\b(?:current(?:ly)?|right\s+now|now)\b",
        r"\bcontainer\s+(?:network|subnet|environment)\b",
        r"\bdocker\s+(?:network|bridge|subnet)\b",
        r"\b(?:lan|vlan|rfc1918)\b",
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?:/\d{1,2})?\b",
    )

    recon = phrase(
        r"\b(?:recon|reconnaissance|enumerat(?:e|ion|ing)|host\s+discovery|"
        r"port\s+scan|service\s+discovery)\b"
    ) or fuzzy({"reconnaissance", "enumeration", "discovery"})

    net_score = 0
    net_score += 4 if net_core else 0
    net_score += 4 if net_tool else 0
    net_score += 2 if net_entities else 0
    net_score += 3 if local_scope else 0
    net_score += 3 if recon else 0
    net_score += 2 if action or current_state_ask else 0
    net_score += 2 if "pentest_ops" in domains and (net_tool or recon or net_core) else 0
    net_score += 1 if "container_ops" in domains and (net_core or local_scope) else 0

    network_actionable = bool(action or current_state_ask)
    network_specific = bool(net_core or net_tool or recon)
    public_target_only = phrase(
        r"\b(?:https?://|www\.|[a-z0-9-]+\.(?:com|net|org|io|dev|gov|edu))\b"
    ) and not local_scope

    if (
        not explanatory_only
        and network_actionable
        and network_specific
        and net_score >= 6
        and not public_target_only
        and (local_scope or net_core or ("network_ops" in domains))
    ):
        domains.add("network_ops")
        evidence["network_ops"] = net_score

    # ----- Containers ------------------------------------------------------
    container_obj = phrase(
        r"\b(?:docker|podman|containers?|compose|containerd|kubernetes|k8s)\b"
    )
    if not explanatory_only and container_obj and (action or current_state_ask):
        domains.add("container_ops")
        evidence["container_ops"] = 6

    # ----- Storage ---------------------------------------------------------
    storage_obj = phrase(
        r"\b(?:storage|disks?|drives?|filesystem|mounts?|raid|lvm|zfs|btrfs|"
        r"smart|smartctl|nvme|lsblk|findmnt|inodes?)\b"
    )
    if not explanatory_only and storage_obj and (action or current_state_ask):
        domains.add("storage_ops")
        evidence["storage_ops"] = 6

    # ----- System / hardware ----------------------------------------------
    system_obj = phrase(
        r"\b(?:cpu|memory|ram|swap|load|process(?:es)?|kernel|boot|thermal|"
        r"temperature|hardware|uptime|lscpu|dmidecode|lspci|lsusb)\b"
    )
    if not explanatory_only and system_obj and (action or current_state_ask):
        domains.add("system_ops")
        evidence["system_ops"] = 6

    # ----- Remote ----------------------------------------------------------
    remote_obj = phrase(
        r"\b(?:over|via)\s+ssh\b",
        r"\bssh\s+(?:into|to)\b",
        r"\bremote\s+(?:host|server|machine|system)\b",
    )
    if not explanatory_only and remote_obj and (action or current_state_ask):
        domains.add("remote_ops")
        evidence["remote_ops"] = 6

    # ----- Service / daemon operations ------------------------------------
    ops_obj = phrase(r"\b(?:systemd|daemon|service|unit|journalctl|systemctl)\b")
    ops_problem = phrase(
        r"\b(?:failed|failing|broken|down|unhealthy|crash(?:ed|ing)?|stuck|"
        r"restart|recover|logs?|errors?)\b"
    )
    if not explanatory_only and ops_obj and (action or ops_problem):
        domains.add("operations")
        evidence["operations"] = 6

    # ----- Security / pentest ---------------------------------------------
    security_obj = phrase(
        r"\b(?:firewall|nftables|iptables|ssh\s+(?:config|policy)|"
        r"authentication|auth\s+logs?|listeners?|tls|certificates?|permissions?|"
        r"security\s+(?:posture|audit|hardening))\b"
    )
    if not explanatory_only and security_obj and action:
        domains.add("security_audit")
        evidence["security_audit"] = 6

    pentest_obj = phrase(
        r"\b(?:pentest|penetration\s+test|reconnaissance|port\s+scan|"
        r"vulnerability\s+scan|nmap)\b"
    )
    if not explanatory_only and pentest_obj and action:
        domains.add("pentest_ops")
        evidence["pentest_ops"] = 6

    # Pentest constrains behavior; it does not erase network capability.
    if (
        "pentest_ops" in domains
        and not public_target_only
        and local_scope
        and (net_core or net_tool or recon)
        and network_actionable
    ):
        domains.add("network_ops")
        evidence["network_ops"] = max(evidence.get("network_ops", 0), net_score)

    if domains != before:
        intent["domains"] = domains
        logger.info(
            "[agent-intent] operational intent fusion added=%s evidence=%s final=%s",
            sorted(domains - before),
            {k: evidence[k] for k in sorted(evidence) if k in (domains - before)},
            sorted(domains),
        )

    return intent



def normalize_asset_inventory_intent(intent: Any, query: str) -> Any:
    """Fuse explicit asset-inventory language into the semantic intent."""
    if not isinstance(intent, dict):
        return intent
    q = str(query or "").lower()
    action = bool(re.search(
        r"\b(?:add|record|inventory|catalog|track|update|move|remove|retire|"
        r"merge|find|show|list|search|scan|discover|collect|identify|"
        r"what(?:'s| is)|where is)\b", q,
    ))
    obj = bool(re.search(
        r"\b(?:asset|cmdb|hardware inventory|hardware|server inventory|parts?|"
        r"components?|motherboard|cpu|processor|ram|memory|dimm|gpu|nvme|"
        r"ssd|hdd|nic|serial|system uuid|spare|shelf|rack|chassis)\b", q,
    ))
    if action and obj:
        domains = set(intent.get("domains") or set())
        if "asset_inventory" not in domains:
            domains.add("asset_inventory")
            intent["domains"] = domains
            logger.info(
                "[intent] asset inventory normalization added asset_inventory final=%s",
                sorted(domains),
            )
    return intent


def asset_read_request(query: str) -> bool:
    """Recognize an explicit technical-asset read without selecting mutation."""
    q = str(query or "").lower()
    if re.search(r"\b(?:add|update|remove|delete|retire|merge|record|move|change)\b", q):
        return False
    return bool(
        re.search(
            r"\b(?:asset(?:s)?|cmdb|tech(?:nical)?|hardware|computational\s+assets?|"
            r"server(?:s)?|network devices?|unidentified devices?|know about)\b", q,
        )
        and re.search(
            r"\b(?:what|show|list|explain|know|have|inventory|recent(?:ly)? discovered|"
            r"where|tell\s+me\s+about)\b", q,
        )
    )


def normalize_homelab_intent(intent: Any, query: str) -> Any:
    """Fuse homelab/network operational language into the semantic intent."""
    if not isinstance(intent, dict):
        return intent
    q = str(query or "").lower()
    if (
        re.search(
            r"\b(?:homelab|home lab|local service|systemd user service|network discovery|"
            r"nmap discovery|scan my network|network scan)\b", q,
        )
        or (
            re.search(r"\b(?:scan|discover|map)\b", q)
            and explicit_private_discovery_cidr(q)
        )
        or re.search(
            r"\b(?:install|setup|set up|prepare|need)\b.{0,80}\b(?:tools?|utilities|"
            r"packages?)\b.{0,80}\b(?:network|nmap|scan|discovery)\b", q,
        )
    ):
        domains = set(intent.get("domains") or set())
        domains.update({"homelab", "network_ops"})
        intent["domains"] = domains
    return intent


OPERATION_CLASSES = frozenset({
    "READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "RESEARCH",
    "MONITOR", "CONTINUE", "APPROVE",
})
DEPTHS = frozenset({"QUICK", "STANDARD", "DEEP"})


# Compatibility-visible regex objects remain part of the contract so callers
# can characterize terse approval/continuation turns without importing the
# retired orchestration loop.  They classify language only; durable Run state
# and resolve_continuation remain authoritative for what may resume.
EXPLICIT_CONTINUATION_RE = re.compile(
    r"^\s*(?:"
    r"yes|y|yeah|yep|ok|okay|sure|do it|go ahead|go on|continue|carry on|"
    r"run it|launch it|start it|use that|that one|same|the same|"
    r"first|second|third|the first one|the second one|the third one|"
    r"[123]|[abc]"
    r")\s*(?:[.!?]+\s*)?$",
    re.IGNORECASE,
)
EXPLICIT_CONTINUATION_PHRASE_RE = re.compile(
    r"^\s*(?:"
    r"(?:yes|yeah|yep|ok|okay|sure)\s*(?:,\s*)?(?:please\s+)?"
    r"(?:continue|carry\s+on|proceed|resume|go\s+ahead(?:\s+and\s+continue)?|"
    r"(?:run|scan|start)\s+(?:it|the\s+scan|the\s+task|this|[^.!?]{0,32}\bscan\b))|"
    r"(?:please\s+)?(?:continue(?:\s+(?:with\s+that|the\s+task|until\s+[^.!?]{0,160}))?(?:\s+please)?|"
    r"carry\s+on|proceed|resume|keep\s+going|go\s+on|go\s+ahead(?:\s+and\s+continue)?|"
    r"do\s+that|do\s+all\s+of\s+(?:the\s+)?(?:above|those|them)|"
    r"all\s+of\s+(?:the\s+)?(?:above|those|them))"
    r")\s*(?:[.!?]+\s*)?$",
    re.IGNORECASE,
)


def is_explicit_continuation(text: str) -> bool:
    """Classify a terse request to resume the preceding Objective/Run.

    This does not select an Action.  The active durable Run is checked later
    by :func:`resolve_continuation`, which can block terminal, ambiguous, or
    unavailable work.
    """
    value = str(text or "").strip()
    return bool(
        EXPLICIT_CONTINUATION_RE.match(value)
        or EXPLICIT_CONTINUATION_PHRASE_RE.match(value)
    )


def explicit_private_discovery_cidr(text: str) -> str | None:
    """Extract an explicitly supplied, bounded private IPv4 discovery scope.

    This is a semantic scope projection, not authorization.  It deliberately
    ignores current interfaces, historical observations, and RFC1918 guesses;
    the broker and normal ActionSpec policy remain authoritative for execution.
    """
    for candidate in re.findall(
        r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}(?!\w)",
        str(text or ""),
    ):
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            continue
        if network.version == 4 and network.is_private and network.num_addresses <= 256:
            return str(network)
    return None


def network_discovery_request_cidr(text: str) -> str | None:
    """Return only a scope present in the current request.

    A missing CIDR is unresolved.  Current host/VPN context and historical
    observations are evidence, never implicit scan authorization.
    """
    return explicit_private_discovery_cidr(text)


def is_network_prerequisite_request(text: str) -> bool:
    """Recognize a request to prepare tools for bounded network work."""
    return bool(re.search(
        r"\b(?:install|setup|set up|prepare|need)\b.{0,100}"
        r"\b(?:tools?|utilities|packages?)\b.{0,100}"
        r"\b(?:network|nmap|scan|discovery)\b",
        str(text or "").lower(),
    ))


def is_explicit_network_discovery_request(text: str) -> bool:
    """Recognize actionable network discovery language without authorizing it."""
    query = str(text or "").lower()
    if re.search(r"^\s*(?:what\s+is|what\s+are|define|explain|how\s+does)\b", query):
        return False
    return bool(
        re.search(r"\b(?:scan|discover|map|enumerate|identify|find)\b", query)
        and re.search(r"\b(?:network|lan|subnet|devices?|hosts?|192(?:\.168)?|rfc1918)\b", query)
    )


def is_network_service_enumeration_request(text: str) -> bool:
    """Recognize service-enumeration intent, not generic shell scanning."""
    query = str(text or "").lower()
    return bool(
        re.search(r"\b(?:service(?:s)?|port(?:s)?|version|enumeration|deeper|deep(?:er)? scan)\b", query)
        and re.search(r"\b(?:network|host(?:s)?|device(?:s)?|scan|discovery|nmap)\b", query)
    )


def explicitly_allows_diagnostic_install(query: str) -> bool:
    """Project affirmative installation intent without granting authority.

    This is semantic evidence for a bounded remediation plan.  Approval,
    package allowlists, and the privileged broker remain authoritative for
    whether anything may actually be installed.
    """
    q = str(query or "").lower().strip()
    if re.search(
        r"(?:"
        r"\b(?:do\s+not|don't|dont|never)\b.{0,36}\b(?:install|add)\b|"
        r"\bwithout\s+(?:installing|adding)\b|"
        r"\bno\s+(?:package\s+)?installs?\b|"
        r"\b(?:avoid|skip)\b.{0,28}\b(?:installing|installation|packages?)\b"
        r")",
        q,
    ):
        return False
    if re.search(
        r"(?:"
        r"\b(?:you\s+can|you\s+may|you(?:'re|\s+are)\s+(?:allowed|authorized)|"
        r"feel\s+free\s+to|go\s+ahead\s+and)\b.{0,32}\b(?:install|add)\b|"
        r"\bpermission\s+(?:is\s+)?granted\b.{0,32}\b(?:install|add)\b"
        r")",
        q,
    ):
        return True
    if re.search(
        r"(?:"
        r"(?:^|[.!?;:]\s+|\bthen\s+|\band\s+then\s+)"
        r"(?:please\s+)?(?:install|add)\b"
        r")",
        q,
    ):
        return True
    return bool(re.search(
        r"(?:"
        r"(?:^|[.!?;:]\s+|\bthen\s+|\band\s+then\s+)"
        r"if\b.{0,36}\b(?:missing|needed|required|necessary|unavailable)\b"
        r".{0,52}\b(?:install|add)\b|"
        r"(?:^|[.!?;:]\s+|\bthen\s+|\band\s+then\s+)"
        r"(?:please\s+)?(?:install|add)\b.{0,52}\bif\b.{0,40}"
        r"\b(?:missing|needed|required|necessary|unavailable)\b"
        r")",
        q,
    ))


def network_substantive_fallback_command(intent_domains, query: str) -> str:
    """Return the legacy compatibility fallback for network remediation.

    The command is only a projection used by the retired text-tool adapter;
    it is not an executor or an authorization decision. Canonical ACI actions
    remain preferred and the normal policy/broker path still gates execution.
    """
    if "network_ops" not in set(intent_domains or set()):
        return ""
    install_flag = "--install-authorized" if explicitly_allows_diagnostic_install(query) else ""
    return ("python -m src.asset_inventory network-discover " + install_flag + " --record-observations").strip()


def _is_continuation_phrase(text: str) -> bool:
    """Recognize operator continuation language without binding to a domain.

    A continuation may include a bounded natural-language qualification (for
    example, ``continue until the report is complete``).  The active Run and
    its pending Action remain authoritative; this helper only classifies the
    user turn and never selects or executes an Action.
    """
    return bool(re.match(
        r"^\s*(?:please\s+)?(?:continue|resume|proceed|go\s+on|go\s+ahead|do\s+it|"
        r"finish\s+it|keep\s+going|do\s+that|do\s+all\s+of\s+(?:the\s+)?"
        r"(?:above|those|them)|all\s+of\s+(?:the\s+)?(?:above|those|them))\b",
        str(text or ""),
        re.IGNORECASE,
    ))


@dataclass(frozen=True)
class IntentFrame:
    operation_class: str
    domain_concept: str
    workspace_hint: str | None = None
    target: str | None = None
    entity_reference: str | None = None
    run_reference: str | None = None
    continuation_reference: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)
    scope: Mapping[str, Any] = field(default_factory=dict)
    depth: str = "STANDARD"
    constraints: tuple[str, ...] = ()
    desired_output: str | None = None
    reference_resolution: Mapping[str, Any] = field(default_factory=dict)
    read_explicit: bool = False
    source: str = "deterministic_compiler"

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["filters"] = dict(self.filters)
        result["scope"] = dict(self.scope)
        return result


_BOUNDED_OWNER_CAPABILITY_CONCEPTS = frozenset({
    "TECHNICAL_ASSET", "HOMELAB_HOST", "NETWORK", "HOUSEHOLD_ITEM", "RECIPE",
    "MEMORY", "WORK",
})


def is_bounded_owner_capability_turn(frame: IntentFrame | None) -> bool:
    """Tell transport adapters when plain chat must enter canonical ACI.

    This is semantic eligibility only. It does not select an Action, grant
    authority, or bypass policy; the resolved contract and normal ACI path do
    those things downstream. Keeping the predicate beside ``IntentFrame``
    prevents each UI/transport from growing its own routing heuristic.
    """
    if frame is None or frame.domain_concept not in _BOUNDED_OWNER_CAPABILITY_CONCEPTS:
        return False
    return bool(
        frame.read_explicit
        or frame.operation_class in {"CREATE", "UPDATE", "EXECUTE", "RESEARCH"}
    )


@dataclass(frozen=True)
class DomainContract:
    concept: str
    capability_id: str
    actions: Mapping[str, str]
    binding: str | None
    exposures: Mapping[str, str]
    result_contract: str


@dataclass(frozen=True)
class ResolvedContract:
    frame: IntentFrame
    contract: DomainContract | None
    action_id: str | None
    action: ActionSpec | None
    binding_name: str | None
    available: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_frame": self.frame.as_dict(),
            "domain_concept": self.frame.domain_concept,
            "capability_id": self.contract.capability_id if self.contract else None,
            "action_id": self.action_id,
            "binding": self.binding_name,
            "available": self.available,
            "reason": self.reason,
            "result_contract": self.contract.result_contract if self.contract else None,
            "exposure": dict(self.contract.exposures) if self.contract else {},
        }


@dataclass(frozen=True)
class ContinuationResolution:
    """Pure resolution result; it never executes or grants authority."""

    status: str
    run_reference: str | None = None
    action_reference: str | None = None
    phase: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_reference": self.run_reference,
            "action_reference": self.action_reference,
            "phase": self.phase,
            "reason": self.reason,
        }


# Mappings deliberately reference existing capability IDs/action IDs. A
# missing binding is reported by validate_contracts rather than being silently
# replaced with a shell or database path.
DOMAIN_CONTRACTS: Mapping[str, DomainContract] = {
    "TECHNICAL_ASSET": DomainContract(
        "TECHNICAL_ASSET", "inventory.manage",
        {"READ": "list", "READ_DETAIL": "get", "CREATE": "add", "UPDATE": "update"},
        "manage_assets",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "technical_asset_list",
    ),
    "SECURITY_FINDING": DomainContract(
        "SECURITY_FINDING", "security.assessment.read", {"READ": "list_findings"}, "manage_security_assessment",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "security_finding_list",
    ),
    "SECURITY_ENGAGEMENT": DomainContract(
        "SECURITY_ENGAGEMENT", "security.assessment.read", {"READ": "list_engagements"}, "manage_security_assessment",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "security_engagement_list",
    ),
    "SECURITY_EVIDENCE": DomainContract(
        "SECURITY_EVIDENCE", "security.assessment.read", {"READ": "list_evidence"}, "manage_security_assessment",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "security_evidence_list",
    ),
    "NETWORK": DomainContract(
        "NETWORK", "homelab.manage", {"READ": "read_network_observations", "READ_CONTEXT": "read_network_context", "READ_UNIDENTIFIED": "list_unidentified_hosts", "READ_ROLES": "infer_role_hypotheses", "EXECUTE": "plan_network_discovery"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "network_capability_or_discovery",
    ),
    "HOMELAB_HOST": DomainContract(
        "HOMELAB_HOST", "homelab.manage", {"READ": "inspect_host", "REMOTE_READ": "remote_host_inspect"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "homelab_host_observation",
    ),
    "SERVICE": DomainContract(
        "SERVICE", "homelab.manage", {"READ": "service_status", "EXECUTE": "plan_service_restart"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "service_status_observation",
    ),
    "OSINT_CASE": DomainContract(
        "OSINT_CASE", "research.public_sources", {"READ": "list_cases", "RESEARCH": "plan"}, "manage_osint",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "osint_case_or_plan",
    ),
    "RESEARCH": DomainContract(
        "RESEARCH", "research.public_sources", {"READ": "list_cases"}, "manage_osint",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "research_case_or_history_list",
    ),
    "WEB_EVIDENCE": DomainContract(
        "WEB_EVIDENCE", "web.evidence", {"READ": "search"}, "web_search",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "public_web_evidence",
    ),
    "WEB_URL": DomainContract(
        "WEB_URL", "web.evidence", {"READ": "fetch"}, "web_fetch",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "public_web_document",
    ),
    "MEMORY": DomainContract(
        "MEMORY", "memory.read", {"READ": "summarize_owner_memory"}, "read_memory",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "explicit_memory_read",
    ),
    "WORK": DomainContract(
        "WORK", "work.read", {"READ": "overview", "READ_ATTENTION": "attention"}, "read_work",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "work_overview",
    ),
    "GOAL": DomainContract("GOAL", "work.read", {"READ": "list_goals"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_goals"),
    "PROJECT": DomainContract("PROJECT", "work.read", {"READ": "list_projects"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_projects"),
    "TASK": DomainContract("TASK", "work.read", {"READ": "list_tasks"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_tasks"),
    "RUN": DomainContract("RUN", "work.read", {"READ": "list_runs"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_runs"),
    "COMMITMENT": DomainContract("COMMITMENT", "work.read", {"READ": "list_commitments"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_commitments"),
    "MISSION": DomainContract("MISSION", "work.read", {"READ": "list_missions"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_missions"),
    "WATCH": DomainContract("WATCH", "work.read", {"READ": "list_watches"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_watches"),
    "HOUSEHOLD_ITEM": DomainContract(
        "HOUSEHOLD_ITEM", "household.read", {"READ": "overview"}, "read_household",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "household_overview",
    ),
    "RECIPE": DomainContract(
        "RECIPE", "recipe.read",
        {"READ": "list", "READ_SEARCH": "search", "READ_DETAIL": "get", "READ_COVERAGE": "can_make", "READ_SCALE": "scale", "READ_EXPIRING": "expiring_candidates", "READ_IMPORT_PREPARE": "prepare_import"},
        "read_recipes",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "recipe_read",
    ),
    "RECIPE_MUTATION": DomainContract(
        "RECIPE_MUTATION", "recipe.manage", {"CREATE": "add", "CREATE_IMPORT_COMMIT": "commit_import"}, "manage_recipes",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "recipe_mutation",
    ),
    # Mutations use the same Inventory service as the human-facing inventory
    # adapter.  Keeping this as a separate contract avoids changing the
    # established read-only Household binding while making CREATE/UPDATE
    # explicit canonical Actions instead of model-selected prose.
    "INVENTORY_MUTATION": DomainContract(
        "INVENTORY_MUTATION", "inventory.manage",
        {"CREATE": "add_item", "UPDATE": "add_stock", "EXECUTE": "consume_stock"},
        "manage_assets",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "inventory_mutation",
    ),
    "INTEGRATION": DomainContract(
        "INTEGRATION", "setup.read", {"READ": "state", "READ_INTEGRATIONS": "integrations"}, "read_setup",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "setup_state_or_integrations",
    ),
    "COMMUNICATIONS": DomainContract(
        "COMMUNICATIONS", "communications.read", {"READ": "overview"}, "read_communications",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "communications_overview",
    ),
    "CONTACT": DomainContract(
        "CONTACT", "communications.read", {"READ": "contacts"}, "read_communications",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "contact_list_or_unavailable",
    ),
    "CAREER_PROFILE": DomainContract(
        "CAREER_PROFILE", "career.read", {"READ": "overview"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_overview",
    ),
    "JOB_SEARCH": DomainContract(
        "JOB_SEARCH", "career.read", {"READ": "overview", "RESEARCH": "provider_status"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_search_or_provider",
    ),
    "JOB_OPPORTUNITY": DomainContract(
        "JOB_OPPORTUNITY", "career.read", {"READ": "saved_opportunities", "RESEARCH": "provider_status"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_opportunities",
    ),
    "APPLICATION": DomainContract(
        "APPLICATION", "career.read", {"READ": "applications"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_applications",
    ),
    "INTERVIEW": DomainContract(
        "INTERVIEW", "career.read", {"READ": "interviews"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_interviews",
    ),
    "DEVELOPER": DomainContract(
        "DEVELOPER", "developer.read",
        {"READ": "search_code", "READ_FILE": "view_file_region", "READ_MAP": "show_repo_map"},
        "developer_read",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "developer_workspace_read",
    ),
}

# Canonical concept-to-projection mapping.  The projection names are legacy
# transport/tool-set labels, not a second semantic router.  ACI owns the
# concept; callers may use these bounded names only to assemble an adapter
# request for the existing capability registry.
CANONICAL_DOMAIN_PROJECTIONS: Mapping[str, str] = {
    "TECHNICAL_ASSET": "asset_inventory",
    "SECURITY_FINDING": "security_audit",
    "SECURITY_ENGAGEMENT": "security_audit",
    "SECURITY_EVIDENCE": "security_audit",
    "NETWORK": "network_ops",
    "HOMELAB_HOST": "homelab",
    "SERVICE": "homelab",
    "OSINT_CASE": "osint",
    "RESEARCH": "osint",
    "WEB_EVIDENCE": "web",
    "WEB_URL": "web",
    "MEMORY": "memory",
    "WORK": "work",
    "GOAL": "work",
    "PROJECT": "work",
    "TASK": "work",
    "RUN": "work",
    "COMMITMENT": "work",
    "MISSION": "work",
    "WATCH": "work",
    "HOUSEHOLD_ITEM": "household",
    "RECIPE": "recipes",
    "INTEGRATION": "setup",
    "COMMUNICATIONS": "communications",
    "CONTACT": "contacts",
    "CAREER_PROFILE": "career",
    "JOB_SEARCH": "career",
    "JOB_OPPORTUNITY": "career",
    "APPLICATION": "career",
    "INTERVIEW": "career",
    "DEVELOPER": "developer",
}


def canonical_domain_projection(frame: IntentFrame) -> frozenset[str]:
    """Return the bounded transport projection for an ACI-owned concept."""
    projection = CANONICAL_DOMAIN_PROJECTIONS.get(str(frame.domain_concept or ""))
    return frozenset((projection,)) if projection else frozenset()


def canonical_read_action(
    domain_concept: str,
    filters: Mapping[str, Any] | None = None,
    *,
    entity_reference: str | None = None,
) -> str | None:
    """Resolve a read operation through the canonical DomainContract table."""
    contract = DOMAIN_CONTRACTS.get(str(domain_concept or "").strip())
    if contract is None:
        return None
    view = dict(filters or {}).get("view")
    operation = "READ"
    if domain_concept in {"TECHNICAL_ASSET", "RECIPE"} and str(entity_reference or "").strip():
        operation = "READ_DETAIL"
    elif domain_concept == "WORK" and view == "attention":
        operation = "READ_ATTENTION"
    elif domain_concept == "INTEGRATION" and view == "integrations":
        operation = "READ_INTEGRATIONS"
    elif domain_concept == "NETWORK" and view == "unidentified":
        operation = "READ_UNIDENTIFIED"
    elif domain_concept == "NETWORK" and view == "context":
        operation = "READ_CONTEXT"
    elif domain_concept == "NETWORK" and view == "roles":
        operation = "READ_ROLES"
    elif domain_concept == "RECIPE" and str(dict(filters or {}).get("recipe_query") or "").strip():
        operation = "READ_SEARCH"
    elif domain_concept == "RECIPE" and dict(filters or {}).get("recipe_expiring") is True:
        operation = "READ_EXPIRING"
    elif domain_concept == "RECIPE" and dict(filters or {}).get("recipe_coverage") is True:
        operation = "READ_COVERAGE"
    elif domain_concept == "RECIPE" and dict(filters or {}).get("recipe_scale") is True:
        operation = "READ_SCALE"
    return contract.actions.get(operation)


def _depth(text: str) -> str:
    q = text.lower()
    if re.search(r"\b(?:deep(?:er)?|deep dive|thorough|detailed)\b", q):
        return "DEEP"
    if re.search(r"\b(?:quick|brief|short)\b", q):
        return "QUICK"
    return "STANDARD"


def resolve_structured_reference(
    text: str,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve conversational references against server-owned opaque refs.

    This is intentionally a pure projection.  It never looks up a guessed ID,
    broadens scope, or authorizes an Action.  Callers may persist the compact
    context and pass it back after a model/provider swap.  Singular references
    fail closed when more than one candidate exists; plural language returns
    the exact bounded set supplied by the caller.
    """
    query = str(text or "").strip().lower()
    supplied = context if isinstance(context, Mapping) else {}
    # Canonical result projections may provide an explicitly ordered eligible
    # set.  Prefer it over a broad conversational entity bag: ordinal
    # references are positions in the result the user just saw, not positions
    # in whichever mixed-domain references happened to be retained in chat.
    raw_candidates = (
        supplied.get("ordered_entities")
        or supplied.get("eligible_entities")
        or supplied.get("entities")
        or supplied.get("references")
        or []
    )
    candidates = [
        item for item in raw_candidates
        if isinstance(item, Mapping)
        and str(item.get("ref") or item.get("id") or "").strip()
        and item.get("eligible", True) is not False
    ]
    last = supplied.get("last") if isinstance(supplied.get("last"), Mapping) else None
    if not candidates and last is not None and not any(
        str(item.get("ref") or item.get("id") or "") == str(last.get("ref") or last.get("id") or "")
        for item in candidates
    ):
        if str(last.get("ref") or last.get("id") or "").strip() and last.get("eligible", True) is not False:
            candidates.append(last)

    plural = bool(re.search(
        r"\b(?:those|them|these|all(?:\s+of)?\s+(?:the\s+)?(?:above|those|them)|"
        r"all\s+of\s+them|everything)\b", query,
    ))
    # Allow natural qualifiers ("first physical one", "second server").
    # The ordinal remains bounded by the supplied ordered entity set.
    ordinal_match = re.search(
        r"\b(?:the\s+)?(first|second|third)"
        r"(?:\s+[a-z0-9_-]+){0,2}\s+"
        r"(?:one|machine|computer|server|host|box|device)\b",
        query,
    )
    # Detail follow-ups can omit the noun entirely ("tell me the specs") or
    # use a possessive pronoun ("what about its RAM"). They are references
    # only when prior canonical context can provide the identity.
    implicit_detail = bool(re.search(
        # ``memory`` by itself names the canonical Memory domain. Treat it as
        # an Asset property only when the surrounding possessive/reference
        # language makes that relationship explicit; otherwise ordinary
        # questions such as "what do you know about me?" must not become
        # unresolved Asset references.
        r"\b(?:specs?|specifications?|cpus?|processors?|ram|gpus?|"
        r"graphics\s+cards?|storage|motherboard|os|operating\s+system)\b",
        query,
    )) and bool(re.search(r"\b(?:tell|show|what|which|give|list|describe)\b", query))
    other = bool(re.search(r"\b(?:the\s+)?other\s+one\b", query))
    # ``it assets`` is the common lower-case/voice-transcription spelling of
    # ``IT assets``. It is an owner-scope noun phrase, not a pronoun referring
    # to the last Asset, so an active referent must not narrow the collection
    # read to one record.
    it_assets = bool(re.search(r"\bit\s+assets?\b", query))
    pronoun = bool(re.search(r"\b(?:it|its|that|this|that\s+one|their)\b", query)) and not it_assets
    singular = pronoun or bool(ordinal_match) or other or implicit_detail
    if not plural and not singular:
        return {"status": "NOT_REFERENCE", "refs": [], "reason": "no structured reference phrase"}
    if not candidates:
        return {"status": "UNRESOLVED", "refs": [], "reason": "no durable reference context"}
    if ordinal_match:
        index = {"first": 0, "second": 1, "third": 2}[ordinal_match.group(1)]
        if index >= len(candidates):
            return {"status": "UNRESOLVED", "refs": [], "reason": "ordinal reference is out of range"}
        selected = [candidates[index]]
    elif other:
        last_ref = str(last.get("ref") or last.get("id") or "") if last else ""
        alternatives = [
            item for item in candidates
            if str(item.get("ref") or item.get("id") or "") != last_ref
        ]
        if len(alternatives) != 1:
            return {
                "status": "AMBIGUOUS", "refs": [],
                "candidate_refs": [
                    str(item.get("ref") or item.get("id"))
                    for item in alternatives or candidates
                ],
                "reason": "other reference does not identify exactly one candidate",
            }
        selected = alternatives
    elif plural:
        selected = candidates
    elif (pronoun or implicit_detail) and last:
        last_ref = str(last.get("ref") or last.get("id") or "")
        selected = [
            item for item in candidates
            if str(item.get("ref") or item.get("id") or "") == last_ref
        ] or [last]
    elif len(candidates) == 1:
        selected = candidates
    else:
        return {
            "status": "AMBIGUOUS", "refs": [],
            "candidate_refs": [str(item.get("ref") or item.get("id")) for item in candidates],
            "reason": "singular reference has multiple candidates",
        }
    refs = [str(item.get("ref") or item.get("id")) for item in selected]
    concepts = sorted({str(item.get("concept") or "").strip() for item in selected if item.get("concept")})
    return {
        "status": "RESOLVED",
        "refs": refs,
        "concept": concepts[0] if len(concepts) == 1 else None,
        "concepts": concepts,
        "selection": "ALL" if plural else "ONE",
    }


def _operation(text: str, *, continuation: bool = False) -> str:
    q = text.lower().strip()
    if continuation or _is_continuation_phrase(q):
        return "CONTINUE"
    if re.search(r"\b(?:delete|remove|retire|forget)\b", q): return "DELETE"
    if re.search(r"\b(?:update|change|edit|rename|reconcile|confirm)\b", q): return "UPDATE"
    if re.search(r"\b(?:create|add|new)\b", q): return "CREATE"
    if re.search(r"\b(?:restart|recover|execute|run|scan|discover\w*|install|turn on|start|begin)\b", q) and not re.search(
        r"\brun\s+out\s+of\b", q,
    ): return "EXECUTE"
    if re.search(r"\b(?:research|investigate|deep dive|look into)\b", q): return "RESEARCH"
    if re.search(r"\b(?:monitor|watch|alert)\b", q): return "MONITOR"
    return "READ"


def compile_intent(
    query: str,
    *,
    continuation: bool = False,
    run_reference: str | None = None,
    reference_context: Mapping[str, Any] | None = None,
) -> IntentFrame:
    """Compile common current product concepts into a bounded IntentFrame."""
    text = str(query or "").strip()
    q = text.lower()
    reference_resolution = dict(resolve_structured_reference(text, reference_context))
    # Keep the low-level resolver's stable public shape while exposing an
    # explicit attempt bit in the IntentFrame projection for evaluator metrics.
    reference_resolution["attempted"] = reference_resolution.get("status") != "NOT_REFERENCE"
    operation = _operation(text, continuation=continuation)
    semantic_read_concept = (
        deterministic_read_concept(text) if operation == "READ" else None
    )
    # READ is the safe fallback operation for semantically incomplete text,
    # but canonical read projection must not treat every imperative containing
    # a domain noun as a request to inspect state. Keep this as bounded intent
    # metadata rather than a tool-name/route heuristic.
    read_explicit = bool(semantic_read_concept) or bool(re.match(
        r"\s*(?:what(?:'s| is| are)?|which|who|where|when|how many|how much|show|list|"
        r"tell me|do you have|are there|is there|find my|what do you)\b",
        q,
    ))
    # Interrogative requests about the research store are canonical reads;
    # the noun "research" must not turn "What research history do I have?"
    # into a new research execution request.
    # A question prefix does not demote an explicit discovery objective to a
    # harmless observation.  Discovery is still staged and scope-authorized
    # by the Network ActionSpec; this only preserves its intent class.
    _network_discovery_language = bool(
        re.search(r"\b(?:network|lan|subnet|wifi|wi-fi|connection|connected|hosts?|devices?)\b", q)
        and re.search(
            r"\b(?:scan\w*|discover\w*|enumerat\w*|probe\w*|map\w*|explore)\b|"
            r"\bdeep\s+dive\b.*\b(?:discovery|dive|mission)\b|"
            r"\bdiscovery\s+(?:dive|mission)\b",
            q,
            re.IGNORECASE,
        )
    )
    if read_explicit and operation in {"RESEARCH", "MONITOR", "EXECUTE"} and not _network_discovery_language:
        operation = "READ"
    concept = semantic_read_concept or "UNKNOWN"
    target = None
    if concept != "UNKNOWN":
        pass
    elif not re.search(r"\b(?:explain|define|what\s+is|difference\s+between|how\s+does)\b", q) and re.search(
        r"\b(?:search|grep|find|look\s+for|inspect|view|show|list|read|open)\b.*\b(?:code|repo|repository|project|file|symbol|function|class|diagnostic|tree|map|diff|changes?)\b|"
        r"\b(?:code|repo|repository|project|file|symbol|function|class|diagnostic|tree|map|diff|changes?)\b.*\b(?:search|grep|find|inspect|view|show|list|read|open)\b|"
        r"\b(?:read|open|view|inspect)\b\s+[^\s]+\.(?:py|js|ts|tsx|jsx|go|rs|java|rb|md|yaml|yml|json|toml|ini|cfg)\b",
        q,
    ):
        concept = "DEVELOPER"
    elif re.search(r"\b(?:security\s+engagement|engagements?)\b", q):
        concept = "SECURITY_ENGAGEMENT"
    elif re.search(r"\b(?:security\s+evidence|evidence\s+for\s+security|security\s+artifacts?)\b", q):
        concept = "SECURITY_EVIDENCE"
    elif re.search(r"\b(?:service(?:s)?|daemon(?:s)?)\b", q) and re.search(r"\b(?:status|running|active|homelab|server|restart|recover|logs?|errors?)\b", q):
        concept = "SERVICE"
    elif re.search(r"\b(?:homelab|container(?:s)?|storage|remote host(?:s)?)\b", q) and not re.search(
        r"\b(?:difference\s+between|what(?:'s|\s+is)\s+the\s+difference|explain)\b", q,
    ):
        concept = "HOMELAB_HOST"
    elif re.search(r"\b(?:mission(?:s)?)\b", q):
        concept = "MISSION"
    elif re.search(r"\b(?:watch(?:es)?|monitors?)\b", q):
        concept = "WATCH"
    elif re.search(r"\b(?:goal(?:s)?)\b", q):
        concept = "GOAL"
    elif re.search(r"\b(?:project(?:s)?)\b", q):
        concept = "PROJECT"
    elif re.search(r"\b(?:task(?:s)?)\b", q):
        concept = "TASK"
    elif re.search(r"\b(?:commitment(?:s)?)\b", q):
        concept = "COMMITMENT"
    elif re.search(r"\b(?:run(?:s)?)\b", q) and re.search(r"\b(?:active|current|durable|waiting|pending|run)\b", q):
        concept = "RUN"
    elif re.search(r"\b(?:research|research history)\b", q) and not re.search(r"\b(?:osint|investigation|case|cases)\b", q):
        concept = "RESEARCH"
    elif re.search(r"\b(?:devices?|hosts?)\b", q) and re.search(
        r"\b(?:look like|probably|role|roles|unidentified|unknown|on my network)\b", q,
    ):
        concept = "NETWORK"
    elif not re.search(r"\b(?:difference\s+between|versus|explain)\b", q) and (
        re.search(r"\b(?:asset(?:s)?|cmdb|hardware|server(?:s)?|technical equipment|machines?)\b", q) or (
        re.search(r"\binventory\b", q)
        and re.search(r"\b(?:state|status|registered|recorded|current|known|show|list)\b", q)
        and not re.search(r"\b(?:pantry|shopping|groceries|recipe|household|stock)\b", q)
        ) or (
        re.search(
            r"\b(?:gpu|gpus|graphics\s+cards?|vram|ram|memory|cpu|cpus|"
            r"processors?|motherboard|storage|specs?|specifications?)\b",
            q,
        )
        and re.search(
            r"\b(?:my|mine|our|ours|we|i\s+(?:have|own|got)|"
            r"do\s+i\s+have|how\s+many|which\s+(?:machines?|hosts?|servers?|boxes?)|"
            r"what\s+(?:machines?|hosts?|servers?|boxes?)|show|list|find|search)\b",
            q,
        )
        ) or (
        re.search(r"\bhow\s+many\s+(?:\d{3,5}|(?:rtx|gtx|quadro|tesla|radeon|arc)\b)", q)
        and re.search(r"\bdo\s+i\s+have\b", q)
        )
    ):
        concept = "TECHNICAL_ASSET"
    elif re.search(r"\b(?:memory|remember|brain)\b", q):
        concept = "MEMORY"
    elif re.search(r"\b(?:network|lan|subnet|hosts?|devices?)\b", q):
        concept = "NETWORK"
    elif re.search(r"\b(?:finding|findings|security engagement|security assessment)\b", q):
        concept = "SECURITY_FINDING"
    elif re.search(r"\b(?:osint|open source intelligence|investigations?|cases?)\b", q):
        concept = "OSINT_CASE"
    elif re.search(r"\b(?:household|pantry|stock|shopping|groceries|kitchen)\b", q):
        concept = "HOUSEHOLD_ITEM"
    elif re.search(r"\b(?:what(?:'s| is)\s+hades\s+waiting\s+on|what\s+needs\s+attention|waiting\s+on|pending\s+approvals?)\b", q):
        concept = "WORK"
    elif re.search(r"\b(?:work|working|project|task|goal|commitment)\b", q) and not re.search(
        r"\bcapabilit(?:y|ies)\b", q,
    ):
        concept = "WORK"
    elif re.search(r"\b(?:communications?|email accounts?|calendars?|calendar events?)\b", q):
        concept = "COMMUNICATIONS"
    elif re.search(r"\b(?:contacts?|address\s*book)\b", q):
        concept = "CONTACT"
    elif re.search(r"\b(?:setup|configured|integrations?|connected)\b", q):
        concept = "INTEGRATION"
    elif re.search(r"\b(?:career|job search|jobs?|opportunit(?:y|ies)|applications?|interviews?|resume|roles?)\b", q):
        if re.search(r"\b(?:application|applied|follow[- ]?up)", q): concept = "APPLICATION"
        elif re.search(r"\b(?:interview|interviews)", q): concept = "INTERVIEW"
        # Opportunity nouns and ordinary save/search language are semantic
        # evidence for the canonical opportunity collection.  In particular,
        # "did I save" must not fall through to the broader career profile.
        elif re.search(r"\b(?:opportunit(?:y|ies)|roles?)\b", q) or re.search(
            r"\b(?:sav(?:e|ed|ing)|similar|find|search)\b", q
        ): concept = "JOB_OPPORTUNITY"
        else: concept = "CAREER_PROFILE"
    # Recipe creation is still owned by the existing Recipe/Inventory Service;
    # distinguish it from read-only recipe cognition before model routing.
    if concept == "UNKNOWN" and operation in {"CREATE", "UPDATE", "DELETE"} and re.search(
        r"\b(?:recipe|recipes|cookbook|dish)\b", q,
    ):
        concept = "RECIPE"
        read_explicit = False
    if concept == "UNKNOWN" and re.search(r"\b(?:recipe|recipes|cookbook|dish)\b", q, re.IGNORECASE) and re.search(
        r"\bimport\b|\bfrom\s+https?://|https?://", q, re.IGNORECASE,
    ):
        concept = "RECIPE"
        operation = "READ"
        read_explicit = True
    # Household consumption is an owner mutation even when the item name is
    # not known to the compiler (for example, "Use one onion"). The executor
    # resolves that name against canonical owner-scoped inventory.
    if concept == "UNKNOWN" and operation == "READ" and re.search(
        r"\b(?:use|consume|used|consumed)\s+(?:\d+(?:\.\d+)?|one|a|an|two|three|four|five)\s+\S",
        q,
    ) and not re.search(r"\b(?:code|python|shell|command|tool|feature|api)\b", q):
        concept = "HOUSEHOLD_ITEM"
        operation = "EXECUTE"
        read_explicit = False

    # Public web access is an ordinary evidence capability. Keep bounded
    # lookup/fetch distinct from OSINT case management and deep research. A
    # local operational question such as "current network" does not match
    # these external-evidence predicates.
    if concept == "UNKNOWN" and re.search(
        r"\b(?:https?://|www\.)|"
        r"\b(?:search|look(?:\s+(?:this|that|it))?\s*up|lookup|browse)\b.{0,32}\b(?:web|internet|online)\b|"
        r"\b(?:web|internet|online)\b.{0,32}\b(?:search|look(?:\s+(?:this|that|it))?\s*up|lookup|browse)\b|"
        r"\b(?:latest|newest|current)\b.{0,48}\b(?:driver|release|version|price|news|docs?|forecast|weather|rate)\b|"
        r"\b(?:news|weather|forecast|exchange\s+rate)\b",
        q,
        re.IGNORECASE,
    ):
        concept = "WEB_URL" if re.search(r"(?:https?://|www\.)", q) else "WEB_EVIDENCE"
        operation = "READ"
        read_explicit = True
    if concept == "UNKNOWN" and _network_discovery_language and operation in {"EXECUTE", "RESEARCH"}:
        concept = "NETWORK"
    # Safe host inspection is a first-class read even when the user phrases
    # it as exploration or a hardware scan.  It never selects shell access.
    if (
        concept in {"UNKNOWN", "TECHNICAL_ASSET"}
        and re.search(r"\b(?:hardware|computational\s+assets?|machine|computer|host|system)\b", q)
        and re.search(r"\b(?:explore|inspect|check|scan)\b", q)
        and not re.search(r"\b(?:network|lan|subnet|service|daemon)\b", q)
    ):
        concept = "HOMELAB_HOST"
        operation = "READ"
        read_explicit = True
    if concept == "NETWORK" and _network_discovery_language:
        # The question can contain "what" and still be an executable
        # discovery objective.  A missing CIDR remains unauthorized/clarify-
        # bound below; current host context is not silently promoted to scope.
        operation = "EXECUTE"
        read_explicit = False
    # Keep advice, definitions, and generic explanations off specialized
    # canonical read contracts. These are safe general-model questions even
    # when they contain a golden-domain noun.
    if (
        concept in {"MEMORY", "NETWORK", "WORK", "GOAL", "PROJECT", "TASK", "COMMITMENT", "RUN", "MISSION", "WATCH"}
        and re.search(
            r"\b(?:why|explain|what\s+(?:is|are|does)|how\s+does|"
            r"difference\s+between|versus|what\s+should\s+i|"
            r"what\s+should\s+(?:you|i)\s+remember|"
            r"tell\s+me\s+about\s+(?:the\s+)?(?:memory|network(?:ing)?))\b",
            q,
        )
        and not re.search(r"\b(?:my|mine|right\s+now|current(?:ly)?|on\s+my\s+plate)\b", q)
        and not re.search(r"\bwe\b.{0,20}\bworking\b", q)
        and not re.search(r"\b(?:hades|waiting\s+on|needs?\s+attention|pending\s+approvals?)\b", q)
    ):
        concept = "UNKNOWN"
    # Make the operation class explicit for genuinely conceptual questions
    # that did not resolve to a canonical domain contract.  ``READ`` is the
    # safe lexical default, but it misleadingly presents general knowledge as
    # an attempted owner-state read in the IntentFrame.  Owner/current-state
    # qualifiers deliberately keep their canonical READ semantics.  This is
    # an operation-class projection, not a phrase-specific tool route: ANSWER
    # has no ActionSpec or executor and therefore cannot acquire authority.
    if (
        concept == "UNKNOWN"
        and operation == "READ"
        and re.search(
            r"^\s*(?:what\s+(?:is|are)\b|explain\b|define\b|"
            r"how\s+(?:does|do)\b|why\s+does\b|"
            r"what\s+does\b[^?]*\bmean\b|"
            r"tell\s+me\s+about\s+(?:the\s+)?network(?:ing)?\b)",
            q,
        )
        and not re.search(
            r"\b(?:my|mine|our|ours|we|i\s+(?:have|own)|own(?:ed)?|"
            r"current(?:ly)?|right\s+now|running|using|connected|on\s+my)\b",
            q,
        )
    ):
        operation = "ANSWER"
        read_explicit = False
    if (
        concept == "WORK"
        and re.search(r"\b(?:start|begin)\s+working\s+on\b|\bwhat\s+should\s+i\s+work\s+on\b", q)
    ):
        concept = "UNKNOWN"
    if concept == "DEVELOPER" and operation == "READ":
        read_explicit = True
    # A resolved opaque reference may supply the semantic subject when the
    # latest turn is intentionally terse (for example, "scan those hosts").
    # It never supplies an ActionSpec or executor.  Conflicting concepts stay
    # ambiguous and are handled by the normal caller/UI clarification path.
    if reference_resolution.get("status") == "RESOLVED":
        referenced_concept = str(reference_resolution.get("concept") or "").strip()
        # A server-owned asset reference disambiguates natural language such
        # as "the second machine".  Preserve that referent instead of letting
        # the generic host-inspection vocabulary change a detail read into an
        # unscoped local-host read.
        if referenced_concept == "TECHNICAL_ASSET" and concept == "HOMELAB_HOST":
            concept = referenced_concept
            operation = "READ"
            read_explicit = True
        if concept == "UNKNOWN" and referenced_concept:
            concept = referenced_concept
        resolved_refs = list(reference_resolution.get("refs") or [])
        if len(resolved_refs) == 1 and not target:
            target = resolved_refs[0]
    match = re.search(r"\b(?:about|for|asset)\s+([A-Za-z0-9_.:-]{2,80})", text, re.IGNORECASE)
    # A resolved opaque reference is stronger than a lexical fragment such as
    # ``about first``. Never replace a server-owned identity with an ordinal.
    if match and operation != "ANSWER" and not target and match.group(1).casefold() not in {
        "the", "a", "an", "one", "it", "that", "this", "these", "those",
        "me", "my", "mah", "mine", "myself", "you", "your", "yours", "us", "our",
        "ours", "them", "their", "theirs", "first", "second", "third",
        # These are collection/read-view nouns, not owner asset identities.
        # Without this boundary, phrases such as "technical asset state" or
        # "asset list" become a detail lookup for an asset literally named
        # ``state``/``list``.
        "state", "states", "list", "lists", "summary", "summaries",
        "inventory", "information", "info", "details", "detail", "data",
        "records", "record", "search", "results", "result", "gpu", "gpus",
        "vram", "ram", "memory", "cpu", "cpus", "processor", "processors",
        "motherboard", "storage", "specs", "specifications", "graphics", "cards",
    }:
        target = match.group(1)
    # A named asset is a bounded lexical candidate, not a model-selected
    # identity. The canonical asset binding still resolves/validates this
    # name owner-scoped before execution; extracting it here prevents phrases
    # such as "Thanatos hardware" from degrading into an unscoped collection
    # read.
    if concept == "TECHNICAL_ASSET" and not target:
        named_asset = re.search(
            r"\b(?:hardware|machine|computer|server|host)\s+"
            r"(?:is\s+)?(?:in|of)\s+([A-Za-z][A-Za-z0-9_.:-]{2,80})\b",
            text,
            re.IGNORECASE,
        )
        if named_asset is None:
            named_asset = re.search(
                r"\b([A-Za-z][A-Za-z0-9_.:-]{2,80})\s+"
                r"(?:hardware|machine|computer|server|host)\b",
                text,
                re.IGNORECASE,
            )
        candidate = named_asset.group(1) if named_asset else None
        if candidate and candidate.casefold() not in {
            "my", "mah", "our", "your", "their", "the", "a", "an", "current", "own", "owned",
            "what", "which", "tell", "show",
        }:
            target = candidate
    # A uniquely named asset plus a read-shaped asset concept is already a
    # deterministic canonical lookup, even when the user uses a terse
    # fragment such as "Thanatos hardware".  Do not make the model rediscover
    # the identity or arbitrate among unrelated Actions.
    remote_requested = False
    if concept == "TECHNICAL_ASSET" and target and operation == "READ":
        read_explicit = True
    # Remote inspection remains the same homelab contract, but its executor
    # must use a canonical owner Asset target rather than the local host.
    # This is an intent projection only; Asset resolution and SSH validation
    # still happen at the canonical execution boundary.
    if concept in {"TECHNICAL_ASSET", "HOMELAB_HOST"} and operation == "READ" and re.search(
        r"\b(?:remote|ssh|over\s+ssh|via\s+ssh)\b", q,
    ):
        concept = "HOMELAB_HOST"
        remote_target = re.search(
            r"\b(?:remote\s+)?(?:host|server|machine|system)\s+"
            r"([A-Za-z][A-Za-z0-9_.:-]{2,80})\b", text, re.IGNORECASE,
        )
        if remote_target and (not target or str(target).casefold() in {"remote", "ssh"}):
            target = remote_target.group(1)
        remote_requested = True
    if concept == "SERVICE" and operation == "EXECUTE" and not target:
        # A restart preflight is safe, but it is not meaningful without the
        # exact unit.  Keep the semantic contract available for qualified
        # requests while making an unqualified imperative clarification-bound.
        match = re.search(
            r"\b(?:restart|recover)\s+(?:the\s+)?(?:registered\s+)?(?:service\s+)?"
            r"([A-Za-z0-9_.:-]{2,80})\b",
            text,
            re.IGNORECASE,
        )
        if match and match.group(1).casefold() not in {"the", "service", "registered"}:
            target = match.group(1)
    safety_constraints: list[str] = []
    if re.search(r"\b(?:merge|join|combine|identify)\b", q) and re.search(
        r"\b(?:by|using|solely\s+on|alone)\s+ip(?:\s+address)?\b", q,
    ):
        safety_constraints.append("strong_identity_required")
    if re.search(r"\b(?:scan|discover|probe|enumerate)\b", q) and re.search(
        r"\b(?:public|internet|external)\b", q,
    ):
        safety_constraints.append("public_scope_requires_authorization")
    if re.search(r"\b(?:approve|replay)\b", q) and re.search(
        r"\b(?:changed|modified|completed|finished|old|stale)\b", q,
    ):
        safety_constraints.append("action_revalidation_required")
    # Active network observation is never authorized by a vague reference to
    # "my/local network" or by historical/current host context.  An explicit
    # bounded CIDR remains on the normal plan/approval/policy path; an
    # unscoped research/deep-dive request is a framework-owned clarification
    # instead of an empty bounded decision problem.
    if (
        concept == "NETWORK"
        and operation in {"EXECUTE", "RESEARCH"}
        and not re.search(
            r"(?<![\w.])(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
            r"(?:\.\d{1,3}){2}/\d{1,2}(?!\w)",
            q,
        )
    ):
        safety_constraints.append("network_scope_requires_authorization")
    if (
        concept == "UNKNOWN"
        and operation in {"EXECUTE", "RESEARCH"}
        and re.search(r"\b(?:scan\w*|discover\w*|probe\w*|enumerat\w*|investigate|research)\b", q)
        and (
            re.search(r"\b(?:network|lan|subnet|wifi|wi-fi|connection|connected)\b", q)
            or re.search(
                r"(?<![\w.])(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
                r"(?:\.\d{1,3}){2}/\d{1,2}(?!\w)",
                q,
            )
        )
    ):
        concept = "NETWORK"
    if (
        concept == "NETWORK"
        and operation in {"EXECUTE", "RESEARCH"}
        and not re.search(
            r"(?<![\w.])(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
            r"(?:\.\d{1,3}){2}/\d{1,2}(?!\w)",
            q,
        )
        and "network_scope_requires_authorization" not in safety_constraints
    ):
        safety_constraints.append("network_scope_requires_authorization")
    reference_filters = {}
    if remote_requested:
        reference_filters["remote"] = True
    if reference_resolution.get("status") == "RESOLVED" and len(reference_resolution.get("refs") or []) > 1:
        reference_filters["entity_refs"] = list(reference_resolution["refs"])
    semantic_view = deterministic_read_view(text, concept)
    if concept == "WORK" and (
        semantic_view == "attention"
        or re.search(r"\b(?:attention|waiting\s+on|pending\s+approvals?)\b", q)
    ):
        reference_filters["view"] = "attention"
    elif concept == "DEVELOPER":
        if re.search(r"\b(?:file|symbol|function|class|line|lines|region|open|view|read)\b", q) or re.search(
            r"\b[^\s]+\.(?:py|js|ts|tsx|jsx|go|rs|java|rb|md|yaml|yml|json|toml|ini|cfg)\b", q
        ):
            reference_filters["view"] = "file"
        elif re.search(r"\b(?:repo(?:sitory)?\s+map|tree|structure|layout|files?)\b", q):
            reference_filters["view"] = "map"
    elif concept == "INTEGRATION" and re.search(
        r"\bintegrations?\b.*\b(?:degraded|broken|attention|health|connected|working)\b|"
        r"\b(?:degraded|broken|attention|health)\b.*\bintegrations?\b", q,
    ):
        reference_filters["view"] = "integrations"
    elif concept == "NETWORK" and operation == "READ" and re.search(r"\b(?:unidentified|unknown|unrecognised|unrecognized)\b", q):
        reference_filters["view"] = "unidentified"
    elif concept == "NETWORK" and operation == "READ" and (
        semantic_view == "context" or re.search(
        r"\b(?:what\s+network|which\s+network|network\s+am\s+i|currently\s+connected|current(?:ly)?\s+(?:on|connected))\b",
        q,
    )):
        reference_filters["view"] = "context"
    elif concept == "NETWORK" and operation == "READ" and re.search(r"\b(?:role|roles|server|servers|router|routers|nas|printer|workstation|iot)\b", q):
        reference_filters["view"] = "roles"
    if concept == "RECIPE" and operation == "READ" and re.search(
        r"\b(?:find|search|look\s+for)\b", q,
    ):
        query_match = re.search(r"\b(?:find|search|look\s+for)\s+(?:a\s+)?(?:recipes?\s+(?:for\s+)?)?(.+)$", q)
        if query_match and query_match.group(1).strip():
            reference_filters["recipe_query"] = query_match.group(1).strip(" ?.!\n")
    if concept == "RECIPE" and operation == "READ" and re.search(
        r"\b(?:can\s+i\s+make|do\s+i\s+have\s+everything|pantry\s+coverage|"
        r"missing\s+ingredients?)\b", q,
    ):
        reference_filters["recipe_coverage"] = True
    if concept == "RECIPE" and operation == "READ" and re.search(
        r"\b(?:scale|resize|adjust)\b.{0,40}\b(?:to\s+)?(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+servings?\b", q,
    ):
        serving_target = deterministic_recipe_servings(q)
        if serving_target:
            reference_filters["recipe_scale"] = True
            reference_filters["servings"] = serving_target
    if concept == "RECIPE" and operation == "READ" and re.search(
        r"\b(?:expir(?:e|ing|y)|about\s+to\s+expire)\b", q,
    ) and re.search(r"\b(?:recipe|meal|dish|cook|make)\b", q):
        reference_filters["recipe_expiring"] = True
    if concept == "RECIPE" and operation == "READ" and re.search(
        r"\b(?:import|from)\b.*(?:recipe|https?://)|https?://", q, re.IGNORECASE,
    ):
        reference_filters["recipe_import"] = True
        source_url = recipe_source_url(text)
        if source_url:
            reference_filters["recipe_source_url"] = source_url
    if concept == "RECIPE" and operation == "CREATE" and re.search(r"https?://", q, re.IGNORECASE):
        reference_filters["recipe_import"] = True
        source_url = recipe_source_url(text)
        if source_url:
            reference_filters["recipe_source_url"] = source_url
        requested_name = recipe_requested_name(text)
        if requested_name:
            reference_filters["recipe_requested_name"] = requested_name
    if concept == "TECHNICAL_ASSET" and operation == "READ":
        # Aggregations remain canonical Asset reads.  Preserve only the
        # bounded component/model term for the inventory adapter; never ask
        # the model to count from prose or memory.
        aggregate = re.search(r"\bhow\s+many\s+(.+?)\s+do\s+i\s+have\b", q)
        if aggregate:
            component = re.sub(r"\b(?:gpus?|graphics\s+cards?|machines?|servers?|boxes?)\b", "", aggregate.group(1), flags=re.IGNORECASE)
            component = re.sub(r"\s+", " ", component).strip(" ?.,")
            if component:
                reference_filters["asset_query"] = component
                reference_filters["asset_projection"] = "count"
        property_match = re.search(
            r"\b(specs?|specifications?|cpus?|processors?|ram|memory|gpus?|graphics\s+cards?|"
            r"storage|motherboard|os|operating\s+system)\b", q,
        )
        collection_property = bool(re.search(
            r"\b(?:which|what|how\s+many|how\s+much|show|list|find|search)\b",
            q,
        ))
        if property_match and (
            target
            or reference_resolution.get("status") == "RESOLVED"
            or collection_property
        ):
            property_name = property_match.group(1).replace(" ", "_")
            reference_filters["asset_property"] = {
                "cpus": "cpu", "processors": "processor", "gpus": "gpu",
                "graphics_cards": "gpu", "specification": "specs",
                "specifications": "specs",
            }.get(property_name, property_name)
        filter_match = re.search(
            r"\b(?:with|having|has|containing)\s+(?:an?\s+)?"
            r"((?:rtx|gtx|quadro|tesla|radeon|arc)\s+\d{3,5})\b", q,
        )
        if filter_match and re.search(r"\b(?:which|what|find|show|list)\b", q):
            reference_filters["asset_query"] = filter_match.group(1).strip(" .?!")
            reference_filters["asset_projection"] = "filter"
    workspace = {
        "MEMORY": "hades", "WORK": "work", "GOAL": "work", "PROJECT": "work", "TASK": "work", "RUN": "work", "COMMITMENT": "work", "MISSION": "work", "WATCH": "work", "CAREER_PROFILE": "work", "JOB_SEARCH": "work",
        "JOB_OPPORTUNITY": "work", "APPLICATION": "work", "INTERVIEW": "communications",
        "TECHNICAL_ASSET": "infrastructure", "NETWORK": "infrastructure", "HOMELAB_HOST": "infrastructure",
        "SERVICE": "infrastructure", "SECURITY_FINDING": "infrastructure", "SECURITY_ENGAGEMENT": "infrastructure",
        "SECURITY_EVIDENCE": "infrastructure", "OSINT_CASE": "research", "RESEARCH": "research",
        "WEB_EVIDENCE": "web", "WEB_URL": "web",
        "HOUSEHOLD_ITEM": "home", "INTEGRATION": "system",
        "COMMUNICATIONS": "communications", "DEVELOPER": "developer",
        "CONTACT": "communications",
    }.get(concept)
    return IntentFrame(
        operation_class=operation,
        domain_concept=concept,
        workspace_hint=workspace,
        target=target,
        entity_reference=target or (
            (reference_resolution.get("refs") or [None])[0]
            if reference_resolution.get("status") == "RESOLVED"
            else None
        ),
        run_reference=run_reference,
        continuation_reference=run_reference if operation == "CONTINUE" else None,
        depth=_depth(text),
        constraints=(
            (("no_filesystem_fallback",) if concept in {"TECHNICAL_ASSET", "NETWORK", "HOMELAB_HOST", "SERVICE"} else ())
            + tuple(safety_constraints)
        ),
        desired_output="grounded_structured_summary" if operation == "READ" else None,
        reference_resolution=reference_resolution,
        filters=reference_filters,
        read_explicit=read_explicit,
    )


def resolve_continuation(frame: IntentFrame, active_run: Mapping[str, Any] | None) -> ContinuationResolution:
    """Resolve generic continuation language against durable Run state.

    This is deliberately a decision projection. The caller still performs
    normal policy, approval, ActionSpec, and executor checks.
    """
    if frame.operation_class != "CONTINUE":
        return ContinuationResolution("NOT_CONTINUATION", reason="intent is not CONTINUE")
    if not isinstance(active_run, Mapping):
        return ContinuationResolution("BLOCKED", reason="no active Run")
    status = str(active_run.get("status") or "").lower()
    run_id = str(active_run.get("id") or active_run.get("run_id") or "").strip() or None
    lifecycle = str(active_run.get("lifecycle_state") or "").lower()
    if status in {"completed", "failed", "cancelled"} or lifecycle in {"succeeded", "failed", "cancelled"}:
        return ContinuationResolution("BLOCKED", run_reference=run_id, phase="TERMINAL", reason="Run is terminal")
    state = active_run.get("continuation_state") if isinstance(active_run.get("continuation_state"), Mapping) else {}
    action_id = str(state.get("pending_action_id") or active_run.get("pending_action_id") or "").strip() or None
    if not run_id:
        return ContinuationResolution("BLOCKED", reason="active Run has no durable reference")
    if state.get("execution_ambiguous"):
        return ContinuationResolution(
            "BLOCKED", run_reference=run_id, action_reference=action_id,
            phase="EXECUTION_AMBIGUOUS", reason="independent verification is required before retry",
        )
    next_step = active_run.get("next_step")
    if isinstance(next_step, Mapping):
        next_status = str(next_step.get("status") or "").upper()
        next_action = next_step.get("action") if isinstance(next_step.get("action"), Mapping) else {}
        next_action_id = str(next_action.get("id") or "").strip() or action_id
        if next_status == "WAITING_APPROVAL":
            return ContinuationResolution("RESOLVED", run_id, next_action_id, "AWAITING_APPROVAL", "exact approval is pending")
        if next_status == "WAITING_INPUT":
            return ContinuationResolution("RESOLVED", run_id, next_action_id, "AWAITING_INPUT", "required input is pending")
        if next_status in {"READY", "IN_PROGRESS"} and next_action:
            return ContinuationResolution("RESOLVED", run_id, next_action_id, next_status, "durable next Action is available")
        if next_status == "COMPLETE":
            return ContinuationResolution("BLOCKED", run_id, next_action_id, "COMPLETE", "Run deliverable is already complete")
        if next_status in {"BLOCKED", "NO_PLAN", "UNAVAILABLE"}:
            return ContinuationResolution("BLOCKED", run_id, next_action_id, next_status, str(next_step.get("reason") or "Run cannot be continued safely"))
    actions = active_run.get("actions")
    if isinstance(actions, list):
        candidates = [item for item in actions if isinstance(item, Mapping) and item.get("status") in {
            "awaiting_approval", "awaiting_input", "proposed", "approved", "executing", "completed",
        }]
        for item in reversed(candidates):
            item_id = str(item.get("id") or "").strip() or None
            item_status = str(item.get("status") or "").lower()
            if item_status == "awaiting_approval":
                return ContinuationResolution("RESOLVED", run_id, item_id, "AWAITING_APPROVAL", "exact approval is pending")
            if item_status == "awaiting_input":
                return ContinuationResolution("RESOLVED", run_id, item_id, "AWAITING_INPUT", "required input is pending")
            if item_status in {"proposed", "approved", "executing"}:
                return ContinuationResolution("RESOLVED", run_id, item_id, item_status.upper(), "pending Action is available")
    phase = "AWAITING_APPROVAL" if status == "awaiting_approval" else "AWAITING_INPUT" if status == "awaiting_input" else "RUNNING"
    return ContinuationResolution("RESOLVED", run_id, action_id, phase)


def resolve_intent(frame: IntentFrame) -> ResolvedContract:
    contract_key = frame.domain_concept
    if frame.domain_concept == "RECIPE" and frame.operation_class in {"CREATE", "UPDATE", "DELETE"}:
        contract_key = "RECIPE_MUTATION"
    if frame.domain_concept == "HOUSEHOLD_ITEM" and frame.operation_class in {"CREATE", "UPDATE", "EXECUTE"}:
        contract_key = "INVENTORY_MUTATION"
    contract = DOMAIN_CONTRACTS.get(contract_key)
    if contract is None:
        return ResolvedContract(frame, None, None, None, None, False, "no_domain_contract")
    if frame.domain_concept == "SERVICE" and frame.operation_class == "EXECUTE" and not frame.target:
        return ResolvedContract(frame, contract, None, None, contract.binding, False, "target_required")
    action_key = frame.operation_class
    # URL-backed recipe creation is an import. Route it through the existing
    # validated import commit instead of an under-specified primitive add.
    if (
        frame.domain_concept == "RECIPE"
        and frame.operation_class == "CREATE"
        and frame.filters.get("recipe_import") is True
    ):
        action_key = "CREATE_IMPORT_COMMIT"
    if frame.domain_concept == "HOMELAB_HOST" and frame.filters.get("remote") and frame.operation_class == "READ":
        action_key = "REMOTE_READ"
    if frame.domain_concept in {"TECHNICAL_ASSET", "RECIPE"} and frame.operation_class == "READ" and frame.entity_reference:
        action_key = "READ_DETAIL"
    if frame.domain_concept == "WORK" and frame.filters.get("view") == "attention":
        action_key = "READ_ATTENTION"
    elif frame.domain_concept == "INTEGRATION" and frame.filters.get("view") == "integrations":
        action_key = "READ_INTEGRATIONS"
    elif frame.domain_concept == "NETWORK" and frame.filters.get("view") == "unidentified":
        action_key = "READ_UNIDENTIFIED"
    elif frame.domain_concept == "NETWORK" and frame.filters.get("view") == "context":
        action_key = "READ_CONTEXT"
    elif frame.domain_concept == "NETWORK" and frame.filters.get("view") == "roles":
        action_key = "READ_ROLES"
    elif frame.domain_concept == "RECIPE" and frame.filters.get("recipe_query"):
        action_key = "READ_SEARCH"
    elif frame.domain_concept == "RECIPE" and frame.filters.get("recipe_expiring") is True:
        action_key = "READ_EXPIRING"
    elif frame.domain_concept == "RECIPE" and frame.operation_class == "READ" and frame.filters.get("recipe_import") is True:
        action_key = "READ_IMPORT_PREPARE"
    elif frame.domain_concept == "RECIPE" and frame.filters.get("recipe_coverage") is True:
        action_key = "READ_COVERAGE"
    elif frame.domain_concept == "RECIPE" and frame.filters.get("recipe_scale") is True:
        action_key = "READ_SCALE"
    elif frame.domain_concept == "DEVELOPER" and frame.filters.get("view") == "file":
        action_key = "READ_FILE"
    elif frame.domain_concept == "DEVELOPER" and frame.filters.get("view") == "map":
        action_key = "READ_MAP"
    action_id = contract.actions.get(action_key)
    if action_id is None and frame.operation_class == "CONTINUE":
        action_id = contract.actions.get("EXECUTE") or contract.actions.get("READ")
    if action_id is None:
        return ResolvedContract(frame, contract, None, None, contract.binding, False, "operation_not_registered")
    capability = capability_for_id(contract.capability_id)
    action = capability.actions.get(action_id) if capability else None
    if action is None or not action.known:
        return ResolvedContract(frame, contract, action_id, action, contract.binding, False, "actionspec_unavailable")
    binding = binding_for_tool(contract.binding or "") if contract.binding else None
    if binding is None or binding.capability_id != contract.capability_id:
        return ResolvedContract(frame, contract, action_id, action, contract.binding, False, "tool_binding_unavailable")
    return ResolvedContract(frame, contract, action_id, action, binding.transport_name, True)


def validate_contracts() -> list[str]:
    errors = []
    for concept, contract in DOMAIN_CONTRACTS.items():
        capability = capability_for_id(contract.capability_id)
        if capability is None:
            errors.append(f"{concept}: missing capability {contract.capability_id}")
            continue
        for operation, action_id in contract.actions.items():
            action = capability.actions.get(action_id)
            if action is None:
                errors.append(f"{concept}/{operation}: missing ActionSpec {action_id}")
                continue
            if contract.binding and binding_for_tool(contract.binding) is None:
                errors.append(f"{concept}: missing ToolBinding {contract.binding}")
            if contract.binding:
                binding = binding_for_tool(contract.binding)
                properties = (((binding.native_schema or {}).get("function") or {}).get("parameters") or {}).get("properties") or {} if binding else {}
                action_enum = ((properties.get("action") or {}).get("enum") or []) if isinstance(properties, Mapping) else []
                # Multiplexed Hades bindings expose ActionSpec IDs in an
                # `action` enum. Single-purpose transport bindings such as
                # web_search/web_fetch expose their semantic action through
                # the binding identity and intentionally have no action field.
                missing_exposure = (
                    sorted(set(contract.actions.values()) - set(action_enum))
                    if "action" in properties else []
                )
                if missing_exposure:
                    errors.append(f"{concept}: native schema omits ActionSpec exposure {missing_exposure}")
                textual_contract = str(binding.textual_contract or "") if binding else ""
                missing_textual = sorted(
                    action_id for action_id in set(contract.actions.values())
                    if action_id not in textual_contract
                )
                if missing_textual:
                    errors.append(f"{concept}: textual contract omits ActionSpec exposure {missing_textual}")
            if operation in {"READ", "READ_DETAIL", "REMOTE_READ", "READ_FILE", "READ_MAP", "READ_INTEGRATIONS", "READ_UNIDENTIFIED", "READ_ROLES", "READ_CONTEXT"} and action.approval.value != "none":
                errors.append(f"{concept}/{action_id}: read requires approval")
            if operation in {"READ", "READ_DETAIL", "REMOTE_READ", "READ_INTEGRATIONS", "READ_UNIDENTIFIED", "READ_ROLES", "READ_CONTEXT"} and contract.capability_id not in {"developer.read", "web.evidence"} and "read_private" not in action.effects:
                errors.append(f"{concept}/{action_id}: read lacks read_private effect")
            if operation in {"READ_FILE", "READ_MAP"} and "read_workspace" not in action.effects:
                errors.append(f"{concept}/{action_id}: developer read lacks read_workspace effect")
            if not action.executor_key:
                errors.append(f"{concept}/{action_id}: missing executor")
            if not contract.result_contract:
                errors.append(f"{concept}/{action_id}: missing result contract")
    return errors


def generated_parity_matrix() -> list[dict[str, Any]]:
    """Generate transport applicability rows from the canonical contracts."""
    rows = []
    for concept, contract in DOMAIN_CONTRACTS.items():
        for operation, action_id in contract.actions.items():
            capability = capability_for_id(contract.capability_id)
            action = capability.actions.get(action_id) if capability else None
            rows.append({
                "concept": concept,
                "operation": operation,
                "action_id": action_id,
                "capability_id": contract.capability_id,
                "binding": contract.binding,
                "exposure": dict(contract.exposures),
                "result_contract": contract.result_contract,
                "effects": list(action.effects) if action else [],
                "approval": action.approval.value if action else None,
                "executor": action.executor_key if action else None,
                "execution_location": action.execution_location if action else None,
            })
    return rows


def result_status(result: Any) -> str:
    """Classify canonical results without turning failure-shaped empties into zero."""
    if not isinstance(result, Mapping):
        return "INVALID_RESULT"
    if result.get("error") or result.get("failed") is True or result.get("unavailable") is True:
        return "FAILED" if not result.get("unavailable") else "UNAVAILABLE"
    if result.get("status") in {
        "EMPTY_RESULT", "SUCCESS_EMPTY", "SUCCESS", "SUCCESS_WITH_DATA",
        "SUCCESS_RESULT", "DEGRADED", "UNAVAILABLE", "FAILED",
    }:
        return str(result["status"])
    if not result:
        return "INVALID_RESULT"
    if isinstance(result.get("assets"), list) and not result["assets"]:
        return "EMPTY_RESULT"
    return "SUCCESS_RESULT"


def validate_result(frame: IntentFrame, result: Any) -> tuple[bool, str]:
    """Validate the small result shape promised by a resolved domain contract."""
    status = result_status(result)
    if status in {"FAILED", "UNAVAILABLE", "INVALID_RESULT"}:
        return False, status
    if frame.domain_concept == "TECHNICAL_ASSET" and frame.operation_class == "READ":
        if not isinstance(result.get("assets"), list):
            return False, "INVALID_RESULT"
    if frame.domain_concept == "NETWORK" and frame.operation_class == "READ":
        view = frame.filters.get("view")
        if view == "unidentified":
            if not isinstance(result.get("hosts"), list):
                return False, "INVALID_RESULT"
        elif view == "roles":
            if not isinstance(result.get("hypotheses"), list):
                return False, "INVALID_RESULT"
        elif not isinstance(result.get("nodes"), list) or not isinstance(result.get("edges"), list):
            return False, "INVALID_RESULT"
    if frame.domain_concept == "SECURITY_FINDING" and frame.operation_class == "READ":
        if not isinstance(result.get("findings"), list):
            return False, "INVALID_RESULT"
    if frame.domain_concept == "RECIPE" and frame.operation_class == "READ":
        if frame.filters.get("recipe_import") is True:
            if result.get("status") not in {"READY_FOR_REVIEW", "NEEDS_REVIEW"}:
                return False, "INVALID_RESULT"
        elif frame.filters.get("recipe_coverage") is True:
            if not isinstance(result.get("can_make"), bool) or not isinstance(result.get("shortages"), list):
                return False, "INVALID_RESULT"
        elif frame.filters.get("recipe_scale") is True:
            if not isinstance(result.get("scaled_ingredients"), list) or not result.get("servings"):
                return False, "INVALID_RESULT"
        elif frame.filters.get("recipe_expiring") is True:
            if not isinstance(result.get("candidates"), list):
                return False, "INVALID_RESULT"
        elif frame.entity_reference:
            if not isinstance(result.get("recipe"), Mapping):
                return False, "INVALID_RESULT"
        elif not isinstance(result.get("recipes"), list):
            return False, "INVALID_RESULT"
    return True, status


def validate_bound_result(binding_name: str, action_id: str, result: Any) -> tuple[bool, str]:
    """Validate a registered binding result against its declared contract.

    The dispatcher knows the canonical binding and ActionSpec but does not
    receive natural-language text. Resolve the owning DomainContract by that
    stable pair instead of asking an adapter or model to identify its own
    result semantics. Mutating/unregistered actions intentionally pass
    through here; their existing verified-execution lifecycle remains the
    authority for those payloads.
    """
    binding_name = str(binding_name or "").strip()
    action_id = str(action_id or "").strip()
    if binding_name == "developer_read":
        if not isinstance(result, Mapping) or not isinstance(result.get("output"), str):
            return False, "INVALID_RESULT"
        return True, "SUCCESS_RESULT"
    for concept, contract in DOMAIN_CONTRACTS.items():
        if contract.binding != binding_name:
            continue
        for operation, registered_action in contract.actions.items():
            if registered_action != action_id:
                continue
            if operation in {"READ", "READ_SEARCH", "READ_DETAIL", "READ_COVERAGE", "READ_SCALE", "READ_INTEGRATIONS", "READ_UNIDENTIFIED", "READ_ROLES"}:
                filters = {}
                if operation == "READ_INTEGRATIONS":
                    filters["view"] = "integrations"
                elif operation == "READ_UNIDENTIFIED":
                    filters["view"] = "unidentified"
                elif operation == "READ_ROLES":
                    filters["view"] = "roles"
                elif operation == "READ_SEARCH":
                    filters["recipe_query"] = "search"
                elif operation == "READ_COVERAGE":
                    filters["recipe_coverage"] = True
                elif operation == "READ_SCALE":
                    filters["recipe_scale"] = True
                if operation == "READ_DETAIL":
                    frame_entity_reference = "recipe"
                else:
                    frame_entity_reference = None
                frame = IntentFrame(
                    operation_class="READ",
                    domain_concept=concept,
                    filters=filters,
                    read_explicit=True,
                    entity_reference=frame_entity_reference,
                )
                valid, reason = validate_result(frame, result)
                # Explicit adapter availability failures are truthful control
                # plane outcomes, not malformed successful payloads. Preserve
                # them for grounded reporting while still rejecting invalid
                # success-shaped data below.
                if reason in {"FAILED", "UNAVAILABLE"}:
                    return True, reason
                if not valid:
                    return valid, reason
                # Collection reads have a stable top-level member even when
                # the collection is empty.  Enforce that small contract at
                # the control-plane boundary rather than allowing an
                # adapter's bare SUCCESS marker to become canonical truth.
                expected = {
                    ("OSINT_CASE", "list_cases"): "cases",
                    ("RESEARCH", "list_cases"): "cases",
                    ("GOAL", "list_goals"): "goals",
                    ("PROJECT", "list_projects"): "projects",
                    ("TASK", "list_tasks"): "tasks",
                    ("RUN", "list_runs"): "runs",
                    ("COMMITMENT", "list_commitments"): "commitments",
                    ("MISSION", "list_missions"): "missions",
                    ("WATCH", "list_watches"): "watches",
                    ("HOUSEHOLD_ITEM", "list_items"): "items",
                    ("HOUSEHOLD_ITEM", "search_items"): "items",
                    ("RECIPE", "list"): "recipes",
                    ("RECIPE", "search"): "recipes",
                    ("RECIPE", "get"): "recipe",
                    ("RECIPE", "scale"): "scaled_ingredients",
                    ("RECIPE", "expiring_candidates"): "candidates",
                    ("RECIPE", "prepare_import"): "draft",
                    ("COMMUNICATIONS", "overview"): "email",
                    ("CONTACT", "contacts"): "contacts",
                }.get((concept, action_id))
                if expected and not isinstance(result.get(expected), (list, dict)) and not (
                    concept == "RECIPE" and action_id == "prepare_import"
                    and result.get("status") == "NEEDS_REVIEW" and result.get(expected) is None
                ):
                    return False, "INVALID_RESULT"
                return True, reason
            # Contracted non-read projections currently have no additional
            # shape rules here; the trusted executor and Run verifier remain
            # authoritative for their effects.
            return True, result_status(result)
    return True, result_status(result)


def classify_compatibility_request(
    messages: list[dict],
    last_user: str,
    *,
    recent_context_for_retrieval,
    explicit_memory_query,
    contextual_retry_continuation,
    contextual_reference_followup,
    explicit_continuation,
    assistant_requested_followup,
    specialized_operational_domains,
) -> dict[str, object]:
    """Classify legacy-only retrieval hints without owning ACI semantics.

    First-class concepts must use ``compile_intent``/``resolve_intent``. This
    bounded projection exists only for older document, email, UI, and shell
    compatibility surfaces that have not crossed that contract yet.
    """
    text = str(last_user or "").strip()
    retry_continuation = contextual_retry_continuation(messages, text)
    contextual_reference = contextual_reference_followup(messages, text)
    continuation = (
        explicit_continuation(text)
        or assistant_requested_followup(messages)
        or retry_continuation
        or contextual_reference
    )
    if re.fullmatch(r"192\.168\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?", text):
        recent_text = " ".join(
            str(message.get("content") or "")
            for message in messages[-10:]
            if message.get("role") in {"user", "assistant"}
        ).lower()
        continuation = continuation or bool(
            re.search(r"\b(scan|discover|network|subnet|range)\b", recent_text)
        )
    retrieval_query = (
        recent_context_for_retrieval(messages, max_user=5, max_chars=1800)
        if continuation else text
    )
    query = retrieval_query.lower()
    if explicit_memory_query(text):
        return {
            "low_signal": False,
            "continuation": continuation,
            "domains": {"memory"},
            "retrieval_query": text,
            "explicit_memory_query": True,
        }
    if not text or bool(_LOW_SIGNAL_RE.match(text)) or is_casual_low_signal(text):
        return {
            "low_signal": True,
            "continuation": False,
            "domains": set(),
            "retrieval_query": text,
            "general_explanatory": bool(
                re.search(r"\b(?:explain|define|teach\s+me|how\s+does|why)\b", query)
            ),
        }

    domains: set[str] = set()

    def has(*patterns: str) -> bool:
        return any(re.search(pattern, query) for pattern in patterns)

    explanatory_only = (
        has(r"\b(?:explain|define|teach\s+me|how\s+does|why)\b")
        and not has(
            r"\b(?:my|our|your|current|this)\b.{0,36}\b(?:host|machine|system|network|lan|subnet|container|disk|service|storage)\b"
        )
    )
    if has(r"\b(cookbook|serve|serving|served|launch|preset|vllm|sglang|llama\.?cpp|ollama|download|downloading|pull|cached models?|running models?|model servers?|models? (?:are )?running|what models?|model picker|gpu box|workstation|server|qwen|gemma|llama|mistral|minimax)\b"):
        domains.add("cookbook")
    if has(r"\b(emails?|mails?|gmail|inbox|reply|forward|cc|bcc|send email|compose email|draft email|message chris|message him|message her)\b"):
        domains.add("email")
    if has(r"\b(notes?|todos?|to-dos?|checklists?|tasks?|task list|remind me|reminders?|buy|pickup|pick up)\b") or has(r"\b(every day|every morning|every evening|recurring|automatically|cron|scheduled task|background task)\b") or has(r"\b(calendar|event|meeting|appointment|schedule)\b"):
        domains.add("notes_calendar_tasks")
    if has(
        r"\b(documents?|docs?|draft|poem|story|essay|outline|letter|edit|rewrite|proofread|suggest|feedback|review this|make a file)\b",
        r"\bcompose\b.{0,32}\b(document|doc|draft|letter|email|message|story|poem|essay|outline|report|proposal|memo|summary|client update)\b",
    ) or ("notes_calendar_tasks" not in domains and has(r"\bwrite\b")):
        domains.add("documents")
    network_target = has(
        r"\b(?:local|internal|current|home|private|our|my)\b.{0,32}\bnet\w*work\b",
        r"\bnet\w*work\b.{0,40}\b(?:hosts?|servers?|devices?|subnets?|lan|commands?)\b",
        r"\b(?:hosts?|servers?|devices?)\b.{0,40}\b(?:net\w*work|lan|subnets?|reachable|online)\b",
        r"\b(?:ip\s+addr|ip\s+route|ip\s+neigh|arp|nmcli|nmap|traceroute|known_hosts)\b",
    )
    network_action = has(
        r"\b(?:discover\w*|dicover\w*|scan\w*|inventory|map|inspect|probe|find|see|list|check|identify|reachable|online)\b",
        r"\b(?:run|execute)\b.{0,24}\bnet\w*work\s+commands?\b",
    )
    if network_target and network_action:
        domains.add("network_ops")
    if has(r"\b(search|web|google|look up|latest|news|weather|forecast|stock price|price of|website|url|https?://|www\.)\b") or has(
        r"\b(wyszukaj|wyszukać|wyszukac)\b.*\b(internet|internecie|online|web)\b",
        r"\b(sprawd[zź]|znajd[zź])\b.*\b(internet|internecie|online|web)\b",
        r"\b(aktualn\w*|bieżąc\w*|biezac\w*|dzisiaj|teraz)\b.*\b(pogod\w*|temperatur\w*)\b",
    ):
        domains.add("web")
    if "network_ops" not in domains and has(r"\b(research|deep dive|investigate|look into)\b"):
        domains.add("web")
    if has(r"\b(open|show|toggle|turn on|turn off|disable|enable|switch model|change model|settings|theme|panel)\b"):
        domains.add("ui")
    if has(r"\b(session|chat history|rename chat|delete chat|archive chat|fork chat|list chats)\b"):
        domains.add("sessions")
    shell_commands = r"echo|printf|top|htop|uname|pwd|whoami|uptime|ps|free|df|du|ls|cat|grep|rg|find|git|docker|podman|systemctl|journalctl|ip|ss|ping|curl|wget|bash|sh|fish|python|python3|node|npm|pnpm|yarn|make|cmake|gcc|clang|cargo|go|java|javac|dnf|apt|pacman|rpm|flatpak|nvidia-smi|lspci|lsblk|mount"
    if has(rf"^\s*(?:please\s+)?(?:run|execute)\s+(?:sudo\s+)?(?:{shell_commands})\b", rf"^\s*(?:can|could|would)\s+you\s+(?:please\s+)?(?:run\s+)?(?:{shell_commands})\b", r"\buse\s+(?:bash|shell|terminal)\s+(?:to|like)\b"):
        domains.add("shell_exec")
    if has(r"\b(?:you|we)\s+(?:have|got)\s+(?:bash|shell|terminal)\b.{0,48}\b(?:run|execute)\b", r"^\s*(?:please\s+)?(?:run|execute)\s+(?:network\s+)?commands?\b"):
        domains.add("shell_exec")
    if "shell_exec" not in domains and "network_ops" not in domains and has(r"\b(file|folder|directory|repo|git|grep|find in files|read file|edit file|shell|terminal|bash)\b"):
        domains.add("files")
    if has(r"\b(run|execute|test|debug|fix|save|create|edit|read|open)\b.{0,40}\b(?:python|javascript|typescript|java|c\+\+|cpp|c#|csharp|rust|go|golang|ruby|php|swift|kotlin|bash|shell|html|css|sql|code|script|program|game)\b", r"\b(?:python|javascript|typescript|java|c\+\+|cpp|c#|csharp|rust|go|golang|ruby|php|swift|kotlin|bash|shell|html|css|sql)\b.{0,40}\b(file|script|program|app)\b"):
        domains.add("files")
    if has(r"\b(background|bg)\s+(?:jobs?|task)\b") or has(r"\b(kill|stop|cancel|terminate|check|tail|show|list)\b.{0,16}\bjobs?\b") or has(r"\bjobs?\b.{0,16}\b(output|status|done|finished|running)\b"):
        domains.add("files")
    if has(r"\b(?:docker(?:\s+compose)?|compose|containers?|systemd|daemons?|services?)\b") and has(r"\b(?:diagnose|diagnosis|debug|troubleshoot|troubleshooting|fix|broken|failing|failed|failure|restart|restarting|restart loop|crash|crashing|unhealthy|down|logs?|errors?|stuck)\b"):
        domains.add("operations")
    if has(r"\b(endpoint|api token|mcp|webhook|preference|configure|config|setting)\b"):
        domains.add("settings")
    if has(r"\b(contact|contacts|phone|phone number|address book|vcard)\b"):
        domains.add("contacts")
    if has(r"\bapi[ _]call\b", r"\bintegrations?\b", r"\b(?:home ?assistant|miniflux|gitea|linkding|jellyfin)\b"):
        domains.add("integrations")

    storage_subject = has(r"\b(?:disk|disks|storage|filesystem|file system|mount|mounts|volume|volumes|partition|partitions|lvm|zfs|btrfs|raid|mdadm|smart|nvme|inode|inodes|i/o|io)\b")
    storage_action = has(r"\b(?:inspect|check|diagnose|diagnosis|troubleshoot|investigate|find|show|list|health|usage|capacity|space|full|free|degraded|failed|failing|read-only|mounted|unmounted|missing|slow|why)\b")
    if not explanatory_only and storage_subject and storage_action:
        domains.add("storage_ops")
    container_subject = has(r"\b(?:docker|podman|compose|containers?|container\s+(?:network|volume|image)|docker\s+(?:network|volume|image))\b")
    container_action = has(r"\b(?:inspect|show|list|diagnose|diagnosis|troubleshoot|check|why|running|exited|exit|logs?|health|networks?|volumes?|images?|stuck|restart|restarting|failed|failing)\b")
    if container_subject and container_action:
        domains.add("container_ops")
    remote_subject = has(r"\b(?:over ssh|via ssh|remote\s+(?:host|server|machine)|ssh\s+into|connect\s+to)\b")
    remote_action = has(r"\b(?:check|inspect|diagnose|run|execute|show|list|compare|connect|ssh|read|tail|review)\b")
    if remote_subject and remote_action:
        domains.add("remote_ops")
    security_subject = has(r"\b(?:security posture|security audit|sshd|ssh configuration|firewall|listening ports?|open ports?|failed logins?|authentication failures?|permissions?|tls|certificates?|exposure|hardening)\b")
    security_action = has(r"\b(?:audit|assess|inspect|check|review|show|find|diagnose|evaluate)\b")
    if security_subject and security_action:
        domains.add("security_audit")
    pentest_topic = has(r"\b(?:pentest|pen test|penetration test|vulnerability scan|security assessment|authorized security test|authorized scan|enumerate services?|service enumeration|port scan|nmap scan)\b")
    pentest_target = has(r"\b(?:this|that|my|our|your|the)\s+(?:host|machine|system|network|lan|server|site|target)\b", r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2}\b")
    pentest_action = has(r"\b(?:run|perform|execute|start|begin|launch|test|scan|enumerate|assess|probe|pentest)\b")
    if pentest_topic and pentest_target and pentest_action:
        domains.add("pentest_ops")
    if has(r"\b(?:osint|open[- ]source intelligence|public records?|public information)\b") and has(r"\b(?:research|investigate|find|search|look up|lookup|trace|profile|map|correlate|deep dive)\b"):
        domains.add("osint")
    system_subject = has(r"\b(?:cpu|memory|ram|swap|load average|processes?|kernel|boot|system logs?|journal|hardware|temperature|thermal|uptime|performance)\b")
    system_action = has(r"\b(?:inspect|check|explore|scan|diagnose|diagnosis|troubleshoot|investigate|find|show|review|health|usage|pressure|slow|high|errors?|failed|failing|why)\b")
    if system_subject and system_action:
        domains.add("system_ops")
    if "container_ops" in domains:
        domains.difference_update({"storage_ops", "operations"})
    if "pentest_ops" in domains:
        domains.difference_update({"network_ops", "security_audit"})
    if "security_audit" in domains:
        domains.difference_update({"operations", "remote_ops"})
    if "storage_ops" in domains and not has(r"\b(?:cpu|memory|ram|swap|load average|processes?|kernel|boot|thermal|temperature)\b"):
        domains.discard("system_ops")
    if domains & set(specialized_operational_domains):
        domains.discard("files")
    return {
        "low_signal": not continuation and not domains,
        "continuation": continuation,
        "domains": domains,
        "retrieval_query": retrieval_query,
        "general_explanatory": explanatory_only,
    }
