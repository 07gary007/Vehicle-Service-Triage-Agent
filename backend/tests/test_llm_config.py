import pytest
from app.config import Settings
from app.services.llm import _azure_auth_kwargs, model_identifier, validate_model_config


def test_openai_model_identifier_is_explicit():
    settings = Settings(model_provider="openai", openai_model="gpt-test")
    assert model_identifier(settings) == "openai/gpt-test"


def test_azure_model_identifier_uses_deployment_name():
    settings = Settings(
        model_provider="azure_openai",
        azure_openai_chat_deployment="triage-chat",
        azure_openai_chat_model="gpt-4o-mini",
    )
    assert model_identifier(settings) == "azure_openai/triage-chat"


def test_azure_provider_requires_credentials():
    settings = Settings(
        model_provider="azure_openai",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_use_managed_identity=False,
        azure_openai_api_key="",
    )
    with pytest.raises(RuntimeError, match="credentials are missing"):
        _azure_auth_kwargs(settings)


def test_azure_provider_requires_chat_and_embedding_deployments():
    settings = Settings(
        model_provider="azure_openai",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="test-key",
    )
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_CHAT_DEPLOYMENT"):
        validate_model_config(settings)
