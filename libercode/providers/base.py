from abc import ABC, abstractmethod
from typing import Optional
import time
import requests

MAX_RETRIES = 3
BACKOFF_BASE = 2


def _log_retry(attempt: int, wait: int):
    print(f"\r  [Retry {attempt + 1}/{MAX_RETRIES}] Waiting {wait}s...", end="", flush=True)


def request_with_retry(url: str, payload: dict, headers: dict = None, stream: bool = False):
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                url, json=payload, headers=headers or {}, stream=stream, timeout=120
            )
            if resp.status_code == 429:
                wait = BACKOFF_BASE ** attempt
                _log_retry(attempt, wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = BACKOFF_BASE ** attempt
                _log_retry(attempt, wait)
                time.sleep(wait)
                continue
            return resp
        except requests.ConnectionError:
            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE ** attempt
                _log_retry(attempt, wait)
                time.sleep(wait)
                continue
            raise
        except requests.Timeout:
            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE ** attempt
                _log_retry(attempt, wait)
                time.sleep(wait)
                continue
            raise
    return None


class BaseProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str: ...

    @abstractmethod
    def chat_stream(
        self,
        messages: list,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ): ...

    @property
    @abstractmethod
    def name(self) -> str: ...
