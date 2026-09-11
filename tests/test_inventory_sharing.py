"""Explicit household sharing tests for the canonical inventory store."""

import pytest

from core import database as cdb
from core.finance_models import Household, HouseholdMembership
from src.finance_service import FinanceService
from src.inventory_service import InventoryNotFound, get_inventory_service
from tests.helpers.sqlite_db import make_temp_sqlite


def _household(session_factory):
    db = session_factory()
    household = Household(id="household-1", name="Dogfood home", owner="alice")
    household_id = household.id
    db.add(household)
    db.add_all([
        HouseholdMembership(id="membership-a", household_id=household.id, user_id="alice", role="owner"),
        HouseholdMembership(id="membership-b", household_id=household.id, user_id="bob", role="member"),
    ])
    db.commit()
    db.close()
    return household_id


def test_kitchen_sharing_is_explicit_read_only_and_household_scoped():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    household_id = _household(session_factory)
    item = service.create_item(
        "alice", name="Shared milk", domain="kitchen", item_kind="ingredient",
        default_unit="l", storage_area="fridge",
    )
    service.add_stock("alice", item["id"], quantity="2", unit="l", idempotency_key="milk-1")

    assert service.list_items("bob", list_name="fridge") == []
    with pytest.raises(InventoryNotFound):
        service.get_item("bob", item["id"])

    policy = service.configure_sharing(
        "alice", household_id, resource="kitchen_inventory", enabled=True,
    )
    assert policy == {
        "household_id": household_id, "resource": "kitchen_inventory",
        "enabled": True, "allow_member_mutation": False,
    }
    visible = service.list_items("bob", list_name="fridge", include_stock=True)
    # Volume is stored in the canonical millilitre unit; the owner-facing UI
    # uses the item's canonical display unit as well.
    assert [(row["name"], row["stock_quantity"]) for row in visible] == [("Shared milk", "2000.000000")]
    assert service.get_item("bob", item["id"])["owner"] == "alice"
    assert service.household_overview("bob")["items"][0]["name"] == "Shared milk"
    assert service.inventory_history("bob")[0]["movement"]["owner"] == "alice"

    with pytest.raises(InventoryNotFound):
        service.add_stock(
            "bob", item["id"], quantity="1", unit="l", idempotency_key="bob-write",
        )
    service.configure_sharing("alice", household_id, resource="kitchen_inventory", enabled=False)
    assert service.list_items("bob", list_name="fridge") == []


def test_non_member_cannot_read_explicitly_shared_inventory():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    household_id = _household(session_factory)
    item = service.create_item(
        "alice", name="Private pantry", domain="kitchen", item_kind="ingredient",
        storage_area="pantry",
    )
    service.configure_sharing("alice", household_id, resource="kitchen_inventory", enabled=True)

    assert service.list_items("mallory", list_name="pantry") == []
    with pytest.raises(InventoryNotFound):
        service.get_item("mallory", item["id"])


def test_recipe_visibility_and_stock_planning_follow_separate_explicit_policies():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    household_id = _household(session_factory)
    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient", default_unit="kg",
    )
    service.add_stock("alice", rice["id"], quantity="1", unit="kg", idempotency_key="rice-1")
    recipe = service.create_recipe(
        "alice", name="Rice bowl", servings="1",
        ingredients=[{"item_id": rice["id"], "quantity": "0.5", "unit": "kg"}],
    )
    assert service.list_recipes("bob") == []
    service.configure_sharing("alice", household_id, resource="recipes", enabled=True)
    assert [row["name"] for row in service.list_recipes("bob")] == ["Rice bowl"]
    assert service.can_make("bob", recipe["id"]).can_make is False

    service.configure_sharing("alice", household_id, resource="kitchen_inventory", enabled=True)
    assert service.can_make("bob", recipe["id"]).can_make is True


def test_member_edits_require_the_second_explicit_permission_and_reuse_canonical_lots():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    household_id = _household(session_factory)
    item = service.create_item(
        "alice", name="Shared eggs", domain="kitchen", item_kind="ingredient",
        default_unit="each", storage_area="fridge",
    )
    service.configure_sharing("alice", household_id, resource="kitchen_inventory", enabled=True)
    with pytest.raises(InventoryNotFound):
        service.add_stock("bob", item["id"], quantity="1", unit="each", idempotency_key="blocked")

    policy = service.configure_sharing(
        "alice", household_id, resource="kitchen_inventory", enabled=True,
        allow_member_mutation=True,
    )
    assert policy["allow_member_mutation"] is True
    assert service.manage_inventory({"action": "list", "list_name": "fridge"}, owner="bob")["items"][0]["name"] == "Shared eggs"
    assert service.manage_inventory({"action": "add_stock", "name": "Shared eggs", "quantity": "1", "unit": "each", "idempotency_key": "bob-add-tool"}, owner="bob")["lot"]["owner"] == "alice"
    added = service.add_stock(
        "bob", item["id"], quantity="6", unit="each", idempotency_key="bob-add",
    )
    assert added["lot"]["owner"] == "alice"
    consumed = service.consume_stock(
        "bob", item["id"], quantity="2", unit="each", idempotency_key="bob-use",
    )
    assert consumed["quantity"] == 2
    assert service.list_items("alice", list_name="fridge", include_stock=True)[0]["stock_quantity"] == "5.000000"
    service.update_item("bob", item["id"], shopping_list=True)
    assert service.list_items("alice", list_name="grocery")[0]["name"] == "Shared eggs"

    sharing = service.list_sharing("alice")
    assert sharing[0]["members"] == [
        {"user_id": "alice", "role": "owner"},
        {"user_id": "bob", "role": "member"},
    ]
    assert sharing[0]["resources"]["kitchen_inventory"] == {
        "enabled": True, "allow_member_mutation": True,
    }


def test_member_can_cook_shared_recipe_and_consumes_owner_stock_once():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    household_id = _household(session_factory)
    rice = service.create_item(
        "alice", name="Shared rice", domain="kitchen", item_kind="ingredient",
        default_unit="g", storage_area="pantry",
    )
    service.add_stock("alice", rice["id"], quantity=500, unit="g", idempotency_key="shared-rice-stock")
    recipe = service.create_recipe(
        "alice", name="Shared rice bowl", servings=1,
        ingredients=[{"item_id": rice["id"], "quantity": 250, "unit": "g"}],
    )
    service.configure_sharing("alice", household_id, resource="recipes", enabled=True)
    service.configure_sharing(
        "alice", household_id, resource="kitchen_inventory", enabled=True,
        allow_member_mutation=True,
    )

    result = service.cook("bob", recipe["id"], idempotency_key="bob-cook-rice")
    assert result["replayed"] is False
    assert str(service.list_lots("bob", rice["id"])[0]["quantity"]) == "250.000000"

    replay = service.cook("bob", recipe["id"], idempotency_key="bob-cook-rice")
    assert replay["replayed"] is True
    assert str(service.list_lots("alice", rice["id"])[0]["quantity"]) == "250.000000"


def test_owner_can_revoke_member_and_shared_inventory_stays_private_after_reload():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    household_id = _household(session_factory)
    item = service.create_item(
        "alice", name="Revocable milk", domain="kitchen", item_kind="ingredient",
        default_unit="l", storage_area="fridge",
    )
    service.configure_sharing("alice", household_id, resource="kitchen_inventory", enabled=True)
    assert service.list_items("bob", list_name="fridge")

    db = session_factory()
    try:
        FinanceService(db).remove_member("alice", household_id, "bob")
    finally:
        db.close()

    reloaded = get_inventory_service(session_factory)
    assert reloaded.list_items("bob", list_name="fridge") == []
    with pytest.raises(InventoryNotFound):
        reloaded.get_item("bob", item["id"])
