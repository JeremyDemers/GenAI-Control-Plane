import importlib.util
from pathlib import Path
from types import ModuleType


def load_google_provider_migration() -> ModuleType:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "e4a1c9b2d3f0_update_google_provider_names.py"
    )
    spec = importlib.util.spec_from_file_location("google_provider_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_google_provider_migration_rewrites_nested_legacy_values() -> None:
    migration = load_google_provider_migration()

    updated = migration._replace_provider_values(
        {
            "provider": "google_vertex_ai",
            "providers": ["google_gemini_enterprise", "amazon_bedrock"],
            "nested": {"provider": "google_vertex_ai"},
        },
        migration.PROVIDER_VALUE_UPGRADE,
    )

    assert updated == {
        "provider": "google_gemini_enterprise_agent_platform",
        "providers": ["google_gemini_enterprise_app", "amazon_bedrock"],
        "nested": {"provider": "google_gemini_enterprise_agent_platform"},
    }
