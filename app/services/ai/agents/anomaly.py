"""
app/services/ai/agents/anomaly.py
Agent 5 — Anomaly Detection Agent
Detects suspicious/unusual transactions, assigns confidence score, explains anomaly.

IMPORTANT: If card-locking APIs are not integrated, actions are guidance only.
"""
from typing import Dict, Any, List, AsyncIterator
import json
from app.services.ai.featherless import chat, stream

SYSTEM_PROMPT = """You are CoPenny AI's Anomaly Detection specialist. You analyze unusual financial transactions
and explain why they're suspicious.

Your job:
1. Explain why each flagged transaction is unusual
2. Assess risk level (low/medium/high)
3. Provide clear, actionable next steps
4. Never cause panic — be calm and professional

Format:
- Transaction summary
- Why it's flagged (with specific comparison to normal behavior)
- Risk assessment
- Recommended actions (what the user should do themselves)

Note: You cannot lock cards or contact banks directly. Provide guidance only.
"""


async def explain_anomalies(anomalies: List[Dict[str, Any]], message: str) -> AsyncIterator[str]:
    """Stream anomaly explanation."""
    if not anomalies:
        async def _empty():
            yield "No unusual transactions detected in your recent spending. Your spending patterns look normal."
        async for chunk in _empty():
            yield chunk
        return

    anomaly_summary = ""
    for a in anomalies[:5]:
        anomaly_summary += (
            f"- ₹{a.get('amount', 0):,.0f} — {a.get('category')} "
            f"({a.get('merchant') or a.get('description', '')}): "
            f"{a.get('confidence', 0)}% confidence, {a.get('reason', '')}\n"
        )

    prompt = f"""User context: "{message}"

Flagged transactions:
{anomaly_summary}

Provide a clear explanation of:
1. Why each transaction is suspicious
2. What this pattern might indicate
3. Specific steps the user should take (check bank statement, contact bank if needed, etc.)
4. How to prevent similar issues

Be reassuring but thorough."""

    async for chunk in stream(prompt, system=SYSTEM_PROMPT):
        yield chunk


async def classify_transaction(transaction: Dict[str, Any],
                                user_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify a single transaction as normal or anomalous.
    Returns confidence and explanation.
    """
    prompt = f"""Is this transaction anomalous given the user's stats?

Transaction:
- Amount: ₹{transaction.get('amount', 0):,.0f}
- Category: {transaction.get('category')}
- Merchant: {transaction.get('merchant', transaction.get('description', ''))}
- Date: {transaction.get('date')}

User's normal spending stats for this category:
- Average: ₹{user_stats.get('avg', 0):,.0f}
- Usual max: ₹{user_stats.get('max', 0):,.0f}
- Transaction count: {user_stats.get('count', 0)}

Return ONLY valid JSON:
{{"is_anomaly": true/false, "confidence": 0-100, "reason": "...", "risk_level": "low|medium|high"}}"""

    try:
        response = await chat(prompt, system=SYSTEM_PROMPT, max_tokens=300)
        response = response.strip().strip("```json").strip("```").strip()
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except Exception as e:
        print(f"[AnomalyAgent] Classification error: {e}")

    return {"is_anomaly": False, "confidence": 0, "reason": "Analysis unavailable.", "risk_level": "low"}
