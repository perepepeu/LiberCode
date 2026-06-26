import json
import requests
from typing import Optional, Generator
from libercode.providers.base import BaseProvider


class BuiltinProvider(BaseProvider):
    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
        api_base: str = "https://api-inference.huggingface.co/models/",
    ):
        self._model = model
        self._api_base = api_base.rstrip("/")

    @property
    def name(self) -> str:
        return f"builtin/{self._model}"

    def chat(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self._api_base}/{self._model}/v1/chat/completions"
        payload = {
            "messages": self._build_messages(messages, system),
            "max_tokens": max_tokens or 4096,
            "temperature": temperature or 0.7,
        }
        try:
            resp = requests.post(url, json=payload, timeout=120)
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
        url = f"{self._api_base}/{self._model}/v1/chat/completions"
        payload = {
            "messages": self._build_messages(messages, system),
            "max_tokens": max_tokens or 4096,
            "temperature": temperature or 0.7,
            "stream": True,
        }
        try:
            resp = requests.post(url, json=payload, stream=True, timeout=120)
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
