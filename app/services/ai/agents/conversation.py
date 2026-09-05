"""
app/services/ai/agents/conversation.py
Agent 1 — Conversation Agent
Understands user intent and routes to the appropriate specialist agent.
"""
from typing import Dict, Any, Optional
from app.services.ai.featherless import chat

SYSTEM_PROMPT = """You are CoPenny AI's intent routing agent. Your ONLY job is to analyze the user message
and return a JSON response identifying which specialized agent should handle it.

Available agents:
- budget: For questions about spending, budget optimization, expense analysis
- goals: For savings goals, financial targets, saving plans
- subscriptions: For recurring payments, subscription management
- anomaly: For suspicious transactions, unusual spending, fraud detection
- rules: For creating automation rules, alerts, IFTTT-style conditions
- general: For general financial questions, greetings, or unclear intent

You must respond with ONLY valid JSON, no explanation:
{"agent": "<agent_name>", "confidence": 0.95, "intent_summary": "<brief summary>"}
"""


async def route(message: str, context: Optional[list] = None) -> Dict[str, Any]:
    """
    Route user message to appropriate specialist agent.
    Returns: {"agent": str, "confidence": float, "intent_summary": str}
    """
    prompt = f"User message: {message}"
    if context:
        recent = context[-3:] if len(context) > 3 else context
        prompt = f"Recent context: {recent}\n\nLatest message: {message}"

    try:
        import json
        response = await chat(prompt, system=SYSTEM_PROMPT, max_tokens=200)
        # Strip markdown if present
        response = response.strip().strip("```json").strip("```").strip()
        result = json.loads(response)
        return {
            "agent": result.get("agent", "general"),
            "confidence": float(result.get("confidence", 0.7)),
            "intent_summary": result.get("intent_summary", message[:100]),
        }
    except Exception as e:
        print(f"[ConversationAgent] Routing error: {e}")
        # Keyword-based fallback routing
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["budget", "spend", "expense", "overspend", "category"]):
            agent = "budget"
        elif any(w in msg_lower for w in ["goal", "save", "saving", "target", "goa", "vacation"]):
            agent = "goals"
        elif any(w in msg_lower for w in ["subscription", "recurring", "cancel", "netflix", "spotify"]):
            agent = "subscriptions"
        elif any(w in msg_lower for w in ["unusual", "suspicious", "fraud", "anomaly", "strange"]):
            agent = "anomaly"
        elif any(w in msg_lower for w in ["rule", "if", "when", "alert", "notify", "ifttt"]):
            agent = "rules"
        else:
            agent = "general"
        return {"agent": agent, "confidence": 0.6, "intent_summary": message[:100]}
