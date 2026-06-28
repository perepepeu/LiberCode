from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class TogetherProvider(BaseProvider):
    display_name  = "together"
    default_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    available_models = [
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        "deepseek-ai/DeepSeek-R1",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "google/gemma-2-27b-it",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "Together AI API key is required. "
                "Set TOGETHER_API_KEY or run /provider setup."
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
            base_url="https://api.together.xyz/v1",
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
            raise ProviderError(f"Together error: {e}")
