from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class CohereProvider(BaseProvider):
    display_name   = "cohere"
    default_model  = "command-r-plus"
    available_models = [
        "command-r-plus",
        "command-r",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "Cohere API key is required. "
                "Set COHERE_API_KEY or run /provider setup."
            )

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            import cohere
        except ImportError:
            raise ProviderError("Install cohere: pip install cohere")

        try:
            client = cohere.ClientV2(api_key=self.api_key)

            chat_msgs = []
            if system:
                chat_msgs.append({"role": "system", "content": system})
            for m in messages:
                chat_msgs.append({"role": m["role"], "content": m["content"]})

            stream = client.chat_stream(
                model=self.model,
                messages=chat_msgs,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            for event in stream:
                if event.event_type == "content-delta":
                    yield event.delta.message.content.text
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"Cohere error: {e}")

    def _fetch_models(self) -> list[str]:
        import cohere
        client = cohere.ClientV2(api_key=self.api_key)
        models = client.models.list()
        return sorted([m.name for m in models])
