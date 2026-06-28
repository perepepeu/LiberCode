# libercode/providers/registry.py
"""Central registry of all available providers."""
from __future__ import annotations
import os
from typing import Type
from libercode.providers.base import BaseProvider

from libercode.providers.openai_provider    import OpenAIProvider
from libercode.providers.anthropic_provider import AnthropicProvider
from libercode.providers.google_provider    import GoogleProvider
from libercode.providers.groq_provider      import GroqProvider
from libercode.providers.openrouter_provider import OpenRouterProvider
from libercode.providers.ollama_provider    import OllamaProvider
from libercode.providers.deepseek_provider  import DeepSeekProvider
from libercode.providers.together_provider  import TogetherProvider
from libercode.providers.nvidia_provider    import NvidiaProvider
from libercode.providers.mistral_provider   import MistralProvider
from libercode.providers.cohere_provider    import CohereProvider
from libercode.providers.xai_provider       import XAIProvider
from libercode.providers.cerebras_provider  import CerebrasProvider
from libercode.providers.builtin            import BuiltinProvider
from libercode.providers.custom             import CustomProvider

PROVIDER_REGISTRY: dict[str, tuple[Type[BaseProvider], str]] = {
    "openai":     (OpenAIProvider,     "OPENAI_API_KEY"),
    "anthropic":  (AnthropicProvider,  "ANTHROPIC_API_KEY"),
    "google":     (GoogleProvider,     "GOOGLE_API_KEY"),
    "groq":       (GroqProvider,       "GROQ_API_KEY"),
    "openrouter": (OpenRouterProvider, "OPENROUTER_API_KEY"),
    "ollama":     (OllamaProvider,     ""),
    "deepseek":   (DeepSeekProvider,   "DEEPSEEK_API_KEY"),
    "together":   (TogetherProvider,   "TOGETHER_API_KEY"),
    "nvidia":     (NvidiaProvider,     "NVIDIA_API_KEY"),
    "mistral":    (MistralProvider,    "MISTRAL_API_KEY"),
    "cohere":     (CohereProvider,     "COHERE_API_KEY"),
    "xai":        (XAIProvider,        "XAI_API_KEY"),
    "cerebras":   (CerebrasProvider,   "CEREBRAS_API_KEY"),
    "builtin":    (BuiltinProvider,    ""),
    "custom":     (CustomProvider,     ""),
}


def available_providers() -> list[str]:
    result = []
    for name, (cls, env_var) in PROVIDER_REGISTRY.items():
        if not env_var:
            result.append(name)
        elif os.environ.get(env_var, "").strip():
            result.append(name)
    return result


def build_provider(
    name:        str,
    model:       str  = "",
    api_key:     str  = "",
    api_base:    str  = "",
    max_tokens:  int  = 4096,
    temperature: float = 0.2,
) -> BaseProvider:
    if name not in PROVIDER_REGISTRY:
        from libercode.providers.base import ProviderError
        raise ProviderError(
            f"Unknown provider '{name}'. "
            f"Available: {', '.join(PROVIDER_REGISTRY)}"
        )

    cls, env_var = PROVIDER_REGISTRY[name]
    resolved_key = api_key or (
        os.environ.get(env_var, "") if env_var else ""
    )

    instance = cls(
        model=model,
        api_key=resolved_key,
        api_base=api_base,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    instance.validate()
    return instance


def detect_available_from_env() -> dict[str, str]:
    found = {}
    for name, (cls, env_var) in PROVIDER_REGISTRY.items():
        if env_var and os.environ.get(env_var, "").strip():
            raw = os.environ[env_var]
            masked = raw[:4] + "…" + raw[-4:] if len(raw) > 8 else "****"
            found[name] = masked
    return found
