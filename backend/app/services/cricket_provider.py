import os
import re
import hashlib
import time
import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

_CACHE_TTLS = {
    "currentMatches": 60,
    "matches": 300,
    "match_scorecard": 120,
}
_response_cache: dict[tuple[str, tuple[tuple[str, Any], ...], str, str], tuple[float, dict[str, Any]]] = {}
_cache_locks: dict[tuple[str, tuple[tuple[str, Any], ...], str, str], asyncio.Lock] = {}


def _cache_key(
    endpoint: str,
    api_key: str,
    params: dict[str, Any],
    mode: str = "live",
) -> tuple[str, tuple[tuple[str, Any], ...], str, str]:
    key_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return endpoint, tuple(sorted(params.items())), key_digest, mode


def _cached_response(
    key: tuple[str, tuple[tuple[str, Any], ...], str, str],
) -> dict[str, Any] | None:
    cached = _response_cache.get(key)
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at <= time.monotonic():
        _response_cache.pop(key, None)
        return None
    return payload


def _store_response(
    key: tuple[str, tuple[tuple[str, Any], ...], str, str],
    endpoint: str,
    payload: dict[str, Any],
) -> None:
    _response_cache[key] = (time.monotonic() + _CACHE_TTLS[endpoint], payload)


@dataclass
class CricketProviderError(RuntimeError):
    """Raised when Cricket Data cannot return a usable response."""

    message: str
    code: str | None = None
    endpoint: str | None = None
    http_status: int | None = None
    provider_status: str | None = None
    provider_message: str | None = None
    provider_reason: str | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def safe_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"message": self.message}
        if self.code is not None:
            detail["code"] = self.code
        if self.http_status is not None:
            detail["provider_http_status"] = self.http_status
        if self.provider_status is not None:
            detail["provider_status"] = self.provider_status
        if self.provider_message:
            detail["provider_message"] = self.provider_message
        if self.provider_reason:
            detail["provider_reason"] = self.provider_reason
        return detail


def _safe_text(value: Any, secret: str) -> str | None:
    if not isinstance(value, str):
        return None
    redacted = value.replace(secret, "[redacted]") if secret else value
    redacted = re.sub(r"(?i)(apikey|api_key|key)=([^&\s]+)", r"\1=[redacted]", redacted)
    return redacted[:500]


class CricketDataProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("CRICKET_DATA_API_KEY")
        self.base_url = (base_url or os.getenv("CRICKET_DATA_API_BASE_URL", "https://api.cricapi.com/v1")).rstrip("/")
        self._client = client

    async def _get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        if not self.api_key:
            raise CricketProviderError(
                "CRICKET_DATA_API_KEY is not configured",
                code="CRICKET_API_KEY_MISSING",
                endpoint=endpoint,
            )
        cache_key = _cache_key(endpoint, self.api_key, params)
        cached = _cached_response(cache_key)
        if cached is not None:
            return cached
        lock = _cache_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = _cached_response(cache_key)
            if cached is not None:
                return cached
            request_params = {"apikey": self.api_key, **params}
            owns_client = self._client is None
            client = self._client or httpx.AsyncClient(timeout=10)
            try:
                response = await client.get(f"{self.base_url}/{endpoint}", params=request_params)
            except httpx.HTTPError as error:
                raise CricketProviderError(
                    "Cricket Data request failed",
                    code="CRICKET_NETWORK_ERROR",
                    endpoint=endpoint,
                    provider_message=_safe_text(str(error), self.api_key),
                ) from error
            finally:
                if owns_client:
                    await client.aclose()
            try:
                payload = response.json()
            except ValueError as error:
                raise CricketProviderError(
                    "Cricket Data returned invalid JSON",
                    code="CRICKET_INVALID_RESPONSE",
                    endpoint=endpoint,
                    http_status=response.status_code,
                ) from error

            provider_status = _safe_text(payload.get("status"), self.api_key) if isinstance(payload, dict) else None
            provider_message = _safe_text(payload.get("message"), self.api_key) if isinstance(payload, dict) else None
            provider_reason = _safe_text(payload.get("reason"), self.api_key) if isinstance(payload, dict) else None
            quota_exhausted = isinstance(provider_reason, str) and provider_reason.casefold() == "quota"
            if response.is_error:
                raise CricketProviderError(
                    "Cricket Data HTTP request failed",
                    code="CRICKET_QUOTA_EXHAUSTED" if quota_exhausted else "CRICKET_HTTP_ERROR",
                    endpoint=endpoint,
                    http_status=response.status_code,
                    provider_status=provider_status,
                    provider_message=provider_message,
                    provider_reason=provider_reason,
                )
            if not isinstance(payload, dict) or payload.get("status") not in (None, "success"):
                raise CricketProviderError(
                    "Cricket Data returned an unsuccessful response",
                    code="CRICKET_QUOTA_EXHAUSTED" if quota_exhausted else "CRICKET_PROVIDER_ERROR",
                    endpoint=endpoint,
                    http_status=response.status_code,
                    provider_status=provider_status,
                    provider_message=provider_message,
                    provider_reason=provider_reason,
                )
            _store_response(cache_key, endpoint, payload)
            return payload

    async def live_matches(self, offset: int = 0) -> dict[str, Any]:
        return await self._get("currentMatches", offset=offset)

    async def recent_matches(self, offset: int = 0) -> dict[str, Any]:
        return await self._get("matches", offset=offset)

    async def scorecard(self, match_id: str) -> dict[str, Any]:
        return await self._get("match_scorecard", offset=0, id=match_id)
