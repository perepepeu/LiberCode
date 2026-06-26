import json
import requests
from typing import Optional, Generator
from libercode.providers.base import BaseProvider


class CustomProvider(BaseProvider):
    def __init__(
        self,
        name: str,
        api_key: str,
        api_base: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self._name = name
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    @property
    def name(self) -> str:
        return f"{self._name}/{self._model}"

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self._name == "openai":
            h["Authorization"] = f"Bearer {self._api_key}"
        elif self._name == "anthropic":
            h["x-api-key"] = self._api_key
            h["anthropic-version"] = "2023-06-01"
        else:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _build_payload(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> dict:
        if self._name == "anthropic":
            payload = {
                "model": self._model,
                "max_tokens": max_tokens or self._max_tokens,
                "temperature": temperature or self._temperature,
                "stream": stream,
            }
            if system:
                payload["system"] = system
                payload["messages"] = messages
            else:
                payload["messages"] = messages
            return payload
        else:
            payload = {
                "model": self._model,
                "messages": self._build_messages(messages, system),
                "max_tokens": max_tokens or self._max_tokens,
                "temperature": temperature or self._temperature,
                "stream": stream,
            }
            return payload

    def chat(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if self._name == "anthropic":
            return self._chat_anthropic(messages, system, temperature, max_tokens)
        return self._chat_openai_compat(messages, system, temperature, max_tokens)

    def _chat_openai_compat(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self._api_base}/chat/completions"
        payload = self._build_payload(messages, system, temperature, max_tokens)
        try:
            resp = requests.post(
                url, json=payload, headers=self._headers(), timeout=120
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[Error {resp.status_code}] {resp.text[:300]}"
        except Exception as e:
            return f"[Connection Error] {e}"

    def _chat_anthropic(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self._api_base}/messages"
        payload = self._build_payload(messages, system, temperature, max_tokens)
        try:
            resp = requests.post(
                url, json=payload, headers=self._headers(), timeout=120
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
            else:
                return f"[Error {resp.status_code}] {resp.text[:300]}"
        except Exception as e:
            return f"[Connection Error] {e}"

    def chat_stream(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        if self._name == "anthropic":
            yield from self._stream_anthropic(messages, system, temperature, max_tokens)
        else:
            yield from self._stream_openai_compat(
                messages, system, temperature, max_tokens
            )

    def _stream_openai_compat(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        url = f"{self._api_base}/chat/completions"
        payload = self._build_payload(
            messages, system, temperature, max_tokens, stream=True
        )
        try:
            resp = requests.post(
                url, json=payload, headers=self._headers(), stream=True, timeout=120
            )
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

    def _stream_anthropic(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        url = f"{self._api_base}/messages"
        payload = self._build_payload(
            messages, system, temperature, max_tokens, stream=True
        )
        try:
            resp = requests.post(
                url, json=payload, headers=self._headers(), stream=True, timeout=120
            )
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {}).get("text", "")
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
