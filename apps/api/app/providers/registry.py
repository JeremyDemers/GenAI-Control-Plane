from app.core.config import get_settings
from app.models.enums import ProviderName, canonical_provider_value
from app.providers.base import AIProviderAdapter
from app.providers.live.adapter import LiveProviderAdapter
from app.providers.mock.adapter import MockProviderAdapter


def get_provider_adapter(provider: str) -> AIProviderAdapter:
    provider = canonical_provider_value(provider)
    if get_settings().provider_mode == "live":
        return LiveProviderAdapter(provider)
    return MockProviderAdapter(provider)


def all_provider_adapters() -> list[AIProviderAdapter]:
    if get_settings().provider_mode == "live":
        return [LiveProviderAdapter(provider.value) for provider in ProviderName]
    return [MockProviderAdapter(provider.value) for provider in ProviderName]
