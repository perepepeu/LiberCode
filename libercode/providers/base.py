# libercode/providers/base.py
"""Abstract base class for all LiberCode providers."""
from __future__ import annotations
import time
from abc import ABC, abstractmethod
from typing import Iterator

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
    """
    Every provider MUST subclass this and implement all
    abstract methods. Do NOT override __init__ without
    calling super().__init__().
    """

    #: Human-readable display name shown in the TUI
    display_name: str = "Unknown"

    #: Default model for this provider
    default_model: str = ""

    #: List of models this provider exposes.
    available_models: list[str] = []

    def __init__(
        self,
        model:       str  = "",
        api_key:     str  = "",
        api_base:    str  = "",
        max_tokens:  int  = 4096,
        temperature: float = 0.2,
    ) -> None:
        self.model       = model or self.default_model
        self.api_key     = api_key
        self.api_base    = api_base
        self.max_tokens  = max_tokens
        self.temperature = temperature
        self._models_cache: list[str] = []
        self._cache_ts: float = 0.0

    @property
    def name(self) -> str:
        """Short identifier used in status bar and logs."""
        return self.display_name

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict],
        system:   str = "",
    ) -> Iterator[str]:
        """
        Yield response text chunks as they arrive.
        MUST be a synchronous generator (plain def + yield).
        The caller runs this in a thread pool.
        Raise ProviderError on unrecoverable errors.
        """

    @abstractmethod
    def validate(self) -> None:
        """
        Verify that the provider is correctly configured
        (api_key present, api_base reachable, etc.).
        Raise ProviderError with a human-readable message on failure.
        Call this during __init__ only if it is fast (no HTTP).
        """

    def list_models(self) -> list[str]:
        """
        Return available model names for this provider.
        Uses a 5-minute in-memory cache. Override _fetch_models()
        to provide live data from the API.
        """
        import time as _time
        if self._models_cache and _time.time() - self._cache_ts < 300:
            return self._models_cache
        try:
            result = self._fetch_models()
            self._models_cache = result
            self._cache_ts = _time.time()
            return result
        except Exception:
            return self._models_cache or list(self.available_models)

    def _fetch_models(self) -> list[str]:
        """Override in subclasses to fetch models from the API."""
        return list(self.available_models)

    def mask_key(self) -> str:
        """Return a masked version of the API key for display."""
        k = self.api_key or ""
        if len(k) <= 8:
            return "****"
        return k[:4] + "…" + k[-4:]


class ProviderError(Exception):
    """Raised by providers on configuration or runtime errors."""
