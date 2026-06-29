import json
from typing import Optional, Generator
from libercode.providers.base import BaseProvider, ProviderError, request_with_retry


class CustomProvider(BaseProvider):
    display_name = "custom"
    default_model = "gpt-4"
    available_models = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]

    def __init__(
        self,
        name: str = "custom",
        api_key: str = "",
        api_base: str = "",
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ):
        self._name = name
        super().__init__(
            model=model or self.default_model,
            api_key=api_key,
            api_base=api_base.rstrip("/") if api_base else "",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        self.display_name = name

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(
                f"API key is required for provider '{self._name}'. "
                f"Set {self._name.upper()}_API_KEY or run /provider setup."
            )

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self._name == "anthropic":
            h["x-api-key"] = self.api_key
            h["anthropic-version"] = "2023-06-01"
        else:
            h["Authorization"] = f"Bearer {self.api_key}"
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
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature or self.temperature,
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
                "model": self.model,
                "messages": self._build_messages(messages, system),
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature or self.temperature,
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
        url = f"{self.api_base}/chat/completions"
        payload = self._build_payload(messages, system, temperature, max_tokens)
        try:
            resp = request_with_retry(url, payload, headers=self._headers())
            if resp is None:
                return "[Error] Max retries exceeded"
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
        url = f"{self.api_base}/messages"
        payload = self._build_payload(messages, system, temperature, max_tokens)
        try:
            resp = request_with_retry(url, payload, headers=self._headers())
            if resp is None:
                return "[Error] Max retries exceeded"
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
        url = f"{self.api_base}/chat/completions"
        payload = self._build_payload(
            messages, system, temperature, max_tokens, stream=True
        )
        try:
            resp = request_with_retry(url, payload, stream=True, headers=self._headers())
            if resp is None:
                yield "[Error] Max retries exceeded"
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

    def _stream_anthropic(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        url = f"{self.api_base}/messages"
        payload = self._build_payload(
            messages, system, temperature, max_tokens, stream=True
        )
        try:
            resp = request_with_retry(url, payload, stream=True, headers=self._headers())
            if resp is None:
                yield "[Error] Max retries exceeded"
                return
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
