"""
agents/llm.py
-------------
Small model-provider boundary for agent message calls.

Only Anthropic is implemented today. Other providers should be added behind
this interface instead of inside individual agents.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Protocol

import anthropic

from config import settings


@dataclass
class LLMBlock:
    """Normalized content block returned by an LLM provider."""

    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None


@dataclass
class LLMUsage:
    """Normalized token usage returned by an LLM provider."""

    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class LLMResponse:
    """Normalized response shape consumed by the agents."""

    stop_reason: str
    content: list[LLMBlock]
    usage: LLMUsage | None = None


class LLMClient(Protocol):
    """Interface every provider adapter must satisfy."""

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> LLMResponse:
        ...


class AnthropicLLMClient:
    """Anthropic-backed implementation of the local LLM client boundary."""

    def __init__(self, api_key: str, anthropic_client: Any | None = None) -> None:
        self.client = anthropic_client or anthropic.Anthropic(api_key=api_key)

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> LLMResponse:
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=[_message_to_anthropic(message) for message in messages],
        )
        return _normalize_anthropic_response(response)


def create_llm_client() -> LLMClient:
    """Create the configured LLM client."""
    provider = os.getenv("LLM_PROVIDER", settings.LLM_PROVIDER).strip().lower()
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or settings.ANTHROPIC_API_KEY
        if not api_key:
            raise EnvironmentError(
                "Missing required environment variable: ANTHROPIC_API_KEY\n"
                "Check your .env file (copy .env.example to get started)."
            )
        return AnthropicLLMClient(api_key=api_key)
    raise ValueError(
        f"Unsupported LLM_PROVIDER='{provider}'. Supported providers: anthropic."
    )


def _message_to_anthropic(message: dict[str, Any]) -> dict[str, Any]:
    """Convert a normalized message into Anthropic's message shape."""
    return {
        "role": message["role"],
        "content": _content_to_anthropic(message["content"]),
    }


def _content_to_anthropic(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return content

    converted = []
    for block in content:
        if isinstance(block, dict):
            converted.append(block)
            continue

        block_type = getattr(block, "type", None)
        if block_type == "text":
            converted.append({"type": "text", "text": getattr(block, "text", "") or ""})
        elif block_type == "tool_use":
            converted.append({
                "type": "tool_use",
                "id": getattr(block, "id", None),
                "name": getattr(block, "name", None),
                "input": getattr(block, "input", None) or {},
            })
        else:
            converted.append(block)

    return converted


def _normalize_anthropic_response(response: Any) -> LLMResponse:
    usage = getattr(response, "usage", None)
    normalized_usage = None
    if usage is not None:
        normalized_usage = LLMUsage(
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    return LLMResponse(
        stop_reason=getattr(response, "stop_reason"),
        content=[_normalize_anthropic_block(block) for block in response.content],
        usage=normalized_usage,
    )


def _normalize_anthropic_block(block: Any) -> LLMBlock:
    block_type = getattr(block, "type", "")
    if block_type == "text":
        return LLMBlock(type="text", text=getattr(block, "text", ""))
    if block_type == "tool_use":
        return LLMBlock(
            type="tool_use",
            id=getattr(block, "id", None),
            name=getattr(block, "name", None),
            input=getattr(block, "input", None) or {},
        )
    return LLMBlock(type=block_type)
