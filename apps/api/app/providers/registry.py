from app.models.enums import ProviderName
from app.providers.base import AIProviderAdapter
from app.providers.mock.adapter import MockProviderAdapter


def get_provider_adapter(provider: str) -> AIProviderAdapter:
    return MockProviderAdapter(provider)


def all_provider_adapters() -> list[AIProviderAdapter]:
    return [MockProviderAdapter(provider.value) for provider in ProviderName]
