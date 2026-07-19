"""update google provider names

Revision ID: e4a1c9b2d3f0
Revises: d8f2b7c1a901
Create Date: 2026-07-19 10:00:00.000000
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "e4a1c9b2d3f0"
down_revision: str | None = "d8f2b7c1a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_VALUE_UPGRADE = {
    "google_gemini_enterprise": "google_gemini_enterprise_app",
    "google_vertex_ai": "google_gemini_enterprise_agent_platform",
}
PROVIDER_VALUE_DOWNGRADE = {value: key for key, value in PROVIDER_VALUE_UPGRADE.items()}

PROVIDER_ENUM_UPGRADE = {
    "GOOGLE_GEMINI": "GOOGLE_GEMINI_ENTERPRISE_APP",
    "GOOGLE_VERTEX": "GOOGLE_GEMINI_AGENT_PLATFORM",
}
PROVIDER_ENUM_DOWNGRADE = {value: key for key, value in PROVIDER_ENUM_UPGRADE.items()}

STRING_PROVIDER_TABLES = (
    "provider_assignments",
    "provider_resources",
    "usage_records",
    "cost_records",
    "audit_events",
    "integration_credentials",
    "provider_health_checks",
)

JSON_COLUMNS = (
    ("access_requests", "provider_names"),
    ("lifecycle_jobs", "payload"),
    ("lifecycle_jobs", "failure_information"),
    ("provider_resources", "metadata_json"),
    ("provider_health_checks", "details"),
    ("audit_events", "metadata_json"),
    ("incidents", "metadata_json"),
)


def upgrade() -> None:
    _add_postgresql_provider_enum_values(
        ("GOOGLE_GEMINI_ENTERPRISE_APP", "GOOGLE_GEMINI_AGENT_PLATFORM")
    )
    _migrate_request_service_provider(PROVIDER_ENUM_UPGRADE)
    _migrate_string_provider_columns(PROVIDER_VALUE_UPGRADE)
    _migrate_json_columns(PROVIDER_VALUE_UPGRADE)
    _migrate_lifecycle_idempotency_keys(PROVIDER_VALUE_UPGRADE)


def downgrade() -> None:
    _migrate_request_service_provider(PROVIDER_ENUM_DOWNGRADE)
    _migrate_string_provider_columns(PROVIDER_VALUE_DOWNGRADE)
    _migrate_json_columns(PROVIDER_VALUE_DOWNGRADE)
    _migrate_lifecycle_idempotency_keys(PROVIDER_VALUE_DOWNGRADE)


def _add_postgresql_provider_enum_values(values: tuple[str, ...]) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    with op.get_context().autocommit_block():
        for value in values:
            op.execute(f"ALTER TYPE providername ADD VALUE IF NOT EXISTS '{value}'")


def _migrate_request_service_provider(mapping: dict[str, str]) -> None:
    connection = op.get_bind()
    for old, new in mapping.items():
        connection.execute(
            sa.text("UPDATE request_services SET provider = :new WHERE provider = :old"),
            {"old": old, "new": new},
        )


def _migrate_string_provider_columns(mapping: dict[str, str]) -> None:
    connection = op.get_bind()
    for table_name in STRING_PROVIDER_TABLES:
        table = sa.table(
            table_name,
            sa.column("provider", sa.String()),
        )
        for old, new in mapping.items():
            connection.execute(
                table.update().where(table.c.provider == old).values(provider=new)
            )


def _migrate_json_columns(mapping: dict[str, str]) -> None:
    connection = op.get_bind()
    for table_name, column_name in JSON_COLUMNS:
        table = sa.table(
            table_name,
            sa.column("id", sa.String()),
            sa.column(column_name, sa.JSON()),
        )
        rows = connection.execute(
            sa.select(table.c.id, table.c[column_name])
        ).mappings()
        for row in rows:
            original = row[column_name]
            updated = _replace_provider_values(original, mapping)
            if updated == original:
                continue
            connection.execute(
                table.update()
                .where(table.c.id == row["id"])
                .values({column_name: updated})
            )


def _migrate_lifecycle_idempotency_keys(mapping: dict[str, str]) -> None:
    connection = op.get_bind()
    table = sa.table(
        "lifecycle_jobs",
        sa.column("id", sa.String()),
        sa.column("idempotency_key", sa.String()),
    )
    rows = connection.execute(
        sa.select(table.c.id, table.c.idempotency_key)
    ).mappings()
    for row in rows:
        updated = row["idempotency_key"]
        for old, new in mapping.items():
            updated = updated.replace(old, new)
        if updated == row["idempotency_key"]:
            continue
        connection.execute(
            table.update()
            .where(table.c.id == row["id"])
            .values(idempotency_key=updated)
        )


def _replace_provider_values(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_replace_provider_values(item, mapping) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_provider_values(item, mapping)
            for key, item in value.items()
        }
    return value
