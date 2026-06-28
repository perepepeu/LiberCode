from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class AnthropicProvider(BaseProvider):
    display_name   = "anthropic"
    default_model  = "claude-sonnet-4-5"
    available_models = [
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "Anthropic API key is required. "
                "Set ANTHROPIC_API_KEY or run /provider setup."
            )

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            import anthropic
        except ImportError:
            raise ProviderError(
                "Install anthropic: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        clean = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                clean.append(m)

        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system or "",
                messages=clean,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            raise ProviderError(f"Anthropic error: {e}")

    def _fetch_models(self) -> list[str]:
        import requests
        resp = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=10,
        )
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data])
