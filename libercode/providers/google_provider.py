from __future__ import annotations
from typing import Iterator
from libercode.providers.base import BaseProvider, ProviderError


class GoogleProvider(BaseProvider):
    display_name   = "google"
    default_model  = "gemini-2.0-flash"
    available_models = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                "Google API key is required. "
                "Set GOOGLE_API_KEY or run /provider setup."
            )

    def chat_stream(
        self, messages: list[dict], system: str = ""
    ) -> Iterator[str]:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ProviderError(
                "Install google-generativeai: pip install google-generativeai"
            )

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system or None,
        )

        history = []
        for m in messages[:-1]:
            role    = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
        last_user = messages[-1]["content"] if messages else ""

        try:
            chat   = model.start_chat(history=history)
            stream = chat.send_message(last_user, stream=True)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise ProviderError(f"Google error: {e}")
