"""Owner-scoped persistence models for inventory, assets, and recipes."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)

from core.database import Base, TimestampMixin, utcnow_naive


QUANTITY_TYPE = Numeric(18, 6)
MONEY_TYPE = Numeric(18, 4)


class InventoryLocation(TimestampMixin, Base):
    __tablename__ = "inventory_locations"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=False)
    # A materialized normalized path gives root and nested locations the same
    # portable uniqueness rule. SQL UNIQUE treats NULL parent_id values as
    # distinct, so (owner, parent_id, name) alone cannot protect root names.
    normalized_path = Column(String, nullable=False)
    parent_id = Column(
        String,
        ForeignKey("inventory_locations.id", ondelete="CASCADE"),
        nullable=True,
    )
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "owner", "normalized_path",
            name="uq_inventory_location_owner_path",
        ),
        Index("ix_inventory_locations_owner_parent", "owner", "parent_id"),
    )


class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False)
    item_kind = Column(String, nullable=False)
    name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    brand = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    model = Column(String, nullable=True)
    sku = Column(String, nullable=True)
    barcode = Column(String, nullable=True)
    default_unit = Column(String, nullable=False, default="each")
    reorder_point = Column(QUANTITY_TYPE, nullable=True)
    location_id = Column(
        String,
        ForeignKey("inventory_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json = Column(JSON, nullable=False, default=dict)
    image_refs_json = Column(JSON, nullable=False, default=list)
    archived = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "domain IN ('it', 'kitchen', 'household')",
            name="ck_inventory_items_domain",
        ),
        CheckConstraint(
            "item_kind IN ('asset', 'consumable', 'ingredient')",
            name="ck_inventory_items_kind",
        ),
        CheckConstraint(
            "reorder_point IS NULL OR reorder_point >= 0",
            name="ck_inventory_items_reorder_nonnegative",
        ),
        Index(
            "ix_inventory_items_owner_domain_active_name",
            "owner", "domain", "archived", "normalized_name",
        ),
        Index("ix_inventory_items_owner_barcode", "owner", "barcode"),
        Index("ix_inventory_items_owner_model", "owner", "model"),
    )


class InventoryAssetDetail(TimestampMixin, Base):
    __tablename__ = "inventory_asset_details"

    item_id = Column(
        String,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    owner = Column(String, nullable=False, index=True)
    serial_number = Column(String, nullable=True)
    asset_tag = Column(String, nullable=True)
    status = Column(String, nullable=False, default="in_stock")
    condition = Column(String, nullable=True)
    acquired_at = Column(Date, nullable=True)
    purchase_price = Column(MONEY_TYPE, nullable=True)
    currency = Column(String(3), nullable=True)
    warranty_expires_at = Column(Date, nullable=True)
    hostname = Column(String, nullable=True)
    mac_addresses_json = Column(JSON, nullable=False, default=list)
    ip_addresses_json = Column(JSON, nullable=False, default=list)
    specs_json = Column(JSON, nullable=False, default=dict)
    assigned_to = Column(String, nullable=True)
    parent_asset_id = Column(
        String,
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_stock', 'deployed', 'repair', 'retired', 'disposed', 'lost')",
            name="ck_inventory_asset_status",
        ),
        CheckConstraint(
            "purchase_price IS NULL OR purchase_price >= 0",
            name="ck_inventory_asset_price_nonnegative",
        ),
        UniqueConstraint("owner", "asset_tag", name="uq_inventory_asset_owner_tag"),
        UniqueConstraint("owner", "serial_number", name="uq_inventory_asset_owner_serial"),
    )


class InventoryLot(TimestampMixin, Base):
    __tablename__ = "inventory_lots"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    item_id = Column(
        String,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id = Column(
        String,
        ForeignKey("inventory_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    quantity = Column(QUANTITY_TYPE, nullable=False, default=0)
    unit = Column(String, nullable=False)
    expiry_date = Column(Date, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    purchase_date = Column(Date, nullable=True)
    unit_cost = Column(MONEY_TYPE, nullable=True)
    currency = Column(String(3), nullable=True)
    lot_code = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_lot_quantity_nonnegative"),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_inventory_lot_cost_nonnegative",
        ),
        Index("ix_inventory_lots_owner_item_expiry", "owner", "item_id", "expiry_date"),
        Index("ix_inventory_lots_owner_location", "owner", "location_id"),
    )


class InventoryMovement(Base):
    """Append-only stock ledger; corrections are compensating movements."""

    __tablename__ = "inventory_movements"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    item_id = Column(
        String,
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lot_id = Column(
        String,
        ForeignKey("inventory_lots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    quantity_delta = Column(QUANTITY_TYPE, nullable=False)
    unit = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    source_kind = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    idempotency_key = Column(String, nullable=False)
    actor = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=utcnow_naive)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)

    __table_args__ = (
        CheckConstraint("quantity_delta != 0", name="ck_inventory_movement_nonzero"),
        CheckConstraint(
            "reason IN ('add', 'consume', 'adjust', 'move_in', 'move_out', 'recipe', 'dispose', 'return')",
            name="ck_inventory_movement_reason",
        ),
        UniqueConstraint(
            "owner", "idempotency_key",
            name="uq_inventory_movement_owner_idempotency",
        ),
        Index("ix_inventory_movements_owner_item_time", "owner", "item_id", "occurred_at"),
    )


def _reject_ledger_mutation(_mapper, _connection, _target) -> None:
    raise ValueError("inventory movements are immutable; append a correction")


event.listen(InventoryMovement, "before_update", _reject_ledger_mutation)
event.listen(InventoryMovement, "before_delete", _reject_ledger_mutation)


class InventoryRecipe(TimestampMixin, Base):
    __tablename__ = "inventory_recipes"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=False)
    instructions = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=True)
    servings = Column(QUANTITY_TYPE, nullable=False, default=1)
    source_url = Column(Text, nullable=True)
    tags_json = Column(JSON, nullable=False, default=list)
    image_refs_json = Column(JSON, nullable=False, default=list)
    archived = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("servings > 0", name="ck_inventory_recipe_servings_positive"),
        Index(
            "ix_inventory_recipes_owner_active_name",
            "owner", "archived", "normalized_name",
        ),
    )


class InventoryRecipeIngredient(Base):
    __tablename__ = "inventory_recipe_ingredients"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    recipe_id = Column(
        String,
        ForeignKey("inventory_recipes.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id = Column(
        String,
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    ingredient_name = Column(String, nullable=False)
    quantity = Column(QUANTITY_TYPE, nullable=True)
    unit = Column(String, nullable=True)
    amount_kind = Column(String, nullable=False, default="EXACT")
    quantity_min = Column(QUANTITY_TYPE, nullable=True)
    quantity_max = Column(QUANTITY_TYPE, nullable=True)
    modifier = Column(String, nullable=True)
    source_text = Column(Text, nullable=True)
    optional = Column(Boolean, nullable=False, default=False)
    substitution_group = Column(String, nullable=True)
    preparation = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inventory_recipe_ingredient_quantity_positive"),
        Index("ix_inventory_recipe_ingredients_owner_recipe", "owner", "recipe_id", "sort_order"),
    )


class InventoryRecipeCook(Base):
    __tablename__ = "inventory_recipe_cooks"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    recipe_id = Column(
        String,
        ForeignKey("inventory_recipes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    servings = Column(QUANTITY_TYPE, nullable=False)
    idempotency_key = Column(String, nullable=False)
    status = Column(String, nullable=False, default="completed")
    movement_ids_json = Column(JSON, nullable=False, default=list)
    cooked_at = Column(DateTime, nullable=False, default=utcnow_naive)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)

    __table_args__ = (
        CheckConstraint("servings > 0", name="ck_inventory_recipe_cook_servings_positive"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'reversed')",
            name="ck_inventory_recipe_cook_status",
        ),
        UniqueConstraint(
            "owner", "idempotency_key",
            name="uq_inventory_recipe_cook_owner_idempotency",
        ),
        Index("ix_inventory_recipe_cooks_owner_recipe_time", "owner", "recipe_id", "cooked_at"),
    )


class InventoryDraft(TimestampMixin, Base):
    """Unconfirmed natural-language/photo/voice import candidate."""

    __tablename__ = "inventory_drafts"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)
    source_ref = Column(String, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    confidence_json = Column(JSON, nullable=False, default=dict)
    image_refs_json = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="pending")
    applied_item_id = Column(
        String,
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('natural_language', 'photo', 'voice', 'telegram', 'import', 'network_discovery')",
            name="ck_inventory_draft_source_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'applied')",
            name="ck_inventory_draft_status",
        ),
        UniqueConstraint(
            "owner", "idempotency_key",
            name="uq_inventory_draft_owner_idempotency",
        ),
        Index("ix_inventory_drafts_owner_status_time", "owner", "status", "created_at"),
    )


INVENTORY_TABLES = (
    InventoryLocation.__table__,
    InventoryItem.__table__,
    InventoryAssetDetail.__table__,
    InventoryLot.__table__,
    InventoryMovement.__table__,
    InventoryRecipe.__table__,
    InventoryRecipeIngredient.__table__,
    InventoryRecipeCook.__table__,
    InventoryDraft.__table__,
)
