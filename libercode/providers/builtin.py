import json
import os
from typing import Optional, Generator
from libercode.providers.base import BaseProvider, ProviderError, request_with_retry


class BuiltinProvider(BaseProvider):
    display_name = "builtin"
    default_model = "Qwen/Qwen2.5-Coder-7B-Instruct"
    available_models = [
        "Qwen/Qwen2.5-Coder-7B-Instruct",
        "Qwen/Qwen2.5-Coder-14B-Instruct",
    ]

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        api_base: str = "https://api-inference.huggingface.co/models/",
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ):
        super().__init__(
            model=model or self.default_model,
            api_key=api_key,
            api_base=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def validate(self) -> None:
        if not self.api_base:
            raise ProviderError(
                "BuiltinProvider requires api_base (HuggingFace endpoint URL)."
            )

    def _get_headers(self) -> dict:
        headers = {}
        token = os.environ.get("HF_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def chat(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self.api_base}/{self.model}/v1/chat/completions"
        payload = {
            "messages": self._build_messages(messages, system),
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
        }
        try:
            resp = request_with_retry(url, payload, headers=self._get_headers())
            if resp is None:
                return "[Error] Max retries exceeded"
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            elif resp.status_code == 503:
                return self._handle_loading(resp)
            else:
                return f"[Error {resp.status_code}] {resp.text[:200]}"
        except Exception as e:
            return f"[Connection Error] {e}"

    def chat_stream(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        url = f"{self.api_base}/{self.model}/v1/chat/completions"
        payload = {
            "messages": self._build_messages(messages, system),
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "stream": True,
        }
        try:
            resp = request_with_retry(url, payload, stream=True, headers=self._get_headers())
            if resp is None:
                yield "[Error] Max retries exceeded"
                return
            if resp.status_code == 503:
                yield self._handle_loading(resp)
                return
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"[Stream Error] {e}"

    def _build_messages(self, messages: list, system: Optional[str] = None) -> list:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        result.extend(messages)
        return result

    def _handle_loading(self, resp) -> str:
        try:
            data = resp.json()
            estimated = data.get("estimated_time", 30)
            return f"[Model is loading - estimated wait: {estimated}s. Please retry in a moment.]"
        except Exception:
            return "[Model is loading. Please retry shortly.]"
