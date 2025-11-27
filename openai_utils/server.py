"""Minimal FastAPI server that bridges ChatKit webhook events to the Agents SDK."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Mapping, MutableMapping

import config
from agents import Agent, Runner
from fastapi import FastAPI, Request
from openai.types.responses import ResponseOutputItem, ResponseOutputMessage, ResponseOutputRefusal, ResponseOutputText
from openai.types.responses.response_input_item_param import FunctionCallOutput, Message as ResponseMessage

app = FastAPI()
logger = logging.getLogger(__name__)

_agent: Agent[Any] | None = None


def _get_agent() -> Agent[Any]:
    """Lazy-initialise the wizard agent so module import does not fail during testing."""

    global _agent
    if _agent is None:
        from agent_setup import build_wizard_agent

        _agent = build_wizard_agent(vector_store_ids=["VS_123"])
    return _agent


def _user_message_input(text: str) -> list[ResponseMessage]:
    """Build a structured Responses input item for a user utterance."""

    return [
        {
            "role": "user",
            "type": "message",
            "content": [{"type": "input_text", "text": text}],
        }
    ]


def _action_invocation_input(action: Mapping[str, Any]) -> list[FunctionCallOutput]:
    """Convert a ChatKit action payload into a direct tool output for the model."""

    call_id = str(action.get("id") or action.get("call_id"))
    payload = action.get("payload", {})
    output: str | Iterable[Mapping[str, Any]]
    if isinstance(payload, str):
        output = payload
    else:
        output = json.dumps(payload)
    return [
        {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        }
    ]


def _serialise_messages(items: Iterable[Any]) -> list[MutableMapping[str, Any]]:
    """Return ChatKit-friendly message payloads from Agents ``RunItem`` objects."""

    serialised: list[MutableMapping[str, Any]] = []
    for item in items:
        raw: ResponseOutputItem | Mapping[str, Any] | None = getattr(item, "raw_item", None)
        if raw is None:
            raw = item if isinstance(item, Mapping) else None
        if isinstance(raw, ResponseOutputMessage):
            content_items = raw.content
            role = raw.role
            message_id = raw.id
            status = raw.status
        elif isinstance(raw, Mapping):
            content_items = raw.get("content", [])
            role = raw.get("role", "assistant")
            message_id = raw.get("id")
            status = raw.get("status", "completed")
        else:
            continue

        content: list[MutableMapping[str, Any]] = []
        for part in content_items:
            if isinstance(part, ResponseOutputText):
                content.append({"type": "text", "text": part.text})
            elif isinstance(part, ResponseOutputRefusal):
                content.append({"type": "refusal", "reason": part.refusal})
            elif isinstance(part, Mapping) and "text" in part:
                content.append({"type": part.get("type", "text"), "text": part["text"]})

        serialised.append(
            {
                "id": message_id,
                "role": role,
                "type": "message",
                "status": status,
                "content": content,
            }
        )
    return serialised


@app.post("/chatkit/respond")
async def respond(req: Request) -> MutableMapping[str, Any]:
    """Handle ChatKit events and drive the Agents event loop directly."""

    event = await req.json()
    event_type = event.get("type")
    conversation_id = event.get("conversation_id")
    run_config = {"model": config.REASONING_MODEL, "reasoning": {"effort": "minimal"}}

    try:
        if event_type == "action_invoked":
            input_items = _action_invocation_input(event["action"])
        elif event_type == "user_message":
            input_items = _user_message_input(str(event["text"]))
        elif event_type in {"conversation_ended", "session_ended"}:
            return {"ok": True, "messages": []}
        else:
            return {"ok": False, "error": f"Unsupported event type: {event_type}"}

        result = await Runner.run(
            _get_agent(),
            input=input_items,
            conversation_id=conversation_id,
            run_config=run_config,
        )
    except Exception:
        logger.exception("Failed to process ChatKit event", extra={"event_type": event_type})
        return {"ok": False, "error": "internal_error"}

    messages = _serialise_messages(result.new_items)
    return {"ok": True, "messages": messages, "conversation_id": conversation_id}
