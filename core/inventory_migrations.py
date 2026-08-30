"""Versioned migrations for the inventory persistence domain."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, MetaData, PrimaryKeyConstraint, String, Table, UniqueConstraint, inspect, select, text
from sqlalchemy.engine import Connection

from core.inventory_models import INVENTORY_TABLES
from core.schema_migrations import (
    SchemaMigration,
    migration_checksum,
    register_schema_migration,
)


INVENTORY_V1_VERSION = "20260822_001_inventory_v1"
INVENTORY_V1_DEFINITION = """inventory-v1
inventory_locations
inventory_locations:owner-normalized-path-unique
inventory_items
inventory_asset_details
inventory_lots
inventory_movements:append-only
inventory_recipes
inventory_recipe_ingredients
inventory_recipe_cooks
inventory_drafts
owner-scoped:numeric-18-6:idempotent
"""
INVENTORY_V1_CHECKSUM = migration_checksum(INVENTORY_V1_DEFINITION)

INVENTORY_V2_VERSION = "20260823_002_inventory_network_discovery"
INVENTORY_V2_DEFINITION = "inventory-v2\ninventory_drafts:network_discovery-source-type\n"
INVENTORY_V2_CHECKSUM = migration_checksum(INVENTORY_V2_DEFINITION)

INVENTORY_V3_VERSION = "20260830_003_recipe_qualitative_amounts"
INVENTORY_V3_DEFINITION = """inventory-v3
inventory_recipe_ingredients:truthful-qualitative-range-amounts
quantity-nullable-unit-nullable-amount-kind-min-max-modifier-source-text
"""
INVENTORY_V3_CHECKSUM = migration_checksum(INVENTORY_V3_DEFINITION)


def apply_inventory_v1(connection: Connection) -> None:
    for table in INVENTORY_TABLES:
        table.create(bind=connection, checkfirst=True)

    inspector = inspect(connection)
    missing = [table.name for table in INVENTORY_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError(f"inventory v1 migration did not create tables: {', '.join(missing)}")


register_schema_migration(
    SchemaMigration(
        version=INVENTORY_V1_VERSION,
        checksum=INVENTORY_V1_CHECKSUM,
        apply=apply_inventory_v1,
    )
)


def apply_inventory_v3(connection: Connection) -> None:
    """Add truthful culinary amount semantics without rewriting recipe rows."""
    inspector = inspect(connection)
    if not inspector.has_table("inventory_recipe_ingredients"):
        return
    existing = {column["name"] for column in inspector.get_columns("inventory_recipe_ingredients")}
    old = Table("inventory_recipe_ingredients", MetaData(), autoload_with=connection)
    # V1 made quantity/unit NOT NULL. SQLite cannot loosen that constraint
    # with ALTER TABLE, so rebuild only that table before adding the semantic
    # nullable fields. Rows and their stable IDs are copied unchanged.
    if old.c.quantity.nullable is False or old.c.unit.nullable is False:
        rebuilt_metadata = MetaData()
        # Foreign-key targets must be present in this metadata collection for
        # SQLAlchemy to emit the rebuilt SQLite table.
        Table("inventory_recipes", rebuilt_metadata, autoload_with=connection)
        Table("inventory_items", rebuilt_metadata, autoload_with=connection)
        rebuilt = Table(
            "inventory_recipe_ingredients_v3", rebuilt_metadata,
            Column("id", old.c.id.type, primary_key=True, nullable=False),
            Column("owner", old.c.owner.type, nullable=False),
            Column("recipe_id", old.c.recipe_id.type, ForeignKey("inventory_recipes.id", ondelete="CASCADE"), nullable=False),
            Column("item_id", old.c.item_id.type, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True),
            Column("ingredient_name", old.c.ingredient_name.type, nullable=False),
            Column("quantity", old.c.quantity.type, nullable=True),
            Column("unit", old.c.unit.type, nullable=True),
            Column("amount_kind", String, nullable=False, default="EXACT"),
            Column("quantity_min", old.c.quantity.type, nullable=True),
            Column("quantity_max", old.c.quantity.type, nullable=True),
            Column("modifier", String, nullable=True),
            Column("source_text", old.c.ingredient_name.type, nullable=True),
            Column("optional", old.c.optional.type, nullable=False, default=False),
            Column("substitution_group", old.c.substitution_group.type, nullable=True),
            Column("preparation", old.c.preparation.type, nullable=True),
            Column("sort_order", old.c.sort_order.type, nullable=False, default=0),
            CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_inventory_recipe_ingredient_quantity_positive"),
        )
        rebuilt.create(connection)
        connection.exec_driver_sql(
            "INSERT INTO inventory_recipe_ingredients_v3 "
            "(id, owner, recipe_id, item_id, ingredient_name, quantity, unit, amount_kind, "
            "quantity_min, quantity_max, modifier, source_text, optional, substitution_group, "
            "preparation, sort_order) "
            "SELECT id, owner, recipe_id, item_id, ingredient_name, quantity, unit, 'EXACT', "
            "NULL, NULL, NULL, ingredient_name, optional, substitution_group, preparation, "
            "sort_order FROM inventory_recipe_ingredients"
        )
        connection.exec_driver_sql("DROP TABLE inventory_recipe_ingredients")
        connection.exec_driver_sql(
            "ALTER TABLE inventory_recipe_ingredients_v3 RENAME TO inventory_recipe_ingredients"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_inventory_recipe_ingredients_owner_recipe "
            "ON inventory_recipe_ingredients (owner, recipe_id, sort_order)"
        )
        existing = {column["name"] for column in inspect(connection).get_columns("inventory_recipe_ingredients")}
    additions = {
        "quantity": "NUMERIC(18, 6)", "unit": "VARCHAR",
        "amount_kind": "VARCHAR NOT NULL DEFAULT 'EXACT'",
        "quantity_min": "NUMERIC(18, 6)", "quantity_max": "NUMERIC(18, 6)",
        "modifier": "VARCHAR", "source_text": "TEXT",
    }
    for name, definition in additions.items():
        if name not in existing:
            connection.exec_driver_sql(
                f"ALTER TABLE inventory_recipe_ingredients ADD COLUMN {name} {definition}"
            )
    connection.exec_driver_sql(
        "UPDATE inventory_recipe_ingredients SET amount_kind = 'EXACT' "
        "WHERE amount_kind IS NULL OR amount_kind = ''"
    )


register_schema_migration(SchemaMigration(
    version=INVENTORY_V3_VERSION, checksum=INVENTORY_V3_CHECKSUM,
    apply=apply_inventory_v3,
))


INVENTORY_V4_VERSION = "20260830_004_recipe_qualitative_schema_cleanup"
INVENTORY_V4_DEFINITION = "inventory-v4\nremove-accidental-recipe-ingredient-timestamps\npreserve-v3-semantics\n"
INVENTORY_V4_CHECKSUM = migration_checksum(INVENTORY_V4_DEFINITION)


def apply_inventory_v4(connection: Connection) -> None:
    """Remove timestamp columns accidentally introduced by the first v3 build.

    The mapped ingredient owner intentionally has no timestamp fields.  This
    forward migration is needed for databases that briefly ran that candidate
    before the v3 migration was corrected.
    """
    inspector = inspect(connection)
    if not inspector.has_table("inventory_recipe_ingredients"):
        return
    columns = {column["name"] for column in inspector.get_columns("inventory_recipe_ingredients")}
    if not {"created_at", "updated_at"}.intersection(columns):
        return
    metadata = MetaData()
    old = Table("inventory_recipe_ingredients", metadata, autoload_with=connection)
    rebuilt_metadata = MetaData()
    Table("inventory_recipes", rebuilt_metadata, autoload_with=connection)
    Table("inventory_items", rebuilt_metadata, autoload_with=connection)
    rebuilt = Table(
        "inventory_recipe_ingredients_v4", rebuilt_metadata,
        Column("id", old.c.id.type, primary_key=True, nullable=False),
        Column("owner", old.c.owner.type, nullable=False),
        Column("recipe_id", old.c.recipe_id.type, ForeignKey("inventory_recipes.id", ondelete="CASCADE"), nullable=False),
        Column("item_id", old.c.item_id.type, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True),
        Column("ingredient_name", old.c.ingredient_name.type, nullable=False),
        Column("quantity", old.c.quantity.type, nullable=True),
        Column("unit", old.c.unit.type, nullable=True),
        Column("amount_kind", String, nullable=False, default="EXACT"),
        Column("quantity_min", old.c.quantity.type, nullable=True),
        Column("quantity_max", old.c.quantity.type, nullable=True),
        Column("modifier", String, nullable=True),
        Column("source_text", old.c.source_text.type, nullable=True),
        Column("optional", old.c.optional.type, nullable=False, default=False),
        Column("substitution_group", old.c.substitution_group.type, nullable=True),
        Column("preparation", old.c.preparation.type, nullable=True),
        Column("sort_order", old.c.sort_order.type, nullable=False, default=0),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_inventory_recipe_ingredient_quantity_positive"),
    )
    rebuilt.create(connection)
    connection.exec_driver_sql(
        "INSERT INTO inventory_recipe_ingredients_v4 "
        "(id, owner, recipe_id, item_id, ingredient_name, quantity, unit, amount_kind, "
        "quantity_min, quantity_max, modifier, source_text, optional, substitution_group, "
        "preparation, sort_order) SELECT id, owner, recipe_id, item_id, ingredient_name, "
        "quantity, unit, amount_kind, quantity_min, quantity_max, modifier, source_text, "
        "optional, substitution_group, preparation, sort_order "
        "FROM inventory_recipe_ingredients"
    )
    connection.exec_driver_sql("DROP TABLE inventory_recipe_ingredients")
    connection.exec_driver_sql("ALTER TABLE inventory_recipe_ingredients_v4 RENAME TO inventory_recipe_ingredients")
    connection.exec_driver_sql(
        "CREATE INDEX ix_inventory_recipe_ingredients_owner_recipe "
        "ON inventory_recipe_ingredients (owner, recipe_id, sort_order)"
    )


register_schema_migration(SchemaMigration(
    version=INVENTORY_V4_VERSION, checksum=INVENTORY_V4_CHECKSUM,
    apply=apply_inventory_v4,
))


def apply_inventory_v2(connection: Connection) -> None:
    """Allow persisted review drafts produced by bounded network discovery.

    SQLite cannot alter a CHECK constraint in place, so rebuild only the
    drafts table while preserving all rows and its owner/idempotency indexes.
    Other engines can use a direct constraint update where supported.
    """
    if connection.dialect.name != "sqlite":
        return
    inspector = inspect(connection)
    if not inspector.has_table("inventory_drafts"):
        return
    metadata = MetaData()
    old = Table("inventory_drafts", metadata, autoload_with=connection)
    rebuilt_metadata = MetaData()
    Table("inventory_items", rebuilt_metadata, autoload_with=connection)
    rebuilt = Table(
        "inventory_drafts_v2", rebuilt_metadata,
        Column("id", String, primary_key=True, nullable=False),
        Column("owner", String, nullable=False),
        Column("source_type", String, nullable=False),
        Column("source_ref", String),
        Column("payload_json", old.c.payload_json.type, nullable=False),
        Column("confidence_json", old.c.confidence_json.type, nullable=False),
        Column("image_refs_json", old.c.image_refs_json.type, nullable=False),
        Column("status", String, nullable=False),
        Column("applied_item_id", String, ForeignKey("inventory_items.id", ondelete="SET NULL")),
        Column("idempotency_key", String, nullable=False),
        Column("created_at", old.c.created_at.type, nullable=False),
        Column("updated_at", old.c.updated_at.type, nullable=False),
        CheckConstraint(
            "source_type IN ('natural_language', 'photo', 'voice', 'telegram', 'import', 'network_discovery')",
            name="ck_inventory_draft_source_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'applied')",
            name="ck_inventory_draft_status",
        ),
        UniqueConstraint("owner", "idempotency_key", name="uq_inventory_draft_owner_idempotency"),
    )
    rebuilt.create(connection)
    columns = [
        "id", "owner", "source_type", "source_ref", "payload_json",
        "confidence_json", "image_refs_json", "status", "applied_item_id",
        "idempotency_key", "created_at", "updated_at",
    ]
    connection.execute(
        rebuilt.insert().from_select(columns, select(*(old.c[name] for name in columns)))
    )
    connection.execute(text("DROP TABLE inventory_drafts"))
    connection.execute(text("ALTER TABLE inventory_drafts_v2 RENAME TO inventory_drafts"))
    connection.execute(text(
        "CREATE INDEX ix_inventory_drafts_owner_status_time "
        "ON inventory_drafts (owner, status, created_at)"
    ))


register_schema_migration(
    SchemaMigration(
        version=INVENTORY_V2_VERSION,
        checksum=INVENTORY_V2_CHECKSUM,
        apply=apply_inventory_v2,
    )
)
