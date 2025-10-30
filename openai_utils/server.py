# server.py
import json

import config
from fastapi import FastAPI, Request
from agents import Runner
from agent_setup import build_wizard_agent

app = FastAPI()
agent = build_wizard_agent(vector_store_ids=["VS_123"])


@app.post("/chatkit/respond")
async def respond(req: Request):
    """
    ChatKit will POST events here (messages, action invocations).
    Parse the event, then call Runner.run(agent, input=..., run_config=...) as needed.
    """
    event = await req.json()
    # Example: action event
    if event.get("type") == "action_invoked":
        action_id = event["action"]["id"]
        payload = event["action"]["payload"]
        # Map action->tool call by sending a user instruction like:
        # "Call tool: add_stage with {...}" OR directly invoke tool via Agents API if you manage the loop.
        # For simplicity, pass natural language + payload. Agent will pick the right tool.
        result = await Runner.run(
            agent,
            input=f"Action {action_id} with payload: {json.dumps(payload)}",
            # You can set model config including reasoning effort here per event:
            run_config={"model": config.REASONING_MODEL, "reasoning": {"effort": "minimal"}},
        )
        return {"ok": True, "messages": result.messages}
    # Message event
    elif event.get("type") == "user_message":
        result = await Runner.run(agent, input=event["text"])
        return {"ok": True, "messages": result.messages}
    return {"ok": False}
