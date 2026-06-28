from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class OpenRouterProvider(BaseProvider):
    display_name  = "openrouter"
    default_model = "anthropic/claude-sonnet-4-5"
    available_models = [
        "anthropic/claude-sonnet-4-5",
        "openai/gpt-4o",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "OpenRouter API key is required. "
                "Set OPENROUTER_API_KEY or run /provider setup."
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
            base_url="https://openrouter.ai/api/v1",
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
                extra_headers={
                    "HTTP-Referer": "https://github.com/perepepeu/LiberCode",
                    "X-Title": "LiberCode",
                },
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise ProviderError(f"OpenRouter error: {e}")

    def _fetch_models(self) -> list[str]:
        import requests
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data])[:50]
