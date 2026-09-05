"""
app/services/ai/agents/budget.py
Agent 2 — Budget Optimizer Agent
Analyzes spending vs budgets and generates AI-powered recommendations.
"""
from typing import Dict, Any, Optional, AsyncIterator
from app.services.ai.featherless import chat, stream

SYSTEM_PROMPT = """You are CoPenny AI's Budget Optimizer. You are a precise, data-driven financial analyst.

Your job:
1. Analyze real spending data vs budget limits provided to you
2. Identify overspending categories with specific numbers
3. Generate concrete, actionable budget reallocation recommendations
4. Be specific: use actual ₹ amounts from the data provided
5. Format clearly with sections: Current Status, Problem Areas, Recommendations

Rules:
- Use only the data provided, never invent numbers
- Always mention specific categories and amounts
- Be direct and practical
- Do NOT display your reasoning chain — present only clean recommendations
"""


async def analyze(user_id: str, message: str, financial_data: Dict[str, Any]) -> AsyncIterator[str]:
    """
    Stream budget analysis response.
    financial_data should contain budget utilization and transaction analytics.
    """
    budgets = financial_data.get("budgets", [])
    analytics = financial_data.get("analytics", {})

    budget_summary = ""
    if budgets:
        for b in budgets[:10]:
            pct = b.get("utilization_pct") or 0
            status = "⚠️ OVER" if pct > 100 else ("🔶 Near limit" if pct > 80 else "✅ OK")
            budget_summary += (
                f"- {b.get('category')}: ₹{b.get('spent', 0):,.0f} / ₹{b.get('monthly_limit', 0):,.0f} "
                f"({pct}%) {status}\n"
            )

    category_breakdown = ""
    by_cat_raw = analytics.get("by_category", {})
    # by_category is a dict {category: amount} — convert to sorted list
    if isinstance(by_cat_raw, dict):
        by_cat = sorted(
            [{"category": k, "total": v} for k, v in by_cat_raw.items()],
            key=lambda x: x["total"], reverse=True
        )
    elif isinstance(by_cat_raw, list):
        by_cat = by_cat_raw
    else:
        by_cat = []
    if by_cat:
        for cat in by_cat[:8]:
            count = cat.get("count", "")
            count_str = f" ({count} txns)" if count else ""
            category_breakdown += f"- {cat.get('category')}: Rs{cat.get('total', 0):,.0f}{count_str}\n"

    prompt = f"""User's financial situation:

BUDGET UTILIZATION (this month):
{budget_summary or 'No budget data available.'}

SPENDING BY CATEGORY (last 90 days):
{category_breakdown or 'No transaction data available.'}

Total Income: ₹{analytics.get('total_income', 0):,.0f}
Total Expenses: ₹{analytics.get('total_expense', 0):,.0f}
Net: ₹{analytics.get('net', 0):,.0f}

User asked: "{message}"

Provide a detailed, actionable budget analysis."""

    async for chunk in stream(prompt, system=SYSTEM_PROMPT):
        yield chunk


async def generate_optimization(financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Non-streaming: generate structured optimization recommendations.
    Returns proposed budget changes for user confirmation.
    """
    budgets = financial_data.get("budgets", [])
    over_budget = [b for b in budgets if float(b.get("utilization_pct") or 0) > 100]

    if not over_budget:
        return {
            "recommendations": [],
            "summary": "Your spending is within budget across all categories. Great work!",
            "requires_confirmation": False
        }

    prompt = f"""Analyze these over-budget categories and suggest specific monthly limit adjustments:

Over-budget categories:
{over_budget}

Return ONLY a JSON array of recommendations:
[
  {{"category": "...", "current_limit": 0, "suggested_limit": 0, "reasoning": "..."}}
]"""

    try:
        import json
        response = await chat(prompt, system=SYSTEM_PROMPT, max_tokens=800)
        response = response.strip().strip("```json").strip("```").strip()
        # Find JSON array
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            recs = json.loads(response[start:end])
        else:
            recs = []
    except Exception as e:
        print(f"[BudgetAgent] Optimization error: {e}")
        recs = []

    return {
        "recommendations": recs,
        "over_budget_count": len(over_budget),
        "requires_confirmation": len(recs) > 0,
        "summary": f"Found {len(over_budget)} over-budget categories. Review recommendations below."
    }
