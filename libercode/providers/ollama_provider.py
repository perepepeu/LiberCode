from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class OllamaProvider(BaseProvider):
    display_name  = "ollama"
    default_model = "llama3.2"
    available_models = [
        "llama3.2",
        "llama3.1",
    ]

    def __init__(self, model="", api_key="",
                 api_base="", max_tokens=4096, temperature=0.2):
        super().__init__(model, api_key, api_base, max_tokens, temperature)
        self.api_base = api_base or "http://localhost:11434"

    def validate(self) -> None:
        pass

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            from openai import OpenAI
        except ImportError:
            raise ProviderError("Install openai: pip install openai")

        client = OpenAI(
            api_key="ollama",
            base_url=f"{self.api_base}/v1",
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
            raise ProviderError(
                f"Ollama error: {e}\n"
                "Is Ollama running? Try: ollama serve"
            )

    def _fetch_models(self) -> list[str]:
        import requests
        resp = requests.get(
            f"{self.api_base}/api/tags",
            timeout=3,
        )
        data = resp.json().get("models", [])
        return [m["name"] for m in data]
