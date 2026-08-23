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
