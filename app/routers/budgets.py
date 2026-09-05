"""
app/routers/budgets.py
Budget management API endpoints backed by PostgreSQL hackwave_db.
AI-powered budget optimization with user confirmation required.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from fastapi import Cookie

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float
    period: str = "monthly"


class BudgetUpdate(BaseModel):
    category: Optional[str] = None
    monthly_limit: Optional[float] = None
    period: Optional[str] = None


class BudgetApplyReq(BaseModel):
    recommendations: List[dict]  # [{"category": str, "suggested_limit": float}]


@router.get("")
def list_budgets(user_id: str = Depends(get_user_id)):
    """Get all budgets with current month utilization from PostgreSQL."""
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    utilization = pg.get_budget_utilization(user_id)
    budgets = pg.get_budgets(user_id)
    return {
        "budgets": budgets,
        "utilization": utilization,
        "over_budget_count": sum(1 for b in utilization if float(b.get("utilization_pct") or 0) > 100),
        "count": len(budgets),
    }


@router.post("", status_code=201)
def create_budget(body: BudgetCreate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        budget = pg.create_budget(user_id, body.model_dump())
        return budget
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{budget_id}")
def update_budget(budget_id: str, body: BudgetUpdate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    updated = pg.update_budget(budget_id, user_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Budget not found")
    return updated


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    pg.delete_budget(budget_id, user_id)
    return None


@router.get("/optimize")
async def optimize_budgets(user_id: str = Depends(get_user_id)):
    """
    AI-powered budget optimization.
    Returns recommendations — requires user confirmation before applying.
    """
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")

    utilization = pg.get_budget_utilization(user_id)
    analytics = pg.get_transaction_analytics(user_id)

    from app.services.ai.agents.budget import generate_optimization
    result = await generate_optimization({
        "budgets": utilization,
        "analytics": analytics,
    })
    return result


@router.post("/apply-optimization")
def apply_optimization(body: BudgetApplyReq, user_id: str = Depends(get_user_id)):
    """
    Apply confirmed budget optimization recommendations to PostgreSQL.
    This is the destructive endpoint — requires explicit user confirmation first.
    """
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")

    applied = []
    errors = []
    for rec in body.recommendations:
        try:
            category = rec.get("category")
            new_limit = rec.get("suggested_limit")
            if not category or not new_limit:
                continue
            # Upsert budget
            result = pg.create_budget(user_id, {
                "category": category,
                "monthly_limit": new_limit,
                "period": "monthly",
            })
            applied.append({"category": category, "new_limit": new_limit, "id": result.get("id")})
        except Exception as e:
            errors.append({"category": rec.get("category"), "error": str(e)})

    return {
        "applied": applied,
        "errors": errors,
        "message": f"Applied {len(applied)} budget optimizations successfully.",
    }
