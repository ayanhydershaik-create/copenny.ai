"""
app/routers/rules.py
IFTTT Rules Engine API endpoints backed by PostgreSQL hackwave_db.
AI parses natural language rules into structured conditions/actions.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from fastapi import Cookie

router = APIRouter(prefix="/api/rules", tags=["rules"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class RuleCreate(BaseModel):
    natural_language: str  # e.g. "If balance falls below ₹5,000, send me an alert"


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def list_rules(user_id: str = Depends(get_user_id)):
    """Get all IFTTT rules from PostgreSQL."""
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    rules = pg.get_rules(user_id)
    return {"rules": rules, "count": len(rules)}


@router.post("", status_code=201)
async def create_rule(body: RuleCreate, user_id: str = Depends(get_user_id)):
    """
    Parse natural language rule with AI and store in PostgreSQL.
    Returns the parsed rule for user confirmation before storage.
    """
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")

    from app.services.ai.agents.rules import parse_rule
    result = await parse_rule(body.natural_language)

    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error", "Could not parse rule"))

    rule_data = result["rule"]
    try:
        stored = pg.create_rule(user_id, rule_data)
        return {
            "rule": stored,
            "explanation": rule_data.get("explanation"),
            "message": "Rule created and will be monitored.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{rule_id}")
def update_rule(rule_id: str, body: RuleUpdate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    updated = pg.update_rule(rule_id, user_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    pg.delete_rule(rule_id, user_id)
    return None


@router.post("/evaluate")
async def evaluate_rules(user_id: str = Depends(get_user_id)):
    """
    Evaluate all active rules against current financial state.
    Returns list of triggered rules with recommended actions.
    """
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")

    rules = pg.get_rules(user_id)
    analytics = pg.get_transaction_analytics(user_id)
    health = pg.calculate_health_score(user_id)

    snapshot = {
        "net": analytics.get("net", 0),
        "total_income": analytics.get("total_income", 0),
        "total_expense": analytics.get("total_expense", 0),
        "health_score": health.get("total", 0),
    }

    from app.services.ai.agents.rules import evaluate_rules as eval_rules
    triggered = await eval_rules(rules, snapshot)

    # Note: rules table has no updated_at column; is_active toggling done via update_rule endpoint

    return {
        "triggered": triggered,
        "triggered_count": len(triggered),
        "total_rules_evaluated": len([r for r in rules if r.get("is_active")]),
    }
