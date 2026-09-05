"""
app/services/ai/agents/rules.py
Agent 6 — Rules Engine Agent
Interprets natural-language IFTTT rules, converts to structured conditions/actions,
monitors rule execution.
"""
from typing import Dict, Any, List, AsyncIterator
import json
from app.services.ai.featherless import chat, stream

SYSTEM_PROMPT = """You are CoPenny AI's Rules Engine. You convert natural language financial rules
into structured, executable conditions and actions.

Your job:
1. Parse the user's natural language rule precisely
2. Extract the exact condition (IF part) and action (THEN part)
3. Return structured JSON that can be stored and executed

Supported condition types:
- threshold: balance/spending below or above a value
- category_limit: spending in a category exceeds limit
- transaction_amount: individual transaction exceeds amount
- date_trigger: rule triggers on a specific date/day

Supported action types:
- alert: send in-app notification
- auto_save: move amount to savings goal
- budget_adjustment: suggest budget change (requires confirmation)

CRITICAL: Always clarify what you're storing. Never execute destructive actions without explicit confirmation.
"""


async def parse_rule(natural_language: str) -> Dict[str, Any]:
    """
    Convert natural language rule to structured condition/action.
    Example: "If balance falls below ₹5,000, send me an alert"
    Returns structured rule data ready for PostgreSQL storage.
    """
    prompt = f"""Convert this financial rule to structured JSON:

Rule: "{natural_language}"

Return ONLY valid JSON:
{{
  "name": "Short descriptive name",
  "condition_type": "threshold|category_limit|transaction_amount|date_trigger",
  "condition_field": "balance|spending|amount|date",
  "condition_operator": "<|>|<=|>=|==",
  "condition_value": "numeric_value_as_string",
  "action_type": "alert|auto_save|budget_adjustment",
  "action_config": {{
    "message": "Alert message to show user",
    "amount": null,
    "goal_id": null
  }},
  "natural_language": "{natural_language}",
  "explanation": "Plain English explanation of what this rule does"
}}"""

    try:
        response = await chat(prompt, system=SYSTEM_PROMPT, max_tokens=600)
        response = response.strip().strip("```json").strip("```").strip()
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(response[start:end])
            parsed["natural_language"] = natural_language
            return {"success": True, "rule": parsed}
    except Exception as e:
        print(f"[RulesAgent] Parse error: {e}")

    return {
        "success": False,
        "error": "Could not parse rule. Please be more specific.",
        "example": "If balance falls below ₹5,000, send me an alert",
    }


async def evaluate_rules(rules: List[Dict[str, Any]],
                          financial_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluate all rules against current financial state.
    Returns list of triggered rules with recommended actions.
    """
    triggered = []
    balance = float(financial_snapshot.get("net") or 0)
    monthly_expense = float(financial_snapshot.get("total_expense") or 0) / 3

    for rule in rules:
        if not rule.get("is_active"):
            continue

        try:
            ctype = rule.get("condition_type", "threshold")
            field = rule.get("condition_field", "balance")
            op = rule.get("condition_operator", "<")
            val = float(rule.get("condition_value") or 0)

            # Determine the actual value to compare
            if field == "balance":
                actual = balance
            elif field == "spending":
                actual = monthly_expense
            else:
                actual = balance

            # Evaluate condition
            triggered_flag = False
            if op == "<" and actual < val:
                triggered_flag = True
            elif op == ">" and actual > val:
                triggered_flag = True
            elif op == "<=" and actual <= val:
                triggered_flag = True
            elif op == ">=" and actual >= val:
                triggered_flag = True

            if triggered_flag:
                action_config = rule.get("action_config") or {}
                if isinstance(action_config, str):
                    try:
                        action_config = json.loads(action_config)
                    except Exception:
                        action_config = {}

                triggered.append({
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "action_type": rule.get("action_type"),
                    "message": action_config.get("message", f"Rule '{rule.get('name')}' triggered."),
                    "condition_met": f"{field} ({actual:,.0f}) {op} {val:,.0f}",
                })
        except Exception as e:
            print(f"[RulesAgent] Rule evaluation error: {e}")

    return triggered


async def explain_rule(message: str) -> AsyncIterator[str]:
    """Stream explanation of what a rule does and how to set it up."""
    prompt = f"""User wants to set up this rule: "{message}"

Explain:
1. What this rule will do when triggered
2. What condition will be monitored (with specific values)
3. What action will be taken
4. How to verify it's working
5. Any limitations (e.g., you'll be notified but card can't be locked automatically)"""

    async for chunk in stream(prompt, system=SYSTEM_PROMPT):
        yield chunk
