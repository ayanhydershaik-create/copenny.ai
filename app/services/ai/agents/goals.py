"""
app/services/ai/agents/goals.py
Agent 3 — Goal Execution Agent
Understands savings goals, calculates realistic plans, and executes approved actions.
"""
from typing import Dict, Any, Optional, AsyncIterator
import json
from app.services.ai.featherless import chat, stream

SYSTEM_PROMPT = """You are CoPenny AI's Goal Execution specialist. You help users create and achieve savings goals.

Your job:
1. Understand the user's savings goal from their message
2. Analyze their income and spending to determine feasibility
3. Create a concrete, realistic savings plan with monthly targets
4. Show the timeline to reach the goal
5. Ask for confirmation before creating/modifying goals

Format responses clearly:
- Goal summary
- Monthly savings required
- Projected timeline
- Recommended auto-save amount
- Specific actions to free up money

Rules:
- Be realistic — don't promise impossible targets
- Use actual ₹ amounts from data provided
- Always ask for user confirmation before creating a goal
"""


async def analyze_goal_request(message: str, financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract goal details from natural language message.
    Returns structured goal data for user confirmation.
    """
    income = financial_data.get("total_income", 0)
    expense = financial_data.get("total_expense", 0)
    monthly_income = income / max(3, 1)  # 90-day data
    monthly_expense = expense / max(3, 1)
    monthly_savings = monthly_income - monthly_expense

    prompt = f"""User message: "{message}"

User's financial data:
- Monthly income (approx): ₹{monthly_income:,.0f}
- Monthly expenses (approx): ₹{monthly_expense:,.0f}
- Current monthly savings capacity: ₹{monthly_savings:,.0f}

Extract goal details and create a plan. Return ONLY valid JSON:
{{
  "goal_name": "...",
  "target_amount": 0,
  "monthly_savings_needed": 0,
  "timeline_months": 0,
  "recommended_auto_save": 0,
  "feasibility": "high|medium|low",
  "plan_summary": "...",
  "suggestions": ["...", "..."]
}}"""

    try:
        response = await chat(prompt, system=SYSTEM_PROMPT, max_tokens=600)
        response = response.strip().strip("```json").strip("```").strip()
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except Exception as e:
        print(f"[GoalAgent] Extraction error: {e}")

    return {
        "goal_name": "Savings Goal",
        "target_amount": 0,
        "monthly_savings_needed": 0,
        "timeline_months": 0,
        "recommended_auto_save": monthly_savings * 0.3,
        "feasibility": "medium",
        "plan_summary": "Unable to parse goal details. Please specify the amount and target date.",
        "suggestions": [],
    }


async def explain_goal(message: str, goals: list, financial_data: Dict[str, Any]) -> AsyncIterator[str]:
    """Stream a goal planning explanation."""
    goals_summary = ""
    for g in goals[:5]:
        target = float(g.get("target_amount") or 0)
        current = float(g.get("current_amount") or 0)
        pct = round((current / target * 100) if target > 0 else 0, 1)
        goals_summary += f"- {g.get('name')}: ₹{current:,.0f} / ₹{target:,.0f} ({pct}%)\n"

    income = float(financial_data.get("total_income") or 0)
    expense = float(financial_data.get("total_expense") or 0)
    monthly_capacity = (income - expense) / 3

    prompt = f"""User request: "{message}"

Current savings goals:
{goals_summary or 'No goals set yet.'}

Financial capacity:
- Monthly savings capacity: ₹{monthly_capacity:,.0f}

Provide a clear, encouraging goal planning response with:
1. Assessment of current goals
2. Specific savings plan for the requested goal
3. Monthly targets and timeline
4. Tips to achieve the goal faster"""

    async for chunk in stream(prompt, system=SYSTEM_PROMPT):
        yield chunk
