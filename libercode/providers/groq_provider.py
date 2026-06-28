from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class GroqProvider(BaseProvider):
    display_name   = "groq"
    default_model  = "llama-3.3-70b-versatile"
    available_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "Groq API key is required. "
                "Set GROQ_API_KEY or run /provider setup."
            )

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            from groq import Groq
        except ImportError:
            raise ProviderError(
                "Install groq: pip install groq"
            )

        client = Groq(api_key=self.api_key)
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
            raise ProviderError(f"Groq error: {e}")

    def _fetch_models(self) -> list[str]:
        import requests
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data])
