"""OpenAI-compatible chat client (stdlib only) — covers DeepSeek and any
other /chat/completions endpoint. Same chat() interface as the other clients.

Keys come from environment variables only; nothing is ever written to disk.
  DeepSeek:  set DEEPSEEK_API_KEY, base_url https://api.deepseek.com
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


class OpenAICompatClient:
    def __init__(self, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com",
                 api_key_env: str = "DEEPSEEK_API_KEY",
                 timeout: float = 180.0, max_retries: int = 3) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        if not self.api_key:
            raise RuntimeError(f"{api_key_env} is not set in the environment.")
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": 2048,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())
                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""
                reasoning = msg.get("reasoning_content") or ""
                if reasoning:
                    content = f"<think>{reasoning}</think>\n{content}"
                return content
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code in (429, 500, 502, 503):
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(f"API call failed after retries: {last_error}")
