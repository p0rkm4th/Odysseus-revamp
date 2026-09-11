"""Bounded, deterministic recipe text extraction.

Recipe imports are untrusted input.  This module only produces a recipe
candidate; it never changes inventory or queues groceries.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.inventory_units import UnitError, normalize_amount

MAX_RECIPE_TEXT = 24_000
MAX_INGREDIENTS = 64

_SECTION_START = re.compile(r"^(ingredients?|what you need)\s*:?[\s]*$", re.I)
_SECTION_END = re.compile(r"^(directions?|instructions?|method|steps?|preparation)\s*:?[\s]*$", re.I)
_SERVINGS = re.compile(r"(?:serves?|servings?|yield)\s*[:\-]?\s*(\d+(?:\.\d+)?)", re.I)
_LINE = re.compile(
    r"^(?:[-*•]\s*)?(?:(\d+(?:\.\d+)?(?:\s+\d+/\d+)?)\s+)?"
    r"([A-Za-z]+)?\s*(?:of\s+)?(.+?)\s*$"
)
_UNITS = {
    "g", "gram", "grams", "kg", "kilogram", "kilograms", "oz", "ounce", "ounces",
    "lb", "lbs", "pound", "pounds", "ml", "milliliter", "milliliters", "l", "liter", "liters",
    "tsp", "teaspoon", "teaspoons", "tbsp", "tablespoon", "tablespoons", "cup", "cups",
    "count", "each", "item", "items", "pc", "pcs", "piece", "pieces",
}


def recipe_text_from_web_result(result: dict[str, Any]) -> str:
    """Build parser-friendly text from the shared web fetch projection.

    HTML extraction commonly flattens page text, while recipe ingredients are
    still available in the fetcher's structured list projection. Prefer a
    bounded list that looks ingredient-like and keep the page text as context.
    """
    title = str(result.get("title") or "Imported recipe").strip()[:200]
    content = str(result.get("content") or "").strip()
    candidates: list[list[str]] = []
    for raw_list in result.get("lists") or []:
        if not isinstance(raw_list, list):
            continue
        lines = [str(value).strip() for value in raw_list if str(value).strip()]
        if len(lines) < 2:
            continue
        score = sum(bool(re.match(r"^(?:[-*•]\s*)?\d", line)) for line in lines)
        if score:
            candidates.append(lines[:MAX_INGREDIENTS])
    ingredients = max(candidates, key=lambda rows: (sum(bool(re.match(r"^\d", row)) for row in rows), len(rows)), default=[])
    if not ingredients:
        return f"{title}\n{content}"
    return f"{title}\n{content}\n\nIngredients:\n" + "\n".join(ingredients)


def _fraction(value: str) -> str:
    value = value.strip()
    if " " in value:
        whole, fraction = value.split(None, 1)
        numerator, denominator = fraction.split("/", 1)
        return str(float(whole) + float(numerator) / float(denominator))
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return str(float(numerator) / float(denominator))
    return value


def _ingredient(line: str) -> dict[str, Any] | None:
    match = _LINE.match(" ".join(line.split()))
    if not match:
        return None
    quantity, possible_unit, name = match.groups()
    if not quantity:
        # Ingredient lines without a quantity are valid count-based recipe
        # requirements, but prose/directions are filtered by section parsing.
        quantity, possible_unit = "1", "each"
    unit = (possible_unit or "each").casefold().rstrip(".")
    if unit not in _UNITS:
        # A word immediately before the ingredient is commonly a package or
        # count descriptor ("1 can tomatoes", "3 cloves garlic"). Do not
        # pretend package sizes are convertible; treat it as one count while
        # retaining the actual ingredient name for stock matching.
        unit = "each"
    try:
        amount = normalize_amount(_fraction(quantity), unit)
    except (UnitError, ValueError):
        return None
    return {"name": name.strip(" ,.;"), "quantity": str(amount.quantity), "unit": amount.unit}


def parse_recipe_text(text: str, *, name: str | None = None) -> dict[str, Any]:
    """Parse common pasted/page/PDF recipe text into a bounded candidate."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("recipe text is required")
    if len(text) > MAX_RECIPE_TEXT:
        raise ValueError(f"recipe text exceeds the {MAX_RECIPE_TEXT} character limit")
    lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
    title = (name or "").strip()
    if not title:
        title = next((line.lstrip("# ") for line in lines if len(line) <= 200 and not _SECTION_START.match(line)), "Imported recipe")
    servings_match = _SERVINGS.search(text)
    servings = servings_match.group(1) if servings_match else "1"
    in_ingredients = False
    ingredients: list[dict[str, Any]] = []
    instructions: list[str] = []
    for line in lines:
        if _SECTION_START.match(line):
            in_ingredients = True
            continue
        if in_ingredients and _SECTION_END.match(line):
            in_ingredients = False
            continue
        if in_ingredients and len(ingredients) < MAX_INGREDIENTS:
            candidate = _ingredient(line)
            if candidate and len(candidate["name"]) <= 200:
                ingredients.append(candidate)
        elif not in_ingredients and _SECTION_END.match(line):
            in_ingredients = False
        elif not in_ingredients and line != title and not _SERVINGS.search(line):
            instructions.append(line)
    if not ingredients:
        # Clipboard copies frequently lose section headings but retain
        # bullets/quantities. Accept only a small run of explicit candidate
        # lines; prose remains instructions and is never silently saved as an
        # ingredient.
        fallback: list[dict[str, Any]] = []
        for line in lines:
            if line == title or _SERVINGS.search(line) or _SECTION_END.match(line):
                continue
            stripped = line.lstrip()
            if not (stripped.startswith(("-", "*", "•")) or re.match(r"^\d", stripped)):
                continue
            candidate = _ingredient(line)
            if candidate and len(candidate["name"]) <= 200 and not re.search(
                r"\b(?:degrees?|minutes?|hours?)\b", candidate["name"], re.I
            ):
                fallback.append(candidate)
        if len(fallback) >= 2:
            ingredients = fallback[:MAX_INGREDIENTS]
    if not ingredients:
        raise ValueError("could not find a bounded Ingredients section or explicit ingredient lines")
    return {
        "name": title[:200], "servings": servings,
        "ingredients": ingredients,
        "instructions": "\n".join(instructions)[:20_000],
    }


def extract_pdf_text(path: str) -> str:
    """Extract text from a managed PDF upload, with a strict page bound."""
    from pypdf import PdfReader

    reader = PdfReader(Path(path))
    pages = []
    for page in reader.pages[:32]:
        pages.append((page.extract_text() or "").strip())
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise ValueError("PDF has no extractable recipe text")
    return text[:MAX_RECIPE_TEXT]
