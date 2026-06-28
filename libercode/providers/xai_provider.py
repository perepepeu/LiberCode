from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class XAIProvider(BaseProvider):
    display_name   = "xai"
    default_model  = "grok-3"
    available_models = [
        "grok-3",
        "grok-3-mini",
        "grok-2",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "xAI API key is required. "
                "Set XAI_API_KEY or run /provider setup."
            )

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            from openai import OpenAI
        except ImportError:
            raise ProviderError("Install openai: pip install openai")

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1",
        )
        msgs = []
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
            raise ProviderError(f"xAI error: {e}")

    def list_models(self) -> list[str]:
        return list(self.available_models)
