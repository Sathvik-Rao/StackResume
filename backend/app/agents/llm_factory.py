from langchain_core.language_models import BaseChatModel
from app.config import settings


def get_llm(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    provider = (provider or settings.llm_provider).lower()
    model = model or settings.llm_model
    temp = settings.llm_temperature

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temp,
            api_key=settings.openai_api_key,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-sonnet-4-6",
            temperature=temp,
            api_key=settings.anthropic_api_key,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.5-flash",
            temperature=temp,
            google_api_key=settings.google_api_key,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model or "llama3.1",
            base_url=settings.ollama_base_url,
            temperature=temp,
            format="json",
        )

    if provider == "custom":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temp,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )

    raise ValueError(f"Unsupported provider: {provider}")
