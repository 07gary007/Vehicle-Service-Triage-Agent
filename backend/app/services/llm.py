from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ..config import get_settings


def get_chat_model():
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.")
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )


def get_embeddings():
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.")
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )
