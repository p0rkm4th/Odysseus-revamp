"""Small, checksum-protected database migration registry.

Odysseus historically creates ORM tables and then runs idempotent startup
helpers.  This registry adds ordering and drift detection for new schema work
without changing that legacy startup contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Callable, Iterable

from sqlalchemy import Column, DateTime, MetaData, String, Table, select
from sqlalchemy.engine import Connection, Engine


MigrationApply = Callable[[Connection], None]


def migration_checksum(definition: str) -> str:
    """Return the stable checksum for a canonical migration definition."""
    if not isinstance(definition, str) or not definition.strip():
        raise ValueError("migration definition must be a non-empty string")
    return hashlib.sha256(definition.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SchemaMigration:
    version: str
    checksum: str
    apply: MigrationApply


class MigrationRegistry:
    """Ordered migration collection with exact-version drift protection."""

    def __init__(self, migrations: Iterable[SchemaMigration] = ()) -> None:
        self._migrations: dict[str, SchemaMigration] = {}
        self._lock = RLock()
        for migration in migrations:
            self.register(migration)

    def register(self, migration: SchemaMigration) -> None:
        if not migration.version or not migration.checksum:
            raise ValueError("migration version and checksum are required")
        with self._lock:
            existing = self._migrations.get(migration.version)
            if existing is not None:
                if existing.checksum != migration.checksum:
                    raise RuntimeError(
                        f"migration {migration.version!r} registered with a different checksum"
                    )
                return
            self._migrations[migration.version] = migration

    def ordered(self) -> tuple[SchemaMigration, ...]:
        with self._lock:
            return tuple(self._migrations[key] for key in sorted(self._migrations))

    def run(self, engine: Engine) -> tuple[str, ...]:
        """Apply pending migrations atomically and return applied versions.

        A recorded version with a different checksum is a startup error.  It
        must never be silently accepted because that would make two databases
        bearing the same version structurally ambiguous.
        """
        applied_now: list[str] = []
        with self._lock, engine.begin() as connection:
            table = _schema_migrations_table()
            table.create(bind=connection, checkfirst=True)
            recorded = {
                row.version: row.checksum
                for row in connection.execute(
                    select(table.c.version, table.c.checksum)
                )
            }
            for migration in self.ordered():
                checksum = recorded.get(migration.version)
                if checksum is not None:
                    if checksum != migration.checksum:
                        raise RuntimeError(
                            f"database migration checksum mismatch for {migration.version!r}"
                        )
                    continue
                migration.apply(connection)
                connection.execute(
                    table.insert().values(
                        version=migration.version,
                        checksum=migration.checksum,
                        applied_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )
                recorded[migration.version] = migration.checksum
                applied_now.append(migration.version)
        return tuple(applied_now)


def _schema_migrations_table() -> Table:
    metadata = MetaData()
    return Table(
        "schema_migrations",
        metadata,
        Column("version", String(128), primary_key=True),
        Column("checksum", String(64), nullable=False),
        Column("applied_at", DateTime, nullable=False),
    )


schema_migration_registry = MigrationRegistry()


def register_schema_migration(migration: SchemaMigration) -> None:
    schema_migration_registry.register(migration)


def run_schema_migrations(engine: Engine) -> tuple[str, ...]:
    return schema_migration_registry.run(engine)
