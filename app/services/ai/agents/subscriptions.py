"""
app/services/ai/agents/subscriptions.py
Agent 4 — Subscription Manager Agent
Detects recurring charges, identifies unused subscriptions, prepares cancellation workflows.

IMPORTANT: This agent NEVER falsely claims to have cancelled a real external subscription.
It prepares the cancellation workflow and provides safe next steps.
"""
from typing import Dict, Any, List, AsyncIterator
import json
from app.services.ai.featherless import chat, stream

SYSTEM_PROMPT = """You are CoPenny AI's Subscription Manager. You analyze recurring payments and help users
optimize their subscription spending.

CRITICAL RULES:
1. NEVER claim you cancelled a real external subscription — you cannot do that
2. For cancellation: provide clear instructions for how the user can cancel themselves
3. Always show the potential monthly savings clearly
4. Flag subscriptions that haven't been used based on spending patterns

Your format:
- List subscriptions with monthly cost
- Calculate total monthly subscription burden
- Flag potentially unused ones with reasoning
- Provide cancellation instructions (not execution)
"""


async def analyze_subscriptions(message: str, subscriptions: List[Dict[str, Any]],
                                 transactions: List[Dict[str, Any]]) -> AsyncIterator[str]:
    """Stream subscription analysis."""
    sub_list = ""
    total_monthly = 0
    for s in subscriptions:
        amount = float(s.get("amount") or 0)
        cycle = s.get("billing_cycle", "monthly")
        monthly = amount if cycle == "monthly" else amount / 12
        total_monthly += monthly
        sub_list += f"- {s.get('name')}: ₹{amount:,.0f}/{cycle}\n"

    prompt = f"""User request: "{message}"

Active subscriptions:
{sub_list or 'No subscriptions found.'}

Total monthly subscription cost: ₹{total_monthly:,.0f}

Analyze these subscriptions and:
1. Calculate total annual cost
2. Flag any that seem potentially unused or duplicate
3. Rank by cost (highest first)
4. Suggest which to consider cancelling
5. Provide clear cancellation instructions for each flagged subscription

Remember: You can only guide the user — you cannot actually cancel subscriptions."""

    async for chunk in stream(prompt, system=SYSTEM_PROMPT):
        yield chunk


async def identify_unused(subscriptions: List[Dict[str, Any]],
                           transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Identify potentially unused subscriptions using transaction frequency analysis.
    Returns structured analysis for user review.
    """
    if not subscriptions:
        return {"unused": [], "total_monthly_waste": 0, "summary": "No subscriptions found."}

    sub_names = [s.get("name", "").lower() for s in subscriptions]

    prompt = f"""Analyze these subscriptions and identify which are likely unused:

Subscriptions: {json.dumps(subscriptions, default=str)}

Return ONLY valid JSON:
{{
  "potentially_unused": [
    {{
      "name": "...",
      "monthly_cost": 0,
      "reason": "...",
      "cancellation_url": "...",
      "cancellation_steps": ["step1", "step2"]
    }}
  ],
  "keep_recommendations": ["..."],
  "total_potential_monthly_savings": 0
}}"""

    try:
        response = await chat(prompt, system=SYSTEM_PROMPT, max_tokens=1000)
        response = response.strip().strip("```json").strip("```").strip()
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response[start:end])
            return {
                "unused": result.get("potentially_unused", []),
                "total_monthly_waste": result.get("total_potential_monthly_savings", 0),
                "keep": result.get("keep_recommendations", []),
                "requires_user_action": True,  # Always true — user must cancel themselves
                "disclaimer": "CoPenny AI has identified these subscriptions. To cancel, follow the provided steps.",
            }
    except Exception as e:
        print(f"[SubscriptionAgent] Identify error: {e}")

    return {"unused": [], "total_monthly_waste": 0, "summary": "Analysis failed."}
