from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class OpenAIProvider(BaseProvider):
    display_name   = "openai"
    default_model  = "gpt-4o"
    available_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4.1",
        "o3",
        "o3-mini",
        "o4-mini",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "OpenAI API key is required. "
                "Set OPENAI_API_KEY or run /provider setup."
            )

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            from openai import OpenAI
        except ImportError:
            raise ProviderError("Install openai: pip install openai")

        client = OpenAI(api_key=self.api_key)
        msgs   = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        try:
            stream = client.chat.completions.create(
                model=self.model,
                messages=msgs,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise ProviderError(f"OpenAI error: {e}")

    def list_models(self) -> list[str]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            models = client.models.list()
            gpt = sorted(
                [m.id for m in models.data if "gpt" in m.id or "o3" in m.id or "o4" in m.id],
                reverse=True
            )
            return gpt or self.available_models
        except Exception:
            return self.available_models
