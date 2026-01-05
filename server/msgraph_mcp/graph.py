import asyncio
import random
from typing import Any

import httpx

from .config import settings
from .errors import MCPError


class GraphClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)

    async def request(
        self,
        method: str,
        url: str,
        token: str,
        headers: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        for attempt in range(settings.max_retry_attempts):
            response = await self._client.request(
                method, url, headers=req_headers, **kwargs
            )
            if response.status_code in (429, 503):
                retry_after = int(response.headers.get("Retry-After", "1"))
                await asyncio.sleep(retry_after)
                continue
            if response.status_code >= 500:
                await asyncio.sleep(self._backoff(attempt))
                continue
            if response.status_code >= 400:
                raise MCPError(
                    "UPSTREAM_ERROR", f"Graph error: {response.text}", status=502
                )
            if response.status_code == 204:
                return {}
            return response.json()

        raise MCPError(
            "UPSTREAM_ERROR", "Graph request failed after retries", status=502
        )

    async def request_raw(
        self,
        method: str,
        url: str,
        token: str,
        headers: dict | None = None,
        **kwargs: Any,
    ) -> bytes:
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "*/*",
        }
        if headers:
            req_headers.update(headers)

        response = await self._client.request(
            method, url, headers=req_headers, **kwargs
        )
        if response.status_code >= 400:
            raise MCPError(
                "UPSTREAM_ERROR", f"Graph error: {response.text}", status=502
            )
        return response.content

    def _backoff(self, attempt: int) -> float:
        base = settings.retry_base_seconds * (2**attempt)
        return base + random.uniform(0, base)

    async def close(self) -> None:
        await self._client.aclose()
