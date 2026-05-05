from __future__ import annotations

import os

from .exceptions import AdsError
from .provider import AdsProvider

# Cache de instâncias por nome — evita recriar o MockAdsProvider entre chamadas
_registry: dict[str, AdsProvider] = {}


def get_ads_provider(provider_name: str = "mock", **kwargs) -> AdsProvider:
    """
    Retorna o AdsProvider correspondente ao nome informado.

    Providers disponíveis:
        "mock"  — MockAdsProvider (padrão; sem dependências externas)
        "meta"  — MetaAdsProvider (requer META_ACCESS_TOKEN e META_AD_ACCOUNT_ID)

    kwargs para "meta":
        access_token   (str) — sobrescreve a variável de ambiente META_ACCESS_TOKEN
        ad_account_id  (str) — sobrescreve a variável de ambiente META_AD_ACCOUNT_ID

    Exemplo:
        provider = get_ads_provider("mock")
        provider = get_ads_provider("meta", access_token="...", ad_account_id="...")
        provider = get_ads_provider()  # retorna mock por padrão
    """
    if provider_name in _registry:
        return _registry[provider_name]

    provider = _build_provider(provider_name, **kwargs)
    _registry[provider_name] = provider
    return provider


def _build_provider(name: str, **kwargs) -> AdsProvider:
    if name == "mock":
        from .providers.mock_provider import MockAdsProvider
        return MockAdsProvider()

    if name == "meta":
        from .providers.meta_provider import MetaAdsProvider

        access_token = kwargs.get("access_token") or os.getenv("META_ACCESS_TOKEN", "")
        ad_account_id = kwargs.get("ad_account_id") or os.getenv("META_AD_ACCOUNT_ID", "")

        if not access_token or not ad_account_id:
            raise AdsError(
                "MetaAdsProvider requires 'access_token' and 'ad_account_id'. "
                "Pass them as kwargs or set META_ACCESS_TOKEN / META_AD_ACCOUNT_ID env vars.",
                "MISSING_META_CONFIG",
            )
        return MetaAdsProvider(access_token=access_token, ad_account_id=ad_account_id)

    raise AdsError(
        f"Unknown provider: '{name}'. Available: 'mock', 'meta'.",
        "UNKNOWN_PROVIDER",
    )


def clear_registry() -> None:
    """Limpa o cache de instâncias — útil em testes que precisam de providers isolados."""
    _registry.clear()
