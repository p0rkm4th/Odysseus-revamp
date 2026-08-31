"""Bounded owner-language field extraction for Household inventory Actions."""

from __future__ import annotations

import re
from typing import Any


def inventory_add_item_payload(query: str) -> dict[str, Any] | None:
    text = str(query or "").strip()
    location_match = re.search(
        r"\s+(?:to|in)\s+(?:(?:my|the)\s+)?"
        r"(?P<area>pantry|refrigerator|fridge|freezer|cabinet|kitchen)\s*\.?$",
        text, re.IGNORECASE,
    )
    area = location_match.group("area") if location_match else None
    item_text = text[:location_match.start()] if location_match else text
    match = re.search(
        r"\badd\s+(?P<quantity>\d+(?:\.\d+)?)\s+(?P<name>.+?)\s*\.?$",
        item_text, re.IGNORECASE,
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
    return {"action": "add_item", "name": name[:200], "domain": "kitchen",
            "item_kind": "ingredient", "default_unit": "each",
            "initial_quantity": float(match.group("quantity")), "initial_unit": "each",
            "category": (area or "").casefold() or None,
            "location_name": (area or "").casefold() or None}

def inventory_consume_stock_payload(query: str, *, item_reference: str | None = None) -> dict[str, Any] | None:
    text = str(query or "").strip()
    match = re.search(
        r"\b(?:use|consume|used|consumed)\s+"
        r"(?:(?P<quantity>\d+(?:\.\d+)?)|(?P<word>one|a|an|two|three|four|five))"
        r"(?:\s+(?P<name>.+?))?\s*[.!?]*$", text, re.IGNORECASE,
    )
    if not match:
        return None
    word_quantities = {"one": 1.0, "a": 1.0, "an": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0}
    quantity = float(match.group("quantity")) if match.group("quantity") else word_quantities[match.group("word").casefold()]
    name = re.sub(
        r"\s+from\s+(?:the\s+)?(?:pantry|kitchen|freezer|refrigerator|fridge)\s*$",
        "", match.group("name") or "", flags=re.IGNORECASE,
    )
    name = re.sub(r"\s+", " ", name).strip(" .\"'")
    if (not name and not item_reference) or quantity <= 0:
        return None
    payload: dict[str, Any] = {"action": "consume_stock", "quantity": quantity, "unit": "each"}
    if name:
        payload["item_name"] = name[:200]
    if item_reference:
        payload["item_id"] = str(item_reference).strip()
    return payload

def inventory_move_item_payload(query: str, *, item_reference: str | None = None) -> dict[str, Any] | None:
    text = str(query or "").strip()
    match = re.search(
        r"\bmove\s+(?:(?P<name>.+?)\s+)?to\s+(?:the\s+)?"
        r"(?P<location>pantry|freezer|refrigerator|fridge|cabinet|kitchen)\s*[.!?]*$",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    name = re.sub(r"\s+", " ", match.group("name") or "").strip(" .\"'")
    if name.casefold() in {"it", "that", "this", "them", "those", "these"}:
        name = ""
    if not name and not item_reference:
        return None
    payload: dict[str, Any] = {"action": "move_item", "location_name": match.group("location").casefold()}
    if name:
        payload["item_name"] = name[:200]
    if item_reference:
        payload["item_id"] = str(item_reference).strip()
    return payload
