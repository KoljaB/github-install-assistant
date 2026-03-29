from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class OpenAITextResponse:
    response_id: str
    text: str
    raw_payload: dict[str, Any]


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required to use the installation assistant.")

    def create_json_response(
        self,
        *,
        model: str,
        prompt: str,
        schema: dict[str, Any],
        previous_response_id: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str = "medium",
    ) -> OpenAITextResponse:
        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "reasoning": {"effort": reasoning_effort},
            "text": {"format": schema},
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        if tools:
            payload["tools"] = tools

        try:
            return self._post(payload)
        except RuntimeError as exc:
            if tools and any(tool.get("type") == "web_search" for tool in tools):
                fallback_tools = [
                    {"type": "web_search_preview"} if tool.get("type") == "web_search" else tool
                    for tool in tools
                ]
                payload["tools"] = fallback_tools
                return self._post(payload)
            raise exc

    def _post(self, payload: dict[str, Any]) -> OpenAITextResponse:
        request = urllib.request.Request(
            url=f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API connection failed: {exc}") from exc

        return OpenAITextResponse(
            response_id=raw.get("id", ""),
            text=_extract_text(raw),
            raw_payload=raw,
        )


def _extract_text(payload: dict[str, Any]) -> str:
    output = payload.get("output", [])
    chunks: list[str] = []
    for item in output:
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "".join(chunks).strip()
