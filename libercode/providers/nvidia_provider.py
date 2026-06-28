from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class NvidiaProvider(BaseProvider):
    display_name   = "nvidia"
    default_model  = "nvidia/llama-3.1-nemotron-ultra-253b-v1"
    available_models = [
        "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "nvidia/llama-3.3-70b-instruct",
        "nvidia/llama-3.1-405b-instruct",
        "nvidia/llama-3.1-70b-instruct",
        "meta/llama-3.3-70b-instruct",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "NVIDIA API key is required. "
                "Set NVIDIA_API_KEY or run /provider setup."
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
            base_url="https://integrate.api.nvidia.com/v1",
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
            raise ProviderError(f"NVIDIA error: {e}")

    def list_models(self) -> list[str]:
        return list(self.available_models)
