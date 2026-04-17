"""Gemini client with model tiering and structured output.

Design notes:
- We use the new `google-genai` SDK (unified client for Gemini API).
- Three tiers ("fast", "plan", "heavy") are chosen per call-site based on
  expected value of the call. Reflection and conversation generation pay
  for Pro; perception filtering and importance scoring use Flash-Lite.
- All structured outputs go through Pydantic schemas — no regex fallback.
- Retries are bounded (3x); on persistent failure we raise so the caller
  decides a fail-safe rather than silently returning a default.
"""
from __future__ import annotations

import logging
import os
import time
from enum import Enum
from typing import Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ModelTier(str, Enum):
    FAST = "fast"
    PLAN = "plan"
    HEAVY = "heavy"


class GeminiClient:
    """Thin wrapper around google-genai with tier routing + Pydantic output."""

    def __init__(self, model_map: dict[str, str], api_key: str | None = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Place it in .env.local or .env."
            )
        self._client = genai.Client(api_key=api_key)
        self._models = {
            ModelTier.FAST: model_map["fast"],
            ModelTier.PLAN: model_map["plan"],
            ModelTier.HEAVY: model_map["heavy"],
        }
        self._call_count = {tier: 0 for tier in ModelTier}

    @property
    def call_count(self) -> dict[str, int]:
        return {tier.value: n for tier, n in self._call_count.items()}

    def generate_structured(
        self,
        tier: ModelTier,
        prompt: str,
        schema: Type[T],
        system: str | None = None,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> T:
        """Call Gemini with JSON-schema-constrained output and parse to a Pydantic model."""
        model = self._models[tier]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            system_instruction=system,
        )
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                self._call_count[tier] += 1
                # google-genai surfaces parsed result as .parsed when response_schema is set
                parsed = getattr(resp, "parsed", None)
                if isinstance(parsed, schema):
                    return parsed
                # fallback: manually validate from .text
                return schema.model_validate_json(resp.text)
            except Exception as e:  # noqa: BLE001 — we classify via last_err
                last_err = e
                logger.warning(
                    "Gemini structured call failed (attempt %d/%d) on %s: %s",
                    attempt + 1,
                    max_retries,
                    model,
                    e,
                )
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(
            f"Gemini structured call failed after {max_retries} attempts on {model}: {last_err}"
        )

    def generate_text(
        self,
        tier: ModelTier,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        model = self._models[tier]
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system,
        )
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        self._call_count[tier] += 1
        return resp.text or ""
