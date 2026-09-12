"""Minimal Ollama chat client (stdlib only). Used ONLY by the optional
head-to-head experiment — the v0 engine and its tests never touch this."""

from __future__ import annotations

import json
import urllib.request


class OllamaClient:
    def __init__(self, model: str = "qwen2.5:7b-instruct",
                 host: str = "http://localhost:11434",
                 seed: int = 7, timeout: float = 300.0,
                 num_predict: int = 300) -> None:
        self.model = model
        self.host = host
        self.seed = seed
        self.timeout = timeout
        # thinking models (qwen3 etc.) need room to reason before the JSON
        self.num_predict = 2048 if "qwen3" in model or "think" in model else num_predict

    def chat(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "seed": self.seed,
                        "num_predict": self.num_predict},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        msg = data["message"]
        content = msg.get("content", "")
        thinking = msg.get("thinking") or ""
        if thinking:
            # keep the reasoning visible for transcripts; the action parser
            # takes the LAST JSON object, which lives in the content
            content = f"<think>{thinking}</think>\n{content}"
        return content
