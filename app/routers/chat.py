"""
app/routers/chat.py
Streaming Chat Router with Server-Sent Events (SSE) and Six Specialized Featherless Agents.

Flow:
User message -> Intent Routing (Conversation Agent) -> Specialist Agent
Progress events emitted:
- "Analyzing your spending..."
- "Checking your active subscriptions..."
- "Comparing your budget..."
- "Preparing recommendations..."
Incremental tokens streamed to frontend without exposing private reasoning.
"""
import json
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Cookie
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from app.services.ai.agents import (
    conversation as conversation_agent,
    budget as budget_agent,
    goals as goals_agent,
    subscriptions as subscriptions_agent,
    anomaly as anomaly_agent,
    rules as rules_agent,
)
from app.services.ai.featherless import stream as general_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class ChatMessageReq(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[List[Dict[str, str]]] = []


@router.post("/stream")
async def chat_stream(body: ChatMessageReq, request: Request, user_id: str = Depends(get_user_id)):
    """
    Server-Sent Events (SSE) streaming chat endpoint.
    Emits structured JSON events:
    - {"type": "progress", "message": "..."}
    - {"type": "agent", "name": "...", "confidence": 0.95}
    - {"type": "token", "content": "..."}
    - {"type": "done", "action": {...}}
    """
    pg = get_postgres_service()

    async def event_generator():
        # Step 1: Record user message in DB
        try:
            if pg.is_connected():
                pg.save_message(user_id=user_id, role="user", content=body.message)
        except Exception as e:
            print(f"[ChatStream] Error saving user message: {e}")

        # Step 2: Emit routing progress
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Understanding your request...'})}\n\n"
        await asyncio.sleep(0.05)

        # Route request via Agent 1 (Conversation Agent)
        routed = await conversation_agent.route(body.message, context=body.context)
        agent_name = routed.get("agent", "general")
        confidence = routed.get("confidence", 0.7)

        yield f"data: {json.dumps({'type': 'agent', 'name': agent_name, 'confidence': confidence})}\n\n"

        full_response_text = ""

        # Step 3: Dispatch to specialized agent
        try:
            if agent_name == "budget":
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Analyzing your spending & budgets...'})}\n\n"
                budgets = pg.get_budget_utilization(user_id) if pg.is_connected() else []
                analytics = pg.get_transaction_analytics(user_id) if pg.is_connected() else {}
                financial_data = {"budgets": budgets, "analytics": analytics}

                async for token in budget_agent.analyze(user_id, body.message, financial_data):
                    full_response_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            elif agent_name == "goals":
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Calculating your savings plan...'})}\n\n"
                goals = pg.get_goals(user_id) if pg.is_connected() else []
                analytics = pg.get_transaction_analytics(user_id) if pg.is_connected() else {}

                async for token in goals_agent.explain_goal(body.message, goals, analytics):
                    full_response_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            elif agent_name == "subscriptions":
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Checking your active subscriptions...'})}\n\n"
                subs = pg.get_subscriptions(user_id, active_only=True) if pg.is_connected() else []
                txs = pg.get_transactions(user_id, limit=100) if pg.is_connected() else []

                async for token in subscriptions_agent.analyze_subscriptions(body.message, subs, txs):
                    full_response_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            elif agent_name == "anomaly":
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Scanning recent transactions for anomalies...'})}\n\n"
                anomalies = pg.get_anomalies(user_id) if pg.is_connected() else []

                async for token in anomaly_agent.explain_anomalies(anomalies, body.message):
                    full_response_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            elif agent_name == "rules":
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Configuring automation rule...'})}\n\n"
                async for token in rules_agent.explain_rule(body.message):
                    full_response_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            else:
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Synthesizing financial advice...'})}\n\n"
                sys_prompt = "You are CoPenny AI, an executive-grade financial assistant by RedHack. Provide crisp, professional advice."
                async for token in general_stream(body.message, system=sys_prompt):
                    full_response_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        except Exception as e:
            err_msg = f"Sorry, I encountered an issue processing your request: {str(e)}"
            yield f"data: {json.dumps({'type': 'token', 'content': err_msg})}\n\n"
            full_response_text = err_msg

        # Step 4: Record assistant message in DB
        try:
            if pg.is_connected() and full_response_text:
                pg.save_message(user_id=user_id, role="assistant", content=full_response_text, agent=agent_name)
        except Exception as e:
            print(f"[ChatStream] Error saving assistant response: {e}")

        yield f"data: {json.dumps({'type': 'done', 'agent': agent_name})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("")
async def chat_json(body: ChatMessageReq, user_id: str = Depends(get_user_id)):
    """
    Standard non-streaming JSON chat endpoint.
    Routes through the 6 specialized Featherless agents and persists to PostgreSQL.
    """
    pg = get_postgres_service()
    if pg.is_connected():
        try:
            pg.save_message(user_id=user_id, role="user", content=body.message)
        except Exception as e:
            print(f"[ChatJSON] Error saving user message: {e}")

    routed = await conversation_agent.route(body.message, context=body.context)
    agent_name = routed.get("agent", "general")
    confidence = routed.get("confidence", 0.7)

    full_response_text = ""
    try:
        if agent_name == "budget":
            budgets = pg.get_budget_utilization(user_id) if pg.is_connected() else []
            analytics = pg.get_transaction_analytics(user_id) if pg.is_connected() else {}
            financial_data = {"budgets": budgets, "analytics": analytics}
            async for token in budget_agent.analyze(user_id, body.message, financial_data):
                full_response_text += token
        elif agent_name == "goals":
            goals = pg.get_goals(user_id) if pg.is_connected() else []
            analytics = pg.get_transaction_analytics(user_id) if pg.is_connected() else {}
            async for token in goals_agent.explain_goal(body.message, goals, analytics):
                full_response_text += token
        elif agent_name == "subscriptions":
            subs = pg.get_subscriptions(user_id, active_only=True) if pg.is_connected() else []
            txs = pg.get_transactions(user_id, limit=100) if pg.is_connected() else []
            async for token in subscriptions_agent.analyze_subscriptions(body.message, subs, txs):
                full_response_text += token
        elif agent_name == "anomaly":
            anomalies = pg.get_anomalies(user_id) if pg.is_connected() else []
            async for token in anomaly_agent.explain_anomalies(anomalies, body.message):
                full_response_text += token
        elif agent_name == "rules":
            async for token in rules_agent.explain_rule(body.message):
                full_response_text += token
        else:
            sys_prompt = "You are CoPenny AI, an executive-grade financial assistant by RedHack. Provide crisp, professional advice."
            async for token in general_stream(body.message, system=sys_prompt):
                full_response_text += token
    except Exception as e:
        full_response_text = f"Sorry, I encountered an issue processing your request: {str(e)}"

    if pg.is_connected() and full_response_text:
        try:
            pg.save_message(user_id=user_id, role="assistant", content=full_response_text, agent=agent_name)
        except Exception as e:
            print(f"[ChatJSON] Error saving assistant response: {e}")

    return {
        "answer": full_response_text,
        "agent": agent_name,
        "confidence": confidence,
        "status": "success",
        "type": "text"
    }


@router.get("/history")
def get_chat_history(user_id: str = Depends(get_user_id), limit: int = 50):
    """Retrieve chat history for the user from PostgreSQL."""
    pg = get_postgres_service()
    if not pg.is_connected():
        return {"messages": []}
    return {"messages": pg.get_messages(user_id, limit=limit)}
