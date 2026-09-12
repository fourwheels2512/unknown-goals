"""Gemini API client (stdlib only) with the same chat() interface as
OllamaClient, so every experiment accepts --provider gemini unchanged.

Reads the key from the GEMINI_API_KEY environment variable — never hardcode
keys, never commit them. Usage:

  set GEMINI_API_KEY=...            (PowerShell: $env:GEMINI_API_KEY="...")
  uv run python experiments/head_to_head.py --provider gemini --model gemini-2.5-flash
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


class GeminiClient:
    def __init__(self, model: str = "gemini-2.5-flash",
                 api_key: str | None = None, timeout: float = 120.0,
                 max_retries: int = 3) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it in the environment first.")
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(self, system: str, user: str) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2048},
        }
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "x-goog-api-key": self.api_key})
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts)
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code in (429, 500, 503):        # rate limit / transient
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise
            except (KeyError, IndexError) as e:      # safety block or empty
                last_error = e
                break
        raise RuntimeError(f"Gemini call failed after retries: {last_error}")
