"""Reusable IBM Granite client via watsonx.ai REST API.

Usage:
    from app.services.granite import GraniteService, get_granite_service
    granite = get_granite_service()
    result = await granite.generate("Explain machine learning in 2 sentences.")
"""

import logging
from functools import lru_cache
from typing import Any, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class GraniteError(Exception):
    """Raised when the Granite API returns an error."""


class GraniteService:
    """Thin async client for the IBM watsonx.ai text generation endpoint."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._iam_token: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        return self._settings.granite_configured

    async def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Generate text with IBM Granite and return the generated string.

        Raises GraniteError if not configured or the API call fails.
        """
        if not self.is_configured:
            raise GraniteError(
                "IBM Granite is not configured. Set GRANITE_API_KEY and IBM_PROJECT_ID."
            )

        token = await self._get_iam_token()
        payload = self._build_payload(prompt, max_new_tokens, temperature, stop_sequences)
        return await self._call_api(token, payload)

    async def generate_safe(
        self,
        prompt: str,
        fallback: str = "[Granite not configured — set GRANITE_API_KEY and IBM_PROJECT_ID]",
        **kwargs: Any,
    ) -> "tuple[str, bool]":
        """Generate text; returns (text, granite_used).

        Falls back to `fallback` string when not configured instead of raising.
        """
        if not self.is_configured:
            logger.warning("Granite not configured; returning fallback response.")
            return fallback, False
        try:
            text = await self.generate(prompt, **kwargs)
            return text, True
        except GraniteError as exc:
            logger.error("Granite API error: %s", exc)
            return fallback, False

    # ── Internals ────────────────────────────────────────────────────────

    def _build_payload(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        stop_sequences: Optional[List[str]],
    ) -> dict:
        params: dict = {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
        }
        if stop_sequences:
            params["stop_sequences"] = stop_sequences

        return {
            "model_id": self._settings.granite_model_id,
            "project_id": self._settings.ibm_project_id,
            "input": prompt,
            "parameters": params,
        }

    async def _get_iam_token(self) -> Optional[str]:
        """Exchange the API key for an IAM bearer token (cached in memory)."""
        if self._iam_token:
            return self._iam_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://iam.cloud.ibm.com/identity/token",
                data={
                    "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                    "apikey": self._settings.granite_api_key,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                raise GraniteError(f"IAM token exchange failed: {resp.status_code} {resp.text}")

            self._iam_token = resp.json()["access_token"]
            return self._iam_token  # type: ignore[return-value]

    async def _call_api(self, token: str, payload: dict) -> str:
        settings = self._settings
        url = f"{settings.granite_url}?version={settings.granite_api_version}"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

        if resp.status_code != 200:
            # Token may have expired — clear cache so next call re-authenticates
            self._iam_token = None
            raise GraniteError(f"Granite API error {resp.status_code}: {resp.text}")

        data = resp.json()
        try:
            return data["results"][0]["generated_text"]
        except (KeyError, IndexError) as exc:
            raise GraniteError(f"Unexpected Granite response shape: {data}") from exc


@lru_cache(maxsize=1)
def get_granite_service() -> GraniteService:
    """Return a singleton GraniteService instance."""
    return GraniteService()
