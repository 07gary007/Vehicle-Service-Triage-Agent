from __future__ import annotations

from typing import Any

from langchain_openai import (
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    ChatOpenAI,
    OpenAIEmbeddings,
)

from ..config import get_settings


def _provider(settings) -> str:
    provider = settings.model_provider.strip().lower()
    if provider in {"azure", "azure-openai", "azure_openai"}:
        return "azure_openai"
    if provider == "openai":
        return provider
    raise RuntimeError(
        "Unsupported MODEL_PROVIDER. Use 'openai' or 'azure_openai'."
    )


def model_identifier(settings=None) -> str:
    """Return the provider/deployment recorded on a triage run."""
    settings = settings or get_settings()
    provider = _provider(settings)
    if provider == "openai":
        return f"openai/{settings.openai_model}"
    deployment = settings.azure_openai_chat_deployment.strip()
    return f"azure_openai/{deployment or settings.azure_openai_chat_model}"


def _azure_auth_kwargs(settings) -> dict[str, Any]:
    if settings.azure_openai_api_key.strip():
        return {"api_key": settings.azure_openai_api_key}

    if settings.azure_openai_use_managed_identity:
        try:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        except ImportError as exc:
            raise RuntimeError(
                "azure-identity is required when AZURE_OPENAI_USE_MANAGED_IDENTITY=true."
            ) from exc

        credential = DefaultAzureCredential()
        return {
            "azure_ad_token_provider": get_bearer_token_provider(
                credential,
                "https://cognitiveservices.azure.com/.default",
            )
        }

    raise RuntimeError(
        "Azure OpenAI credentials are missing. Set AZURE_OPENAI_API_KEY for local use "
        "or enable AZURE_OPENAI_USE_MANAGED_IDENTITY in a cloud workload."
    )


def _require_azure_settings(settings) -> None:
    missing = []
    if not settings.azure_openai_endpoint.strip():
        missing.append("AZURE_OPENAI_ENDPOINT")
    if not settings.azure_openai_api_version.strip():
        missing.append("AZURE_OPENAI_API_VERSION")
    if missing:
        raise RuntimeError(f"Azure OpenAI settings are missing: {', '.join(missing)}")


def validate_model_config(settings=None) -> None:
    """Validate provider configuration without making a network call."""
    settings = settings or get_settings()
    provider = _provider(settings)
    if provider == "openai":
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.")
        return

    _require_azure_settings(settings)
    missing = []
    if not settings.azure_openai_chat_deployment.strip():
        missing.append("AZURE_OPENAI_CHAT_DEPLOYMENT")
    if not settings.azure_openai_embedding_deployment.strip():
        missing.append("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    if not settings.azure_openai_api_key.strip() and not settings.azure_openai_use_managed_identity:
        missing.append("AZURE_OPENAI_API_KEY or AZURE_OPENAI_USE_MANAGED_IDENTITY")
    if missing:
        raise RuntimeError(f"Azure OpenAI settings are missing: {', '.join(missing)}")


def get_chat_model():
    settings = get_settings()
    provider = _provider(settings)
    if provider == "openai":
        validate_model_config(settings)
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            use_responses_api=settings.openai_use_responses_api,
        )

    validate_model_config(settings)
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_chat_deployment,
        api_version=settings.azure_openai_api_version,
        model=settings.azure_openai_chat_model or settings.azure_openai_chat_deployment,
        use_responses_api=settings.azure_openai_use_responses_api,
        **_azure_auth_kwargs(settings),
    )


def get_embeddings():
    settings = get_settings()
    provider = _provider(settings)
    if provider == "openai":
        validate_model_config(settings)
        return OpenAIEmbeddings(model=settings.openai_embedding_model, api_key=settings.openai_api_key)

    validate_model_config(settings)
    return AzureOpenAIEmbeddings(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_embedding_deployment,
        model=settings.azure_openai_embedding_model,
        api_version=settings.azure_openai_api_version,
        **_azure_auth_kwargs(settings),
    )
