"""Thin Vertex Gemini wrapper: JSON mode, retry with backoff, json_repair on parse.

Slimmed-down copy of opportunityX_AI-Workers/app/services/gemini_client.py.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

from google import genai
from google.genai import types
from json_repair import repair_json

log = logging.getLogger("capabilityx.gemini")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT", "qistonpe-project-22810"),
            location=os.getenv("GCP_LOCATION", "global"),
        )
    return _client


def generate_json(
    prompt: str,
    parts: list[Any] | None = None,
    *,
    temperature: float = 0.2,
    seed: int | None = None,
    schema: dict | None = None,
    model: str | None = None,
    max_retries: int = 4,
    tag: str = "",
) -> Any:
    """Send prompt (+ optional file parts) and return the parsed JSON response."""
    config = types.GenerateContentConfig(
        temperature=temperature,
        seed=seed,
        max_output_tokens=32768,
        response_mime_type="application/json",
        response_schema=schema,
    )
    contents = [*(parts or []), prompt]
    last: Exception | None = None
    for attempt in range(1, max_retries + 1):
        t0 = time.perf_counter()
        try:
            r = client().models.generate_content(model=model or MODEL, contents=contents, config=config)
            text = r.text or ""
            log.info("gemini %s ok in %.1fs (%d chars)", tag, time.perf_counter() - t0, len(text))
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return json.loads(repair_json(text))
        except Exception as e:  # network / quota / parse — retry all
            last = e
            log.warning("gemini %s attempt %d failed: %s", tag, attempt, str(e)[:200])
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 20) + random.random())
    raise RuntimeError(f"Gemini call failed ({tag}): {last}")


def file_part(data: bytes, mime_type: str) -> types.Part:
    return types.Part.from_bytes(data=data, mime_type=mime_type)
